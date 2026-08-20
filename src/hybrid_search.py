"""Hybrid retrieval: dense vector similarity + BM25, over a metadata-filtered pool.

Lý do tồn tại, đo được: query "hạn mức chuyển tiền P2P Tier 2" chạy vector thuần
trả về top-3 toàn BRD-002 (0.628 / 0.598 / 0.594), còn đáp án thật —
20.000.000 VNĐ trong BR-002 — không lọt top-3. BRD-002 nói VỀ chuyển tiền P2P
nên gần query về ngữ nghĩa; BR-002 CHỨA con số. Embedding không phân biệt được
hai thứ đó, BM25 thì có.

Thứ tự bắt buộc: lọc metadata TRƯỚC, chấm điểm SAU. Xem :func:`_normalize_scores`
để biết vì sao thứ tự này không phải chuyện tối ưu tốc độ mà là chuyện đúng/sai.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src import bm25_retriever
from src.embedding import encode
from src.vectorstore import CHROMA_DIR, _build_where, get_collection

logger = logging.getLogger(__name__)

# Mặc định chỉ chặn tài liệu HẾT HIỆU LỰC, không phải "chỉ giữ Approved".
# Catalog có 4 status: Approved (16 doc), In Progress (2: US-EPIC-014/021),
# Closed (1: INC-001), Deprecated (1: BR-002-v1). Lọc cứng status == "Approved"
# sẽ khóa vĩnh viễn UserStory và IncidentReport khỏi mọi truy vấn — hỏng các câu
# Q010/Q012/Q020 trong bộ evaluation. Thứ nhóm version_conflict cần chặn là
# BR-002-v1, và chỉ nó mới là Deprecated.
DEFAULT_STATUS_FILTER = {"$nin": ["Deprecated"]}

DEFAULT_ALPHA = 0.5


# --------------------------------------------------------------------------- #
# Filter
# --------------------------------------------------------------------------- #
def _resolve_filters(
    filters: dict[str, Any] | None, include_deprecated: bool
) -> dict[str, Any] | None:
    """Merge the caller's filters with the default "hide deprecated docs" clause.

    Ba đường đi, theo thứ tự ưu tiên:

    * ``include_deprecated=True`` -> KHÔNG áp mệnh đề status nào. Dành cho câu
      hỏi lịch sử (Q028: "trước đây hạn mức Tier 3 là bao nhiêu"), ở đó bản
      Deprecated LẠI là nguồn hợp lệ.
    * caller tự truyền khóa ``status`` -> dùng nguyên, không đụng vào. Đây là
      cách ép về strict ``{"status": "Approved"}`` khi cần.
    * còn lại -> chèn :data:`DEFAULT_STATUS_FILTER`.

    ``module`` / ``doc_type`` caller truyền vào luôn được giữ nguyên.
    """
    resolved = dict(filters or {})
    if include_deprecated:
        return resolved or None
    resolved.setdefault("status", DEFAULT_STATUS_FILTER)
    return resolved


# --------------------------------------------------------------------------- #
# Chuẩn hóa & hợp nhất điểm
# --------------------------------------------------------------------------- #
def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Min-max BM25 scores into 0..1 — the pool passed in must be pre-filtered.

    Hai nhánh cho ra hai loại điểm KHÁC THANG ĐO, không cộng thẳng được:

    ============ ================== =============================================
    Nhánh        Thang              Bản chất
    ============ ================== =============================================
    vector       cố định **0..1**   ``1 - cosine_distance``; vector đã L2-normalize
                                    và collection dùng không gian cosine, nên đây
                                    đúng là cosine similarity.
    BM25         **mở**, không trần tổng ``IDF × TF`` đã bão hòa. Phụ thuộc số từ
                                    trong query, độ hiếm của token và kích thước
                                    corpus. Query 2 từ ra ~3, query 8 từ ra ~25.
    ============ ================== =============================================

    Cộng thẳng thì BM25 nuốt trọn nhánh vector. Nên min-max riêng nhánh BM25 về
    0..1 rồi mới cộng có trọng số.

    CHỈ chuẩn hóa BM25, GIỮ NGUYÊN cosine. Cosine vốn đã ở thang cố định có nghĩa
    tuyệt đối; min-max nó nữa sẽ (a) hủy tín hiệu mà bước generation cần để TỪ
    CHỐI trả lời câu adversarial, và (b) khiến chunk tốt-nhất-trong-đám-tệ luôn
    được 1.0, trông như hoàn hảo.

    Vì sao pool phải lọc TRƯỚC: min-max phụ thuộc ``max`` và ``min`` của pool.
    Nếu một chunk BR-002-v1 điểm cao còn nằm trong pool lúc tính ``max`` rồi mới
    bị loại khỏi kết quả, nó đã kịp nén điểm chuẩn hóa của mọi chunk còn lại
    xuống thấp và làm lệch toàn bộ fusion. Lọc trước không phải để chạy nhanh hơn.

    Biên: ``max == min`` (query không có token nào trong corpus, hoặc pool chỉ có
    1 ứng viên) -> trả 0.0 hết, tránh chia cho 0. Đúng về nghĩa: không có tín
    hiệu từ vựng nào để phân biệt thì nhánh từ vựng không được đóng góp gì, xếp
    hạng tự lùi về thuần vector.
    """
    if not scores:
        return {}

    lowest = min(scores.values())
    highest = max(scores.values())
    span = highest - lowest
    if span <= 0.0:
        return {chunk_id: 0.0 for chunk_id in scores}
    return {chunk_id: (score - lowest) / span for chunk_id, score in scores.items()}


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
def hybrid_search(
    text: str,
    filters: dict[str, Any] | None = None,
    top_k: int = 5,
    alpha: float = DEFAULT_ALPHA,
    include_deprecated: bool = False,
    persist_dir: Path | str = CHROMA_DIR,
) -> list[dict[str, Any]]:
    """Search with vector + BM25 fused, best first.

    ``score = alpha * vector_score + (1 - alpha) * bm25_score_norm``

    Mỗi hit là dict gồm ``chunk_id``, ``content``, ``metadata``, ``score``, kèm
    ``vector_score`` (cosine thô) và ``bm25_score`` (BM25 thô) để soi được vì sao
    một chunk lên hạng, và để bước generation còn ngưỡng tuyệt đối mà từ chối
    câu hỏi ngoài phạm vi KB.

    ``alpha=1.0`` là vector thuần, ``alpha=0.0`` là BM25 thuần.
    """
    collection = get_collection(persist_dir)
    where = _build_where(_resolve_filters(filters, include_deprecated))

    # Tập ứng viên hợp lệ, xác định TRƯỚC khi bất kỳ điểm nào được tính.
    allowed_ids = set(collection.get(where=where, include=[])["ids"])
    if not allowed_ids:
        return []

    # Corpus chỉ ~127 chunk nên chấm điểm TOÀN BỘ tập đã lọc ở cả hai nhánh, không
    # cắt candidate pool. Cắt pool là chỗ hybrid search hay sai nhất: khi một chunk
    # chỉ nằm trong top-N của một nhánh, người ta gán 0 cho nhánh còn lại — mà 0 là
    # một GIẢ ĐỊNH, không phải điểm thật, và nó phạt oan đúng những chunk mà hybrid
    # sinh ra để cứu. Khi KB lớn lên thì thêm candidate_k; giờ chưa cần.
    pool_size = len(allowed_ids)

    result = collection.query(
        query_embeddings=[encode(text)],
        n_results=pool_size,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    ids = result["ids"][0]
    if len(ids) < pool_size:
        # HNSW là tìm kiếm XẤP XỈ: nó có thể trả về ít hơn n_results dù pool còn
        # dư. Chunk rơi ra ở đây sẽ mất luôn khỏi bảng xếp hạng hybrid kể cả khi
        # BM25 chấm nó cao — đúng loại chunk mà bước này sinh ra để cứu. Ở KB
        # 127 chunk chưa bao giờ xảy ra; kêu to nếu nó bắt đầu xảy ra.
        logger.warning(
            "Nhánh vector chỉ trả %d/%d chunk trong pool — %d chunk không được "
            "chấm điểm vector và có thể bị rớt oan khỏi kết quả hybrid.",
            len(ids),
            pool_size,
            pool_size - len(ids),
        )

    vector_scores = {
        chunk_id: 1.0 - result["distances"][0][rank] for rank, chunk_id in enumerate(ids)
    }
    contents = {chunk_id: result["documents"][0][rank] for rank, chunk_id in enumerate(ids)}
    metadatas = {chunk_id: result["metadatas"][0][rank] for rank, chunk_id in enumerate(ids)}

    bm25_scores = dict(
        bm25_retriever.search(
            text, top_k=pool_size, persist_dir=persist_dir, allowed_ids=allowed_ids
        )
    )
    bm25_norm = _normalize_scores(bm25_scores)

    hits = [
        {
            "chunk_id": chunk_id,
            "content": contents[chunk_id],
            "metadata": metadatas[chunk_id],
            "score": alpha * vector_scores[chunk_id] + (1.0 - alpha) * bm25_norm.get(chunk_id, 0.0),
            "vector_score": vector_scores[chunk_id],
            "bm25_score": bm25_scores.get(chunk_id, 0.0),
        }
        for chunk_id in ids
    ]
    hits.sort(key=lambda hit: hit["score"], reverse=True)
    return hits[:top_k]


if __name__ == "__main__":
    import json
    import sys

    from src.vectorstore import PROJECT_ROOT, build_index, query

    # Console Windows mặc định là cp1252, không in được tiếng Việt.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    count = build_index()
    bm25_retriever.get_index(refresh=True)  # collection vừa bị ghi lại
    print(f"\n{'=' * 78}\nĐã index {count} chunk\n{'=' * 78}")

    def doc_ids(hits: list[dict[str, Any]]) -> list[str]:
        seen: list[str] = []
        for hit in hits:
            if hit["metadata"]["doc_id"] not in seen:
                seen.append(hit["metadata"]["doc_id"])
        return seen

    # ---- Câu hỏi đã chứng minh vector thuần thất bại ---------------------- #
    q = "Hạn mức chuyển tiền P2P mỗi ngày của tài khoản Tier 2 là bao nhiêu?"
    print(f"\n### {q}\n### Đáp án đúng: 20.000.000 VNĐ, nguồn BR-002\n{'-' * 78}")

    print("\n[TRƯỚC] vector-only:")
    for rank, hit in enumerate(query(q, top_k=3), start=1):
        print(f"  {rank}. {hit['score']:.3f}  {hit['metadata']['doc_id']}")

    print("\n[SAU] hybrid:")
    for rank, hit in enumerate(hybrid_search(q, top_k=3), start=1):
        print(
            f"  {rank}. {hit['score']:.3f}  {hit['metadata']['doc_id']:<12}"
            f"(vector {hit['vector_score']:.3f} | bm25 {hit['bm25_score']:6.2f})"
        )

    # ---- Recall@3 trên toàn bộ bộ đánh giá -------------------------------- #
    eval_path = PROJECT_ROOT / "data" / "Evaluation" / "evaluation_questions.json"
    questions = json.loads(eval_path.read_text(encoding="utf-8"))["questions"]

    print(f"\n\n{'=' * 78}\nRecall@3 theo nhóm — vector-only vs hybrid\n{'=' * 78}")
    print(f"{'nhóm':<18}{'n':>4}{'vector':>10}{'hybrid':>10}")
    print("-" * 78)

    totals = {"vector": 0, "hybrid": 0, "n": 0}
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in questions:
        groups.setdefault(item["group"], []).append(item)

    for group, items in groups.items():
        # Câu adversarial không có nguồn đúng nào — recall không đo được, bỏ qua.
        scored = [item for item in items if item["expected_source_docs"]]
        if not scored:
            print(f"{group:<18}{len(items):>4}{'—':>10}{'—':>10}  (không có nguồn đúng)")
            continue

        hit_v = hit_h = 0
        for item in scored:
            expected = set(item["expected_source_docs"])
            history = group == "version_conflict" and not item.get("must_not_use_docs")
            hit_v += bool(expected & set(doc_ids(query(item["question"], top_k=3))))
            hit_h += bool(
                expected
                & set(
                    doc_ids(
                        hybrid_search(
                            item["question"], top_k=3, include_deprecated=history
                        )
                    )
                )
            )

        totals["vector"] += hit_v
        totals["hybrid"] += hit_h
        totals["n"] += len(scored)
        print(
            f"{group:<18}{len(scored):>4}"
            f"{hit_v / len(scored):>9.0%}{hit_h / len(scored):>10.0%}"
        )

    print("-" * 78)
    print(
        f"{'TỔNG':<18}{totals['n']:>4}"
        f"{totals['vector'] / totals['n']:>9.0%}{totals['hybrid'] / totals['n']:>10.0%}"
    )
