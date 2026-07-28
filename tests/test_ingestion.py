"""Tests for src/ingestion.py.

Mỗi test bám vào một cái bẫy cụ thể của bộ dữ liệu (thứ tự bảng trong .docx,
công thức Excel, kiểu datetime.date của YAML...) chứ không chỉ smoke test.
"""

import json

import pytest

from src.ingestion import DEFAULT_CATALOG, ingest_all


@pytest.fixture(scope="module")
def docs():
    """Ingest the knowledge base once for the whole module."""
    return {doc["doc_id"]: doc for doc in ingest_all()}


@pytest.fixture(scope="module")
def catalog():
    with open(DEFAULT_CATALOG, encoding="utf-8") as handle:
        return json.load(handle)


def test_ingest_all_returns_20_docs(docs, catalog):
    assert len(docs) == 20
    assert set(docs) == {entry["doc_id"] for entry in catalog}


def test_metadata_chroma_compatible(docs):
    """ChromaDB chỉ nhận str/int/float/bool — YAML front-matter trả datetime.date."""
    for doc_id, doc in docs.items():
        for key, value in doc["metadata"].items():
            assert isinstance(value, (str, int, float, bool)), (
                f"{doc_id}.{key} có kiểu {type(value).__name__}, ChromaDB sẽ từ chối"
            )


def test_required_metadata_fields_present(docs):
    required = {
        "doc_id",
        "file_path",
        "doc_type",
        "module",
        "version",
        "status",
        "effective_date",
        "owner",
        "file_format",
        "char_count",
    }
    for doc_id, doc in docs.items():
        assert required <= set(doc["metadata"]), f"{doc_id} thiếu trường metadata"


def test_no_empty_content(docs):
    for doc_id, doc in docs.items():
        assert doc["metadata"]["char_count"] > 200, f"{doc_id} có nội dung quá ngắn"
        assert doc["metadata"]["char_count"] == len(doc["content"])


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #
def test_markdown_frontmatter_stripped(docs):
    doc = docs["BRD-001"]
    assert not doc["content"].lstrip().startswith("---")
    assert "doc_id: BRD-001" not in doc["content"]
    assert doc["metadata"]["title"].startswith("Business Requirement Document")


def test_markdown_frontmatter_overrides_catalog(docs):
    """Front-matter sát tài liệu hơn nên thắng catalog khi xung đột."""
    assert docs["US-EPIC-014"]["metadata"]["owner"] == "PO - Nguyen Van A"
    # ...nhưng catalog vẫn bù trường mà front-matter thiếu.
    assert docs["US-EPIC-014"]["metadata"]["effective_date"] == "2026-04-10"


# --------------------------------------------------------------------------- #
# DOCX
# --------------------------------------------------------------------------- #
def test_docx_table_position_preserved(docs):
    """Bảng của SOP-005 phải nằm giữa mục 5 và mục 6, không bị dồn xuống cuối."""
    content = docs["SOP-005"]["content"]
    heading_5 = content.index("# 5. Phân loại chênh lệch")
    heading_6 = content.index("# 6. Nguyên tắc")
    table = content.index("| Loại chênh lệch |")
    assert heading_5 < table < heading_6


def test_docx_table_content(docs):
    content = docs["SOP-005"]["content"]
    assert "| Thiếu ở ManhPay |" in content
    for kind in ("Thiếu ở ManhPay", "Thiếu ở đối tác", "Lệch số tiền", "Trùng lặp"):
        assert kind in content


def test_docx_headings_and_bullets(docs):
    """SOP-002 không có bảng nhưng phải giữ được cấu trúc heading + bullet."""
    content = docs["SOP-002"]["content"]
    assert content.count("\n# ") >= 7
    assert "|---|" not in content
    assert "- Khách hàng vào mục Tài khoản > Xác thực danh tính." in content
    assert "ngưỡng chấp nhận tối thiểu 85%" in content


# --------------------------------------------------------------------------- #
# XLSX
# --------------------------------------------------------------------------- #
def test_xlsx_no_raw_formula(docs):
    for doc_id in ("FEE-001", "LIMIT-001"):
        content = docs[doc_id]["content"]
        assert "=IF(" not in content
        assert "=SUM(" not in content
        assert "=MAX(" not in content


def test_xlsx_percent_rendered(docs):
    """Ô lưu 0.015 với number_format '0.0%' phải hiện thành 1.5%."""
    content = docs["FEE-001"]["content"]
    assert "1.5%" in content
    assert "0.015" not in content
    assert "0.6%" in content  # merchant hạng Kim Cương


def test_xlsx_computed_values_present(docs):
    """Giá trị đã tính của công thức phải có mặt, định dạng nghìn kiểu VN."""
    assert "30.000" in docs["FEE-001"]["content"]  # =IF(...MAX(...))
    assert "400.000.000" in docs["LIMIT-001"]["content"]  # =SUM(G12:G15)


def test_xlsx_all_sheets_present(docs):
    limit = docs["LIMIT-001"]["content"]
    assert "## Sheet: HanMuc_Theo_Tier" in limit
    assert "## Sheet: SLA_Xu_Ly" in limit
    fee = docs["FEE-001"]["content"]
    assert "## Sheet: BangPhi_KhachHang" in fee
    assert "## Sheet: BangPhi_Merchant" in fee


def test_xlsx_table_rows_well_formed(docs):
    """Preamble phải bị tách khỏi bảng, nếu không bảng Markdown sẽ lệch cột."""
    for line in docs["LIMIT-001"]["content"].splitlines():
        if line.startswith("| Nạp tiền |"):
            assert line.count("|") == 8  # 7 cột -> 8 dấu gạch
            break
    else:
        pytest.fail("Không tìm thấy dòng dữ liệu 'Nạp tiền' trong bảng hạn mức")


# --------------------------------------------------------------------------- #
# Deprecated / metadata filter
# --------------------------------------------------------------------------- #
def test_deprecated_doc_ingested_with_status(docs):
    """Bản Deprecated vẫn được nạp — lọc là việc của bước retrieval."""
    meta = docs["BR-002-v1"]["metadata"]
    assert meta["status"] == "Deprecated"
    assert meta["superseded_by"] == "BR-002"
    assert meta["expired_date"] == "2025-06-15"


def test_conflicting_versions_both_ingested(docs):
    """Cặp mâu thuẫn có chủ đích: 100 triệu (Approved) vs 50 triệu (Deprecated)."""
    assert docs["BR-002"]["metadata"]["status"] == "Approved"
    assert "100.000.000" in docs["BR-002"]["content"]
    assert "50.000.000" in docs["BR-002-v1"]["content"]
