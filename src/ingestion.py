
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import docx
import frontmatter
import openpyxl
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_CATALOG = DEFAULT_DATA_DIR / "metadata_catalog.json"

_CATALOG_OWNED_KEYS = ("file_path", "file_format")

# Số ô không rỗng tối thiểu để coi một dòng Excel là header của bảng dữ liệu.
# Các dòng preamble (`Mã tài liệu | FEE-001`) chỉ có <= 2 ô.
_MIN_CELLS_FOR_HEADER_ROW = 3


# --------------------------------------------------------------------------- #
# Metadata helpers
# --------------------------------------------------------------------------- #
def _to_primitive(value: Any) -> str | int | float | bool | None:
    """Chuyển đổi giá trị metadata sang định dạng mà ChromaDB chấp nhận.

    ChromaDB chỉ nhận str/int/float/bool. YAML front-matter trả về
    ``datetime.date`` cho các trường ngày tháng nên bắt buộc phải đổi sang ISO.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (str, int, float)):
        return value
    return str(value)


def normalize_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``raw`` with only non-empty, ChromaDB-safe values."""
    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        primitive = _to_primitive(value)
        if primitive is None:
            continue
        if isinstance(primitive, str) and not primitive.strip():
            continue
        normalized[key] = primitive.strip() if isinstance(primitive, str) else primitive
    return normalized


def merge_metadata(
    catalog_entry: dict[str, Any], doc_meta: dict[str, Any]
) -> dict[str, Any]:
    """Merge catalog metadata with the metadata embedded in the document.

    Catalog là nền (luôn đầy đủ 9 trường), front-matter phủ lên vì nó sát tài
    liệu hơn và giàu hơn (title, sprint, severity, superseded_by...). Riêng
    ``file_path``/``file_format`` luôn lấy theo catalog.
    """
    base = normalize_metadata(catalog_entry)
    overlay = normalize_metadata(doc_meta)
    doc_id = base.get("doc_id", "<unknown>")

    for key, value in overlay.items():
        if key in _CATALOG_OWNED_KEYS:
            continue
        if key in base and base[key] != value:
            logger.warning(
                "[%s] metadata conflict on '%s': catalog=%r, document=%r "
                "-> dùng giá trị của tài liệu",
                doc_id,
                key,
                base[key],
                value,
            )
        base[key] = value

    return base


