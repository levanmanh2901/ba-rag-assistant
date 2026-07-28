"""ChromaDB vector store for the ManhPay knowledge base.

:func:`build_index` runs the whole ingest pipeline end to end — ingestion →
chunking → embedding → persisted ChromaDB collection — and :func:`query` runs a
similarity search with optional metadata filtering.

Filtering matters more than usual here: the knowledge base deliberately contains
BR-002 (``Approved``, hạn mức Tier 3 = 100 triệu) alongside BR-002-v1
(``Deprecated``, 50 triệu). Without ``filters={"status": "Approved"}`` the
retriever happily returns the outdated number.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import chromadb

from src.chunking import chunk_documents
from src.embedding import encode, encode_batch
from src.ingestion import ingest_all

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "manhpay_kb"


# --------------------------------------------------------------------------- #
# Collection
# --------------------------------------------------------------------------- #
def get_collection(
    persist_dir: Path | str = CHROMA_DIR, reset: bool = False
) -> chromadb.Collection:
    """Open (or create) the persistent collection."""
    client = chromadb.PersistentClient(path=str(persist_dir))

    if reset and COLLECTION_NAME in {c.name for c in client.list_collections()}:
        client.delete_collection(COLLECTION_NAME)

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        # Mặc định của Chroma là không gian l2. Vector của ta đã chuẩn hóa nên
        # dùng cosine, khi đó score = 1 - distance chính là cosine similarity.
        configuration={"hnsw": {"space": "cosine"}},
        # BẮT BUỘC. Mặc định là DefaultEmbeddingFunction — nó tải một model ONNX
        # riêng và âm thầm mã hóa câu truy vấn bằng model KHÁC với model đã dùng
        # lúc index, khiến kết quả tìm kiếm sai mà không có lỗi nào được ném ra.
        embedding_function=None,
    )


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def build_index(
    persist_dir: Path | str = CHROMA_DIR,
    rebuild: bool = True,
    batch_size: int = 64,
) -> int:
    """Run ingestion → chunking → embedding → ChromaDB. Returns the chunk count.

    ``rebuild=True`` xóa hẳn collection cũ trước khi ghi: đổi cách chunk mà chỉ
    ghi đè thì các chunk_id của lần build trước sẽ nằm lại thành rác mồ côi.
    """
    chunks = chunk_documents(ingest_all())
    collection = get_collection(persist_dir, reset=rebuild)

    logger.info("Đang mã hóa %d chunk...", len(chunks))
    embeddings = encode_batch([chunk["content"] for chunk in chunks])

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        collection.upsert(
            ids=[chunk["chunk_id"] for chunk in batch],
            embeddings=embeddings[start : start + batch_size],
            documents=[chunk["content"] for chunk in batch],
            metadatas=[chunk["metadata"] for chunk in batch],
        )

    total = collection.count()
    logger.info("Đã lưu %d chunk vào %s", total, persist_dir)
    return total


# --------------------------------------------------------------------------- #
# Query
# --------------------------------------------------------------------------- #
def _build_where(filters: dict[str, Any] | None) -> dict[str, Any] | None:
    """Translate a plain filter dict into ChromaDB ``where`` syntax.

    ``{"status": "Approved"}``            -> ``{"status": {"$eq": "Approved"}}``
    ``{"doc_type": ["BRD", "SOP"]}``      -> ``{"doc_type": {"$in": [...]}}``
    Từ 2 điều kiện trở lên PHẢI bọc trong ``$and`` — Chroma không tự hiểu dict
    nhiều khóa và báo lỗi rất khó lần.
    """
    if not filters:
        return None

    clauses = [
        {key: {"$in": list(value)} if isinstance(value, (list, tuple, set)) else {"$eq": value}}
        for key, value in filters.items()
    ]
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def query(
    text: str,
    filters: dict[str, Any] | None = None,
    top_k: int = 5,
    persist_dir: Path | str = CHROMA_DIR,
) -> list[dict[str, Any]]:
    """Search the index, returning chunks ordered from most to least similar."""
    collection = get_collection(persist_dir)
    result = collection.query(
        query_embeddings=[encode(text)],
        n_results=top_k,
        where=_build_where(filters),
        include=["documents", "metadatas", "distances"],
    )

    ids = result["ids"][0]
    return [
        {
            "chunk_id": chunk_id,
            "content": result["documents"][0][rank],
            "metadata": result["metadatas"][0][rank],
            "distance": result["distances"][0][rank],
            # Vector đã chuẩn hóa + không gian cosine -> đây đúng là cosine similarity.
            "score": 1.0 - result["distances"][0][rank],
        }
        for rank, chunk_id in enumerate(ids)
    ]


if __name__ == "__main__":
    import sys

    # Console Windows mặc định là cp1252, không in được tiếng Việt.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    def show(title: str, hits: list[dict[str, Any]]) -> None:
        print(f"\n{title}")
        print("-" * 78)
        for hit in hits:
            meta = hit["metadata"]
            print(
                f"  {hit['score']:.3f}  {meta['doc_id']:<11} {meta['status']:<11}"
                f"{meta['heading_path'][:42]}"
            )

    count = build_index()
    print(f"\n{'=' * 78}\nĐã index {count} chunk\n{'=' * 78}")

    q1 = "Hạn mức chuyển tiền một ngày của tài khoản Tier 3 là bao nhiêu?"
    print(f"\n### Câu hỏi: {q1}")
    show("[1] KHÔNG lọc metadata — bản Deprecated lọt vào, câu trả lời sẽ sai:", query(q1))
    show(
        "[2] Lọc status = Approved — chỉ còn tài liệu còn hiệu lực:",
        query(q1, filters={"status": "Approved"}),
    )

    q2 = "Phí nạp tiền qua thẻ quốc tế Visa là bao nhiêu?"
    print(f"\n### Câu hỏi: {q2}")
    show("[3] Số liệu nằm trong bảng Excel:", query(q2, filters={"status": "Approved"}))

    q3 = "ManhPay có hỗ trợ mua vé máy bay không?"
    print(f"\n### Câu hỏi (adversarial, KB không có đáp án): {q3}")
    show("[4] Score thấp -> bước generation nên từ chối trả lời:", query(q3, top_k=3))
