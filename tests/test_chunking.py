"""Tests for src/chunking.py.

Trọng tâm là các bảng nghiệp vụ: mỗi test bám vào một bảng cụ thể phải còn
nguyên vẹn trong đúng một chunk, kèm heading và đoạn văn giải thích của nó.
Không cần model nên chạy dưới 1 giây.
"""

import pytest

from src.chunking import (
    MAX_CHUNK_CHARS,
    chunk_documents,
    contains_table,
    is_table_block,
    split_sections,
)
from src.ingestion import ingest_all


@pytest.fixture(scope="module")
def chunks():
    """Chunk the whole knowledge base once for the module."""
    return chunk_documents(ingest_all())


@pytest.fixture(scope="module")
def by_doc(chunks):
    grouped = {}
    for chunk in chunks:
        grouped.setdefault(chunk["doc_id"], []).append(chunk)
    return grouped


def table_chunks(chunks, doc_id, marker):
    """Chunks of ``doc_id`` whose content contains ``marker``."""
    return [c for c in chunks if c["doc_id"] == doc_id and marker in c["content"]]


# --------------------------------------------------------------------------- #
# Hình dạng output
# --------------------------------------------------------------------------- #
def test_every_document_produces_chunks(by_doc):
    assert len(by_doc) == 20


def test_chunk_shape_and_unique_ids(chunks):
    ids = [chunk["chunk_id"] for chunk in chunks]
    assert len(ids) == len(set(ids)), "chunk_id bị trùng -> ChromaDB sẽ ghi đè mất chunk"
    for chunk in chunks:
        assert set(chunk) == {"chunk_id", "content", "doc_id", "metadata"}
        assert chunk["chunk_id"].startswith(chunk["doc_id"] + "#")


def test_metadata_inherits_document_metadata(chunks):
    """Mỗi chunk phải mang đủ metadata tài liệu gốc để filter được về sau."""
    docs = {doc["doc_id"]: doc for doc in ingest_all()}
    for chunk in chunks:
        doc_meta = docs[chunk["doc_id"]]["metadata"]
        for key, value in doc_meta.items():
            if key == "char_count":  # chunk dùng chunk_char_count riêng
                continue
            assert chunk["metadata"][key] == value, f"{chunk['chunk_id']} lệch '{key}'"


def test_chunk_metadata_fields_present(chunks):
    required = {
        "chunk_id",
        "chunk_index",
        "heading",
        "heading_path",
        "has_table",
        "chunk_char_count",
        "part",
        "n_parts",
    }
    for chunk in chunks:
        assert required <= set(chunk["metadata"])
        assert chunk["metadata"]["chunk_char_count"] == len(chunk["content"])


def test_metadata_chroma_compatible(chunks):
    """ChromaDB chỉ nhận str/int/float/bool."""
    for chunk in chunks:
        for key, value in chunk["metadata"].items():
            assert isinstance(value, (str, int, float, bool)), (
                f"{chunk['chunk_id']}.{key} có kiểu {type(value).__name__}"
            )


def test_deprecated_status_propagates_to_every_chunk(by_doc):
    """Bước retrieval lọc theo status ở cấp chunk, nên mọi chunk phải mang status."""
    assert all(c["metadata"]["status"] == "Deprecated" for c in by_doc["BR-002-v1"])
    assert all(c["metadata"]["status"] == "Approved" for c in by_doc["BR-002"])


# --------------------------------------------------------------------------- #
# Kích thước và context header
# --------------------------------------------------------------------------- #
def test_no_chunk_exceeds_budget(chunks):
    for chunk in chunks:
        assert chunk["metadata"]["chunk_char_count"] <= MAX_CHUNK_CHARS, (
            f"{chunk['chunk_id']} vượt ngân sách -> sẽ bị model cắt cụt"
        )


def test_no_heading_only_chunk(chunks):
    """Section rỗng (VD `# 2. Phạm vi` rồi ngay tới `## Trong phạm vi`) bị loại bỏ."""
    for chunk in chunks:
        body = chunk["content"].split("\n\n", 1)[1] if "\n\n" in chunk["content"] else ""
        stripped = "\n".join(
            line for line in body.splitlines() if not line.startswith("#")
        ).strip()
        assert stripped, f"{chunk['chunk_id']} chỉ có heading, không có nội dung"


def test_every_chunk_has_context_header(chunks):
    for chunk in chunks:
        assert chunk["content"].startswith("Tài liệu: ")
        assert chunk["metadata"]["doc_id"] in chunk["content"].splitlines()[0]


def test_context_header_uses_real_title_for_binary_formats(by_doc):
    """docx/xlsx không có front-matter nên title phải lần ra từ nội dung."""
    assert "Quy trình đối soát" in by_doc["SOP-005"][0]["content"].splitlines()[0]
    assert "MA TRẬN HẠN MỨC" in by_doc["LIMIT-001"][0]["content"].splitlines()[0]


def test_split_parts_are_numbered(by_doc):
    """Section bị cắt phải ghi rõ phần mấy trên mấy để LLM biết còn phần khác."""
    split = [c for c in by_doc["GL-001"] if c["metadata"]["n_parts"] > 1]
    assert len(split) >= 2
    assert [c["metadata"]["part"] for c in split] == list(range(1, len(split) + 1))
    assert f"(phần 1/{len(split)})" in split[0]["content"]


