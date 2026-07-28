"""Tests for src/embedding.py.

Đánh dấu `slow` vì phải nạp model ~470MB. Test quan trọng nhất ở đây là
:func:`test_no_chunk_is_truncated` — nó nối chunking với model và là hàng rào
thật sự chống lỗi cắt cụt âm thầm; MAX_CHUNK_CHARS chỉ là xấp xỉ theo ký tự.
"""

import pytest

from src.chunking import chunk_documents
from src.embedding import (
    EMBEDDING_DIM,
    MAX_SEQ_LENGTH,
    count_tokens,
    embedding_dim,
    encode,
    encode_batch,
    get_model,
)
from src.ingestion import ingest_all

pytestmark = pytest.mark.slow


def cosine(a, b):
    """Vector đã chuẩn hóa nên cosine chính là tích vô hướng."""
    return sum(x * y for x, y in zip(a, b))


@pytest.fixture(scope="module")
def chunks():
    return chunk_documents(ingest_all())


# --------------------------------------------------------------------------- #
# Cấu hình model
# --------------------------------------------------------------------------- #
def test_max_seq_length_is_raised_to_512():
    """Mặc định của model là 128 và phần vượt bị cắt âm thầm, không báo lỗi.

    Để nguyên 128 thì bảng hạn mức BR-002 (266 token) mất sạch cột Tier 2/Tier 3.
    """
    assert get_model().max_seq_length == MAX_SEQ_LENGTH == 512


def test_embedding_dimension():
    assert embedding_dim() == EMBEDDING_DIM == 384
    assert len(encode("kiểm tra số chiều")) == 384


# --------------------------------------------------------------------------- #
# Tính nhất quán
# --------------------------------------------------------------------------- #
def test_vectors_are_normalized():
    for vector in encode_batch(["hạn mức giao dịch", "quy trình đối soát"]):
        assert sum(x * x for x in vector) ** 0.5 == pytest.approx(1.0, abs=1e-5)


def test_encode_matches_encode_batch():
    """Truy vấn và index phải đi qua cùng một đường mã hóa.

    Không so sánh bằng nhau tuyệt đối: trong một lô, câu ngắn bị pad theo câu dài
    nhất nên phép nhân ma trận đổi thứ tự cộng dồn, lệch cỡ 1e-7. Cosine = 1.0.
    """
    text = "Tier 3 rút tiền tối đa bao nhiêu một ngày?"
    single = encode(text)
    batched = encode_batch([text, "một câu khác dài hơn hẳn để ép model phải pad"])[0]

    assert cosine(single, batched) == pytest.approx(1.0, abs=1e-5)


def test_encode_batch_handles_empty_input():
    assert encode_batch([]) == []


def test_returns_plain_python_floats():
    """ChromaDB và JSON đều không thích numpy.float32."""
    vector = encode("kiểm tra kiểu dữ liệu")
    assert isinstance(vector, list)
    assert all(type(x) is float for x in vector)


# --------------------------------------------------------------------------- #
# Chất lượng ngữ nghĩa
# --------------------------------------------------------------------------- #
def test_related_text_scores_higher_than_unrelated():
    query, related, unrelated = encode_batch(
        [
            "hạn mức giao dịch của tài khoản Tier 3",
            "Tier 3 mỗi ngày được chuyển tối đa bao nhiêu tiền?",
            "quy trình đối soát dữ liệu cuối ngày với ngân hàng",
        ]
    )
    assert cosine(query, related) > cosine(query, unrelated)


# --------------------------------------------------------------------------- #
# Hàng rào chống cắt cụt
# --------------------------------------------------------------------------- #
def test_no_chunk_is_truncated(chunks):
    """KHÔNG chunk nào được vượt 512 token — nếu vượt là mất nội dung vĩnh viễn.

    Đây là test nối chunking với model. MAX_CHUNK_CHARS chỉ ước lượng theo ký tự;
    mật độ token của bảng dày hơn văn xuôi nhiều nên phải đếm bằng chính tokenizer.
    """
    oversized = [
        (chunk["chunk_id"], count_tokens(chunk["content"]))
        for chunk in chunks
        if count_tokens(chunk["content"]) > MAX_SEQ_LENGTH
    ]
    assert not oversized, f"chunk bị cắt cụt khi encode: {oversized}"


def test_count_tokens_reflects_tokenizer():
    assert count_tokens("") < count_tokens("một câu tiếng Việt dài hơn hẳn câu rỗng")
