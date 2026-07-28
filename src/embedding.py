"""Sentence embeddings for the ManhPay RAG pipeline.

Wraps ``sentence-transformers`` behind two functions, :func:`encode` for a single
text and :func:`encode_batch` for many, both returning plain Python lists so the
vectors drop straight into ChromaDB.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:  # pragma: no cover - chỉ dùng cho type hint
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

# CẢNH BÁO — ĐỪNG XÓA DÒNG NÀY. sentence_bert_config.json của model đặt
# max_seq_length = 128, và phần vượt quá bị CẮT ÂM THẦM, không hề báo lỗi.
# Đo trên KB ManhPay: 33/123 section vượt 128 token, trong đó có chính bảng hạn
# mức của BR-002 (266 token) — để mặc định thì toàn bộ cột Tier 2 và Tier 3
# không lọt vào vector. Backbone là BERT với max_position_embeddings = 512
# (kiểm tra config.json) nên nâng lên 512 là hợp lệ.
MAX_SEQ_LENGTH = 512

_model: "SentenceTransformer | None" = None


def get_model() -> "SentenceTransformer":
    """Return the shared model instance, loading it on first use.

    Nạp lười để ``import src.embedding`` không kéo theo torch + ~470MB trọng số:
    chunking và test của nó phải chạy được mà không đụng tới model.
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Đang nạp model %s...", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        _model.max_seq_length = MAX_SEQ_LENGTH
        logger.info(
            "Đã nạp model: %d chiều, max_seq_length = %d",
            embedding_dim(),
            _model.max_seq_length,
        )
    return _model


def embedding_dim() -> int:
    """Return the model's output dimension.

    sentence-transformers 5.x đổi tên ``get_sentence_embedding_dimension`` thành
    ``get_embedding_dimension``; requirements.txt cho phép >=3.3 nên phải đỡ cả hai.
    """
    model = get_model()
    getter = getattr(model, "get_embedding_dimension", None) or (
        model.get_sentence_embedding_dimension
    )
    return getter()


def count_tokens(text: str) -> int:
    """Count tokens the way the embedding model does, special tokens included."""
    return len(get_model().tokenizer.encode(text))


def encode_batch(
    texts: Sequence[str], batch_size: int = 32, show_progress: bool = False
) -> list[list[float]]:
    """Encode many texts at once — far faster than looping over :func:`encode`."""
    if not texts:
        return []

    truncated = [t for t in texts if count_tokens(t) > MAX_SEQ_LENGTH]
    if truncated:
        # Đúng chế độ hỏng thầm lặng mà cả thiết kế chunking sinh ra để phòng:
        # phần đuôi bị cắt sẽ không bao giờ tìm được bằng vector search.
        logger.warning(
            "%d/%d văn bản vượt %d token và SẼ BỊ CẮT khi encode. "
            "Xem lại MAX_BODY_CHARS trong src/chunking.py.",
            len(truncated),
            len(texts),
            MAX_SEQ_LENGTH,
        )

    vectors = get_model().encode(
        list(texts),
        batch_size=batch_size,
        show_progress_bar=show_progress,
        # Vector đơn vị: cosine similarity trở thành tích vô hướng, và với
        # ChromaDB dùng không gian cosine thì score = 1 - distance.
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vectors.tolist()


def encode(text: str) -> list[float]:
    """Encode one text into a normalised embedding vector.

    Cố tình gọi lại :func:`encode_batch` chứ không tự encode: hai đường đi phải
    cho ra vector y hệt nhau, nếu không thì vector lúc truy vấn lệch khỏi vector
    lúc index — loại lỗi chỉ lộ ra sau khi đã index xong toàn bộ.
    """
    return encode_batch([text])[0]


if __name__ == "__main__":
    import sys

    # Console Windows mặc định là cp1252, không in được tiếng Việt.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # bớt log tải model từ HF

    model = get_model()
    print(f"\nModel            : {MODEL_NAME}")
    print(f"Số chiều         : {embedding_dim()}")
    print(f"max_seq_length   : {model.max_seq_length}  (mặc định của model là 128)")

    query = "hạn mức giao dịch của tài khoản Tier 3"
    related = "Tier 3 mỗi ngày được chuyển tối đa bao nhiêu tiền?"
    unrelated = "quy trình đối soát dữ liệu cuối ngày với ngân hàng"

    q, r, u = encode_batch([query, related, unrelated])
    sim = lambda a, b: sum(x * y for x, y in zip(a, b))  # noqa: E731 - vector đã chuẩn hóa

    print(f"\nCâu truy vấn     : {query}")
    print(f"  ~ liên quan    : {sim(q, r):.4f}  | {related}")
    print(f"  ~ không liên quan: {sim(q, u):.4f}  | {unrelated}")
    # encode() và encode_batch() không cho ra bit y hệt nhau: trong một lô, câu
    # ngắn bị pad theo câu dài nhất nên phép nhân ma trận đổi thứ tự cộng dồn.
    # Sai khác cỡ 1e-7, cosine = 1.0 — không ảnh hưởng gì tới xếp hạng kết quả.
    single = encode(query)
    print(f"\nencode vs encode_batch: sai khác tối đa {max(abs(a - b) for a, b in zip(single, q)):.2e}")
    print(f"Chuẩn vector          : {sum(x * x for x in q) ** 0.5:.6f}")