# --------------------------------------------------------------------------- #
# Bảng — phần quan trọng nhất
# --------------------------------------------------------------------------- #
def test_br002_tier_table_intact_in_single_chunk(chunks):
    """Test đinh: bảng hạn mức Tier phải nằm trọn 1 chunk cùng heading và lưu ý.

    Đây là chunk phải-đúng của cả đồ án — nhóm câu hỏi version_conflict nhắm
    thẳng vào nó. Tách bảng ra khỏi đoạn "cộng dồn / reset 00:00" thì câu trả lời
    về hạn mức ngày sẽ thiếu quy tắc diễn giải.
    """
    found = table_chunks(chunks, "BR-002", "| Nạp tiền |")
    assert len(found) == 1, "bảng hạn mức Tier bị cắt thành nhiều chunk"
    content = found[0]["content"]

    for row in ("Nạp tiền", "Chuyển tiền P2P", "Thanh toán QR", "Rút tiền về NH"):
        assert f"| {row} |" in content
    for amount in ("5.000.000", "20.000.000", "100.000.000", "50.000.000"):
        assert amount in content
    assert "3. Bảng hạn mức chi tiết" in content, "mất heading mang ngày hiệu lực"
    assert "cộng dồn" in content, "mất đoạn văn giải thích quy tắc /ngày"
    assert found[0]["metadata"]["has_table"] is True


def test_sop005_difference_table_intact(chunks):
    """Bảng phân loại chênh lệch trong .docx — 4 loại phải ở cùng một chunk."""
    found = table_chunks(chunks, "SOP-005", "| Loại chênh lệch |")
    assert len(found) == 1
    for kind in ("Thiếu ở ManhPay", "Thiếu ở đối tác", "Lệch số tiền", "Trùng lặp"):
        assert f"| {kind} |" in found[0]["content"]


def test_limit001_total_row_stays_with_data_rows(chunks):
    """Dòng TỔNG (công thức SUM) vô nghĩa nếu tách khỏi các dòng nó cộng lại."""
    found = table_chunks(chunks, "LIMIT-001", "| Nạp tiền |")
    assert len(found) == 1
    assert "400.000.000" in found[0]["content"]
    assert "TỔNG hạn mức/ngày" in found[0]["content"]


def test_no_chunk_contains_orphan_table_rows(chunks):
    """Chunk nào có dòng dữ liệu bảng thì phải có cả header + dòng phân cách.

    Bắt đúng lỗi cắt giữa bảng: phần sau sẽ toàn dòng `| ... |` mà không ai biết
    cột nào là cột nào.
    """
    for chunk in chunks:
        lines = [l for l in chunk["content"].splitlines() if l.startswith("|")]
        if not lines:
            continue
        assert contains_table(chunk["content"]), (
            f"{chunk['chunk_id']} có dòng bảng mồ côi, thiếu header/phân cách"
        )


def test_oversized_table_repeats_header_in_every_part(by_doc):
    """GL-001 (16 thuật ngữ) buộc phải cắt — mỗi phần vẫn phải tự đọc được."""
    parts = [c for c in by_doc["GL-001"] if c["metadata"]["has_table"]]
    assert len(parts) >= 2
    for part in parts:
        assert "| Thuật ngữ | Định nghĩa |" in part["content"]
    joined = "".join(p["content"] for p in parts)
    for term in ("Idempotency Key", "Chargeback", "Float Balance", "eKYC"):
        assert term in joined, f"mất thuật ngữ '{term}' khi cắt bảng"


def test_has_table_flag_matches_content(chunks):
    for chunk in chunks:
        assert chunk["metadata"]["has_table"] == contains_table(chunk["content"])


# --------------------------------------------------------------------------- #
# FAQ — cắt theo đoạn văn
# --------------------------------------------------------------------------- #
def test_faq_split_into_separate_questions(by_doc):
    """FAQ chỉ có 1 heading H1 cho 8 câu hỏi -> phải cắt theo cặp Q&A."""
    faq = by_doc["FAQ-001"]
    assert len(faq) >= 4, "8 câu hỏi dồn chung quá ít chunk, retrieval sẽ nhiễu"

    q4 = [c for c in faq if "Q4:" in c["content"]]
    assert len(q4) == 1
    # Câu hỏi và câu trả lời của nó không được rơi vào hai chunk khác nhau.
    assert "24 giờ" in q4[0]["content"]


# --------------------------------------------------------------------------- #
# Hàm nội bộ
# --------------------------------------------------------------------------- #
def test_split_sections_skips_headings_inside_code_fence():
    content = "# Thật\n\nnội dung\n\n```\n# Giả trong code fence\n```\n\nsau fence"
    sections = split_sections(content)
    assert len(sections) == 1
    assert sections[0].heading == "Thật"


def test_split_sections_builds_heading_path():
    content = "# 3. Yêu cầu\n\nmở đầu\n\n## 3.1 Hạn mức\n\nchi tiết hạn mức"
    paths = [s.heading_path for s in split_sections(content)]
    assert paths == ["3. Yêu cầu", "3. Yêu cầu > 3.1 Hạn mức"]


def test_is_table_block():
    assert is_table_block("| a | b |\n|---|---|\n| 1 | 2 |")
    assert not is_table_block("| a | b |\n| 1 | 2 |")  # thiếu dòng phân cách
    assert not is_table_block("đoạn văn bình thường")
