"""Structure-aware chunking for the ManhPay knowledge base.

Splits the unified Markdown produced by :mod:`src.ingestion` along its H1/H2
headings instead of at a fixed character count, so a chunk always corresponds to
one meaningful section of a document::

    {"chunk_id": str, "content": str, "doc_id": str, "metadata": dict}

Two rules drive the whole design:

1. **A table never becomes a chunk of its own.** It stays with the heading and
   the prose of its section — the numbers in a fee/limit table are meaningless
   without them, and a chunk of bare digits embeds terribly.
2. **A section is only split when it would be truncated by the embedding model**
   (see ``MAX_CHUNK_CHARS``), and even then only at safe boundaries: blank lines
   between blocks, or whole table rows with the header repeated.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterator

from src.ingestion import ingest_all

logger = logging.getLogger(__name__)

# Ngân sách kích thước của TOÀN BỘ nội dung một chunk — gồm cả context header
# lẫn dòng heading. Model paraphrase-multilingual-MiniLM-L12-v2 chạy ở
# max_seq_length = 512 token và cắt âm thầm phần vượt quá; đo trên KB này thì
# văn xuôi ~3.4 ký tự/token còn bảng dày đặc nhất (sheet phí của FEE-001) chỉ
# 2.44 ký tự/token, nên 1200 ký tự ~ 492 token, vừa đủ nằm dưới ngưỡng.
# Ngân sách PHẢI tính cả context header: bỏ sót nó là đúng cách FEE-001 lọt lên
# 525 token và mất mấy dòng phí cuối bảng.
# Hàng rào thật sự nằm ở test_embedding.py, chỗ đếm token bằng chính tokenizer.
MAX_CHUNK_CHARS = 1200

# Khi phải cắt nhỏ, phát ra chunk ngay khi gom đủ ngần này ký tự thay vì nhồi
# cho đầy MAX_CHUNK_CHARS. Nhờ vậy mỗi cặp Q&A trong FAQ thành một chunk riêng,
# thay vì 8 câu hỏi không liên quan bị dồn chung một chunk.
MIN_BODY_CHARS = 200

_HEADING_RE = re.compile(r"^(#{1,2}) +(.*\S)\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_TABLE_SEPARATOR_RE = re.compile(r"^\|[\s\-:|]+\|$")


# --------------------------------------------------------------------------- #
# Section splitting
# --------------------------------------------------------------------------- #
class _Section:
    """One H1/H2 section: its heading line, its body, and its heading path."""

    def __init__(self, heading: str, heading_path: str, heading_line: str) -> None:
        self.heading = heading
        self.heading_path = heading_path
        self.heading_line = heading_line
        self.lines: list[str] = []

    @property
    def body(self) -> str:
        return "\n".join(self.lines).strip()

    @property
    def text(self) -> str:
        """Full section text — heading line included, so BM25 can match on it."""
        if not self.heading_line:
            return self.body
        return f"{self.heading_line}\n\n{self.body}" if self.body else self.heading_line


def split_sections(content: str) -> list[_Section]:
    """Split Markdown into H1/H2 sections, keeping H3+ inside their parent.

    Bỏ qua heading nằm trong code fence — KB hiện tại không có, nhưng đây là cái
    bẫy rẻ tiền nên chặn trước.
    """
    sections: list[_Section] = []
    current = _Section(heading="", heading_path="", heading_line="")
    current_h1 = ""
    in_fence = False

    for line in content.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence

        match = None if in_fence else _HEADING_RE.match(line)
        if match is None:
            current.lines.append(line)
            continue

        level, heading = len(match.group(1)), match.group(2)
        if level == 1:
            current_h1 = heading
            heading_path = heading
        else:
            heading_path = f"{current_h1} > {heading}" if current_h1 else heading

        sections.append(current)
        current = _Section(heading, heading_path, line)

    sections.append(current)

    # Section có thân rỗng (VD `# 2. Phạm vi` rồi ngay sau là `## Trong phạm vi`
    # trong cả 4 file BRD) chỉ đóng vai trò nhóm — không sinh chunk, heading của
    # nó vẫn đi vào heading_path của các section con.
    return [s for s in sections if s.body]


# --------------------------------------------------------------------------- #
# Block / table helpers
# --------------------------------------------------------------------------- #
def _split_blocks(body: str) -> list[str]:
    """Split a section body into blocks separated by blank lines."""
    return [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]


def is_table_block(block: str) -> bool:
    """True if ``block`` is a GitHub-flavoured Markdown table (header + separator)."""
    lines = block.splitlines()
    return (
        len(lines) >= 2
        and lines[0].lstrip().startswith("|")
        and bool(_TABLE_SEPARATOR_RE.match(lines[1].strip()))
    )


def contains_table(text: str) -> bool:
    """True if ``text`` holds at least one Markdown table."""
    return any(is_table_block(block) for block in _split_blocks(text))


def _split_table_block(block: str, budget: int) -> Iterator[str]:
    """Split an oversized table into row groups, repeating the header each time.

    Không bao giờ cắt giữa một dòng: đơn vị nhỏ nhất là một dòng bảng nguyên vẹn.
    Chỉ GL-001 (16 thuật ngữ) và sheet SLA_Xu_Ly của LIMIT-001 rơi vào nhánh này.
    """
    lines = block.splitlines()
    prefix = f"{lines[0]}\n{lines[1]}"
    rows = lines[2:]

    group: list[str] = []
    size = len(prefix)
    for row in rows:
        if group and size + len(row) + 1 > budget:
            yield "\n".join([prefix, *group])
            group, size = [], len(prefix)
        group.append(row)
        size += len(row) + 1

    if group:
        yield "\n".join([prefix, *group])


def _pack_blocks(blocks: list[str], budget: int) -> Iterator[str]:
    """Group blocks into part bodies that each fit within ``budget``."""
    group: list[str] = []
    size = 0

    def flush() -> Iterator[str]:
        nonlocal group, size
        if group:
            yield "\n\n".join(group)
            group, size = [], 0

    for block in blocks:
        if len(block) > budget:
            yield from flush()
            if is_table_block(block):
                yield from _split_table_block(block, budget)
            else:
                # Đoạn văn đơn lẻ dài quá ngưỡng: cắt ở đây chỉ tổ làm hỏng nghĩa,
                # thà để nguyên và ghi log. KB hiện tại không có trường hợp này.
                logger.warning(
                    "Khối văn bản %d ký tự vượt ngân sách %d, giữ nguyên: %.60s...",
                    len(block),
                    budget,
                    block,
                )
                yield block
            continue

        if group and size + len(block) + 2 > budget:
            yield from flush()

        group.append(block)
        size += len(block) + 2

        if size >= MIN_BODY_CHARS:
            yield from flush()

    yield from flush()


# --------------------------------------------------------------------------- #
# Context header
# --------------------------------------------------------------------------- #
def _document_title(doc: dict[str, Any]) -> str:
    """Best available human title for a document.

    16 file `.md` có `title` trong front-matter; 2 `.docx` và 2 `.xlsx` thì không
    nên phải lần ra từ nội dung: docx mở đầu bằng H1 là tên quy trình, còn xlsx
    mở đầu mỗi sheet bằng một dòng tiêu đề in hoa.
    """
    title = doc["metadata"].get("title")
    if title:
        return str(title)

    lines = [line.strip() for line in doc["content"].splitlines() if line.strip()]
    for line in lines:
        if line.startswith("# "):
            return line[2:].strip()
    for line in lines:
        if not line.startswith(("#", "|", "**", "-")):
            return line

    return doc["doc_id"]


def _context_header(
    title: str, metadata: dict[str, Any], heading_path: str, part: int, n_parts: int
) -> str:
    """Build the provenance header prepended to every chunk before embedding.

    Chunk bảng và chunk Q&A lẻ nếu đứng một mình thì mất hết ngữ cảnh; header này
    làm chúng tự mang đủ thông tin, và giúp LLM trích dẫn đúng tài liệu.
    """
    doc_id = metadata.get("doc_id", "")
    parts = [p for p in (doc_id, metadata.get("doc_type")) if p]
    if metadata.get("module"):
        parts.append(f"module {metadata['module']}")
    if metadata.get("version"):
        parts.append(f"v{metadata['version']}")

    lines = [f"Tài liệu: {title} ({', '.join(parts)})"]
    if heading_path:
        suffix = f" (phần {part}/{n_parts})" if n_parts > 1 else ""
        lines.append(f"Mục: {heading_path}{suffix}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #
def chunk_document(
    doc: dict[str, Any], max_chars: int = MAX_CHUNK_CHARS
) -> list[dict[str, Any]]:
    """Chunk one ingested document into structure-aware chunks."""
    doc_id = doc["doc_id"]
    title = _document_title(doc)
    chunks: list[dict[str, Any]] = []

    for section in split_sections(doc["content"]):
        # Context header được nối vào đầu mọi chunk nên phải trừ khỏi ngân sách,
        # cộng thêm chỗ cho hậu tố " (phần 10/10)" nếu section bị cắt.
        header = _context_header(title, doc["metadata"], section.heading_path, 1, 1)
        budget = max(max_chars - len(header) - 16, MIN_BODY_CHARS)

        if len(section.text) <= budget:
            texts = [section.text]
        else:
            # Mỗi phần lặp lại dòng heading nên phải trừ nó ra khỏi ngân sách.
            body_budget = max(budget - len(section.heading_line) - 2, MIN_BODY_CHARS)
            bodies = list(_pack_blocks(_split_blocks(section.body), body_budget))
            texts = [
                f"{section.heading_line}\n\n{body}" if section.heading_line else body
                for body in bodies
            ]

        for part, text in enumerate(texts, start=1):
            index = len(chunks)
            chunk_id = f"{doc_id}#{index:03d}"
            part_header = _context_header(
                title, doc["metadata"], section.heading_path, part, len(texts)
            )
            content = f"{part_header}\n\n{text}"

            metadata = dict(doc["metadata"])
            metadata.update(
                chunk_id=chunk_id,
                chunk_index=index,
                heading=section.heading,
                heading_path=section.heading_path,
                has_table=contains_table(text),
                chunk_char_count=len(content),
                part=part,
                n_parts=len(texts),
            )
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "content": content,
                    "doc_id": doc_id,
                    "metadata": metadata,
                }
            )

    if not chunks:
        raise ValueError(f"[{doc_id}] không cắt ra được chunk nào")

    return chunks


def chunk_documents(
    docs: list[dict[str, Any]], max_chars: int = MAX_CHUNK_CHARS
) -> list[dict[str, Any]]:
    """Chunk every ingested document."""
    chunks = [chunk for doc in docs for chunk in chunk_document(doc, max_chars)]
    logger.info("Đã cắt %d tài liệu thành %d chunk", len(docs), len(chunks))
    return chunks


if __name__ == "__main__":
    import statistics
    import sys
    from collections import Counter

    # Console Windows mặc định là cp1252, không in được tiếng Việt.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    all_chunks = chunk_documents(ingest_all())
    per_doc = Counter(chunk["doc_id"] for chunk in all_chunks)
    sizes = [chunk["metadata"]["chunk_char_count"] for chunk in all_chunks]

    print(f"\n{'doc_id':<14}{'chunks':>8}{'có bảng':>10}{'bị cắt':>9}{'max ký tự':>11}")
    print("-" * 52)
    for doc_id in per_doc:
        owned = [c for c in all_chunks if c["doc_id"] == doc_id]
        print(
            f"{doc_id:<14}{len(owned):>8}"
            f"{sum(1 for c in owned if c['metadata']['has_table']):>10}"
            f"{sum(1 for c in owned if c['metadata']['n_parts'] > 1):>9}"
            f"{max(c['metadata']['chunk_char_count'] for c in owned):>11}"
        )
    print("-" * 52)
    print(
        f"Tổng: {len(all_chunks)} chunk | ký tự min/trung vị/max = "
        f"{min(sizes)}/{int(statistics.median(sizes))}/{max(sizes)} | "
        f"{sum(1 for c in all_chunks if c['metadata']['has_table'])} chunk có bảng"
    )

    # Kiểm chứng bằng mắt: bảng hạn mức Tier của BR-002 phải nằm trọn 1 chunk,
    # kèm heading (ngày hiệu lực) và đoạn lưu ý về quy tắc cộng dồn.
    print("\n" + "=" * 52)
    print("CHUNK CHỨA BẢNG HẠN MỨC TIER (BR-002)")
    print("=" * 52)
    for chunk in all_chunks:
        if chunk["doc_id"] == "BR-002" and "| Nạp tiền |" in chunk["content"]:
            print(chunk["content"])