# --------------------------------------------------------------------------- #
# Markdown table helper (dùng chung cho .docx và .xlsx)
# --------------------------------------------------------------------------- #
def _escape_cell(text: str) -> str:
    """Escape pipes and collapse newlines so a cell stays on one table row."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _rows_to_markdown_table(rows: list[list[str]]) -> str:
    """Render rows (first one is the header) as a GitHub-flavoured Markdown table."""
    if not rows:
        return ""

    width = max(len(row) for row in rows)
    padded = [[*row, *([""] * (width - len(row)))] for row in rows]

    header, *body = padded
    lines = [
        "| " + " | ".join(_escape_cell(c) for c in header) + " |",
        "|" + "---|" * width,
    ]
    lines.extend("| " + " | ".join(_escape_cell(c) for c in row) + " |" for row in body)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Reader: Markdown
# --------------------------------------------------------------------------- #
def read_markdown(path: Path) -> tuple[str, dict[str, Any]]:
    """Read a ``.md`` file, splitting YAML front-matter from the body."""
    post = frontmatter.load(str(path), encoding="utf-8")
    if not post.metadata:
        logger.warning("%s: không tìm thấy YAML front-matter", path.name)
    return post.content.strip(), dict(post.metadata)


# --------------------------------------------------------------------------- #
# Reader: DOCX
# --------------------------------------------------------------------------- #
def _heading_level(style_name: str) -> int | None:
    """Return the Markdown heading level for a Word style, or None if not a heading."""
    if style_name == "Title":
        return 1
    match = re.fullmatch(r"Heading (\d)", style_name)
    return int(match.group(1)) if match else None


def _docx_table_rows(table: DocxTable) -> list[list[str]]:
    return [[cell.text.strip() for cell in row.cells] for row in table.rows]


def read_docx(path: Path) -> tuple[str, dict[str, Any]]:
    """Read a ``.docx`` file into Markdown, preserving paragraph/table order.

    Duyệt trực tiếp các phần tử con của body thay vì ghép ``doc.paragraphs`` với
    ``doc.tables``: bảng phân loại chênh lệch trong SOP_DoiSoat_v2.0.docx nằm
    giữa mục 5 và mục 6, nếu nối bảng vào cuối file thì nó mất hoàn toàn ngữ cảnh.
    """
    document = docx.Document(str(path))
    blocks: list[str] = []
    bullets: list[str] = []

    def flush_bullets() -> None:
        # Gom các gạch đầu dòng liên tiếp thành một danh sách Markdown liền mạch,
        # thay vì mỗi dòng là một đoạn văn riêng.
        if bullets:
            blocks.append("\n".join(bullets))
            bullets.clear()

    for element in document.element.body.iterchildren():
        tag = element.tag.split("}")[-1]

        if tag == "p":
            paragraph = DocxParagraph(element, document)
            text = paragraph.text.strip()
            if not text:
                continue

            # p.style có thể là None với các đoạn không gán style tường minh.
            style_name = paragraph.style.name if paragraph.style is not None else ""
            level = _heading_level(style_name)
            if style_name == "List Paragraph":
                bullets.append("- " + text)
                continue

            flush_bullets()
            blocks.append("#" * level + " " + text if level is not None else text)

        elif tag == "tbl":
            flush_bullets()
            rows = _docx_table_rows(DocxTable(element, document))
            table_md = _rows_to_markdown_table(rows)
            if table_md:
                blocks.append(table_md)

    flush_bullets()
    return "\n\n".join(blocks), {}


# --------------------------------------------------------------------------- #
# Reader: XLSX
# --------------------------------------------------------------------------- #
def _format_number(value: int | float, number_format: str) -> str:
    """Render a numeric cell the way Excel displays it.

    Bắt buộc phải áp ``number_format``: cột "Mức phí" lưu 0.015 với định dạng
    "0.0%" — nếu dump giá trị thô thì RAG đọc được "0.015" thay vì "1.5%".
    """
    if "%" in number_format:
        decimals = len(number_format.split("%")[0].partition(".")[2])
        return f"{value * 100:.{decimals}f}%"

    if isinstance(value, int) or float(value).is_integer():
        # Dấu chấm phân cách nghìn để khớp cách viết trong các file .md
        # (5.000.000) — giúp BM25 match được giữa Excel và Markdown.
        return f"{int(value):,}".replace(",", ".")

    return str(value)


def _format_cell(cell: Any) -> str:
    """Convert one openpyxl cell into display text."""
    value = cell.value
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return _format_number(value, cell.number_format or "General")
    return str(value).strip()


def read_xlsx(path: Path) -> tuple[str, dict[str, Any]]:
    """Read an ``.xlsx`` file into Markdown, one section per sheet.

    Dùng ``data_only=True`` để lấy giá trị đã tính sẵn thay vì chuỗi công thức
    (``=IF(...)``, ``=SUM(...)``).
    """
    workbook = openpyxl.load_workbook(str(path), data_only=True)
    sections: list[str] = []

    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        rendered_rows = [
            [_format_cell(cell) for cell in row] for row in sheet.iter_rows()
        ]

        _assert_no_raw_formula(path, sheet_name, rendered_rows)

        preamble, table_rows = _split_preamble(rendered_rows)

        block = [f"## Sheet: {sheet_name}"]
        if preamble:
            block.append("\n".join(preamble))
        table_md = _rows_to_markdown_table(table_rows)
        if table_md:
            block.append(table_md)
        sections.append("\n\n".join(block))

    return "\n\n".join(sections), {}


def _assert_no_raw_formula(
    path: Path, sheet_name: str, rows: list[list[str]]
) -> None:
    """Fail loudly if a cell still holds a formula string instead of its value."""
    for row_idx, row in enumerate(rows, start=1):
        for cell in row:
            if cell.startswith("="):
                message = (
                    f"{path.name} / sheet '{sheet_name}' dòng {row_idx}: đọc được "
                    f"công thức thô {cell!r} thay vì giá trị. File thiếu cached "
                    f"value — mở và lưu lại bằng Excel/LibreOffice."
                )
                logger.error(message)
                raise ValueError(message)


def _split_preamble(rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    """Split the metadata preamble rows from the actual data table.

    Mọi sheet đều mở đầu bằng 7-9 dòng metadata (`Mã tài liệu | FEE-001`) trước
    header thật. Dòng header là dòng đầu tiên có đủ số ô — preamble chỉ có <= 2 ô.
    """
    header_idx = next(
        (
            idx
            for idx, row in enumerate(rows)
            if sum(1 for cell in row if cell) >= _MIN_CELLS_FOR_HEADER_ROW
        ),
        None,
    )
    if header_idx is None:
        return [_preamble_line(row) for row in rows if any(row)], []

    preamble = [_preamble_line(row) for row in rows[:header_idx] if any(row)]
    table_rows = [row for row in rows[header_idx:] if any(row)]
    return preamble, table_rows


def _preamble_line(row: list[str]) -> str:
    """Render a preamble row as ``**Key:** value`` (or plain text if it has one cell)."""
    filled = [cell for cell in row if cell]
    if len(filled) == 1:
        return filled[0]
    return f"**{filled[0]}:** " + " ".join(filled[1:])


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
_READERS = {"md": read_markdown, "docx": read_docx, "xlsx": read_xlsx}


def load_catalog(catalog_path: Path | str = DEFAULT_CATALOG) -> list[dict[str, Any]]:
    """Load the document catalog that drives ingestion."""
    with open(catalog_path, encoding="utf-8") as handle:
        return json.load(handle)


def ingest_document(
    entry: dict[str, Any], data_dir: Path | str = DEFAULT_DATA_DIR
) -> dict[str, Any]:
    """Ingest one catalog entry into the normalised document dict."""
    doc_id = entry["doc_id"]
    file_format = entry["file_format"]
    path = Path(data_dir) / entry["file_path"]

    if not path.is_file():
        raise FileNotFoundError(
            f"[{doc_id}] catalog trỏ tới file không tồn tại: {path}"
        )

    reader = _READERS.get(file_format)
    if reader is None:
        raise ValueError(f"[{doc_id}] định dạng chưa hỗ trợ: {file_format!r}")

    content, doc_meta = reader(path)
    if not content.strip():
        raise ValueError(f"[{doc_id}] đọc ra nội dung rỗng: {path}")

    if doc_meta.get("doc_id") and doc_meta["doc_id"] != doc_id:
        logger.warning(
            "[%s] doc_id trong tài liệu là %r, không khớp catalog",
            doc_id,
            doc_meta["doc_id"],
        )

    metadata = merge_metadata(entry, doc_meta)
    metadata["char_count"] = len(content)

    return {"doc_id": doc_id, "content": content, "metadata": metadata}


def ingest_all(
    catalog_path: Path | str = DEFAULT_CATALOG,
    data_dir: Path | str = DEFAULT_DATA_DIR,
) -> list[dict[str, Any]]:
    """Ingest all documents listed in the catalog."""
    catalog = load_catalog(catalog_path)
    documents = [ingest_document(entry, data_dir) for entry in catalog]

    logger.info(
        "Đã nạp %d tài liệu (%d ký tự)",
        len(documents),
        sum(doc["metadata"]["char_count"] for doc in documents),
    )
    return documents


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    docs = ingest_all()

    print(f"\n{'doc_id':<14}{'fmt':<6}{'status':<12}{'chars':>8}{'tables':>8}")
    print("-" * 48)
    for doc in docs:
        n_tables = doc["content"].count("\n|---")
        print(
            f"{doc['doc_id']:<14}"
            f"{doc['metadata']['file_format']:<6}"
            f"{doc['metadata']['status']:<12}"
            f"{doc['metadata']['char_count']:>8}"
            f"{n_tables:>8}"
        )
    print("-" * 48)
    print(f"Tổng: {len(docs)} tài liệu")
