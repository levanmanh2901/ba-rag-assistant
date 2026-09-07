"""Cross-encoder reranking over the shortlist that hybrid search produces.

Lý do tồn tại, đo được: hai câu hỏi nhóm ``table_numeric`` vẫn hỏng sau hybrid
search. Q015 (phí thẻ quốc tế, nguồn FEE-001) đứng hạng 5; Q018 (tổng hạn mức
Tier 3, nguồn LIMIT-001) đứng hạng 8 và KHÔNG lọt top-5 context, khiến
:func:`src.generation.generate_answer` từ chối oan một câu hỏi hợp lệ.

Nguyên nhân KHÔNG phải câu hỏi khó, mà là một cái trần có hệ thống.

**Bi-encoder** (``paraphrase-multilingual-MiniLM-L12-v2``, dùng ở
:mod:`src.embedding`) mã hóa câu hỏi và chunk TÁCH RỜI, mỗi bên thành một vector
384 chiều, rồi mới đo cosine. Vector của chunk buộc phải tóm tắt toàn bộ chunk
TRƯỚC KHI biết câu hỏi là gì. Với một bảng số dày đặc — ``| Tier 3 | 100.000.000
| ...`` lặp lại hàng chục dòng gần giống hệt nhau — cái vector duy nhất đó là
trung bình cộng của một khối gần như không có cấu trúc câu, thứ mà model (huấn
luyện trên cặp paraphrase) mới bấu vào được. Biểu diễn bị nhòe và nằm xa mọi
vector câu hỏi. Đo trên KB này: chunk .xlsx có vector_score trung bình 0.163,
cao nhất 0.426; chunk văn xuôi trung bình 0.272, cao nhất 0.706. Đây là THUỘC
TÍNH CỦA CHUNK, không phải của cặp câu hỏi–chunk, nên đổi cách hỏi không cứu
được.

**Cross-encoder** nhận ``[CLS] câu_hỏi [SEP] chunk [SEP]`` như MỘT chuỗi duy
nhất. Mọi lớp self-attention đều cho token của câu hỏi nhìn thẳng vào token của
chunk: "2.000.000" trong câu hỏi attend trực tiếp tới ô "1.5%" và ô "tối thiểu
5.000"; "Tier 3" attend tới đúng dòng Tier 3. Nó KHÔNG CẦN một vector nén đại
diện cho chunk, nên không có nút thắt cổ chai — và do đó không có cái trần phụ
thuộc loại chunk.

Cái giá: không tính trước được bất cứ thứ gì. Bi-encoder encode toàn bộ corpus
một lần lúc index rồi mỗi query chỉ tốn một phép nhân ma trận; cross-encoder
phải chạy một lượt forward CHO MỖI CẶP, mỗi lần hỏi. Vì thế nó chỉ chạy trên
danh sách rút gọn :data:`CANDIDATE_K` ứng viên mà hybrid search đã lọc sẵn,
không bao giờ chạy trên toàn corpus. Đúng phân công: hybrid search lo *recall*
với chi phí gần như bằng không, cross-encoder lo *precision* trên phần còn lại.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.hybrid_search import TABLE_BOOST, hybrid_search
from src.vectorstore import CHROMA_DIR

if TYPE_CHECKING:  # pragma: no cover - chỉ dùng cho type hint
    from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

# Đa ngữ, huấn luyện trên mMARCO (có tiếng Việt), 12 lớp / 384 hidden — nặng
# ngang đúng model embedding đang dùng, nên không làm đổi hạng mục yêu cầu máy.
# Đổi sang BAAI/bge-reranker-v2-m3 sẽ khá hơn về chất lượng nhưng nặng 2.2GB và
# chậm hơn nhiều lần trên CPU; giữ hằng số này để việc thử là đổi một dòng.
RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# Số ứng viên lấy từ hybrid search đưa vào rerank. Độ trễ TUYẾN TÍNH theo con số
# này. 20/127 chunk ≈ 16% corpus, đủ rộng để cứu Q018 (đang hạng 8) mà vẫn rẻ.
CANDIDATE_K = 20

# CẢNH BÁO — ĐỪNG BỎ. Đây đúng cái bẫy đã cắn dự án này một lần ở
# src/embedding.py:21-27: model cắt phần vượt quá ÂM THẦM, không hề báo lỗi.
# Ở đây còn dễ dính hơn vì một "cặp" là câu hỏi CỘNG chunk, mà chunk có thể dài
# tới MAX_CHUNK_CHARS = 1200 ký tự. Nếu bị cắt thì phần đuôi bảng — chỗ hay nằm
# đúng dòng chứa đáp án — không bao giờ được chấm điểm.
MAX_LENGTH = 512

_model: "CrossEncoder | None" = None


def get_reranker() -> "CrossEncoder":
    """Return the shared cross-encoder, loading it on first use.

    Nạp lười theo đúng khuôn :func:`src.embedding.get_model`: ``import
    src.reranking`` không được kéo theo ~470MB trọng số, để test của phần nhận
    diện câu hỏi và của chunking vẫn chạy được trong một giây.
    """
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        logger.info("Đang nạp cross-encoder %s...", RERANKER_MODEL)
        _model = CrossEncoder(RERANKER_MODEL, max_length=MAX_LENGTH)
        logger.info("Đã nạp cross-encoder, max_length = %d", MAX_LENGTH)
    return _model


def _warn_if_truncated(pairs: list[tuple[str, str]]) -> None:
    """Log a warning for pairs the model will silently cut at ``MAX_LENGTH``."""
    tokenizer = get_reranker().tokenizer
    over = sum(
        1
        for question, content in pairs
        if len(tokenizer.encode(question, content)) > MAX_LENGTH
    )
    if over:
        logger.warning(
            "%d/%d cặp vượt %d token và SẼ BỊ CẮT khi rerank — phần đuôi chunk "
            "không được chấm. Xem lại MAX_CHUNK_CHARS trong src/chunking.py.",
            over,
            len(pairs),
            MAX_LENGTH,
        )


def rerank(
    query: str, hits: list[dict[str, Any]], top_k: int = 5
) -> list[dict[str, Any]]:
    """Reorder ``hits`` by cross-encoder relevance, best first, cut to ``top_k``.

    Mỗi hit được thêm ``rerank_score`` (logit thô của model) và ``rerank_rank``
    (hạng 1-based sau khi rerank). ``score`` của hybrid search được GIỮ NGUYÊN,
    không ghi đè — hai lý do:

    * Gate :data:`src.generation.MIN_TOP_SCORE` được hiệu chỉnh trên thang điểm
      hybrid (0..1, có nghĩa tuyệt đối). Logit của cross-encoder không cùng
      thang đó, ghi đè vào là ngưỡng 0.45 mất hết ý nghĩa.
    * Giữ cả hai điểm cạnh nhau thì so sánh trước/sau mới làm được, mà đó chính
      là sản phẩm cần giao của tuần này.

    Dùng logit thô chứ không bọc sigmoid: sigmoid đơn điệu tăng nên KHÔNG đổi
    thứ tự, mà thêm một phép biến đổi nữa chỉ khiến con số khó đối chiếu với
    output gốc của model khi debug.
    """
    if not hits:
        return []

    pairs = [(query, hit["content"]) for hit in hits]
    _warn_if_truncated(pairs)

    scores = get_reranker().predict(pairs)

    ranked = sorted(
        (dict(hit, rerank_score=float(score)) for hit, score in zip(hits, scores)),
        key=lambda hit: hit["rerank_score"],
        reverse=True,
    )
    for rank, hit in enumerate(ranked, start=1):
        hit["rerank_rank"] = rank
    return ranked[:top_k]


def search_and_rerank(
    text: str,
    filters: dict[str, Any] | None = None,
    top_k: int = 5,
    candidate_k: int = CANDIDATE_K,
    include_deprecated: bool = False,
    table_boost: float = TABLE_BOOST,
    persist_dir: Path | str = CHROMA_DIR,
) -> list[dict[str, Any]]:
    """Hybrid search for ``candidate_k`` candidates, then cross-encoder the top ``top_k``."""
    hits = hybrid_search(
        text,
        filters=filters,
        top_k=candidate_k,
        include_deprecated=include_deprecated,
        table_boost=table_boost,
        persist_dir=persist_dir,
    )
    return rerank(text, hits, top_k=top_k)


if __name__ == "__main__":
    import json
    import sys
    import time

    from src import bm25_retriever
    from src.vectorstore import PROJECT_ROOT, build_index

    # Console Windows mặc định là cp1252, không in được tiếng Việt.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    build_index()
    bm25_retriever.get_index(refresh=True)  # collection vừa bị ghi lại

    eval_path = PROJECT_ROOT / "data" / "Evaluation" / "evaluation_questions.json"
    questions = {
        item["id"]: item
        for item in json.loads(eval_path.read_text(encoding="utf-8"))["questions"]
    }

    def doc_rank(hits: list[dict[str, Any]], doc_id: str) -> str:
        seen: list[str] = []
        for hit in hits:
            if hit["metadata"]["doc_id"] not in seen:
                seen.append(hit["metadata"]["doc_id"])
        return str(seen.index(doc_id) + 1) if doc_id in seen else "—"

    # Nạp model trước để không tính giờ khởi động nguội vào độ trễ mỗi câu.
    start = time.perf_counter()
    get_reranker()
    print(f"\nNạp cross-encoder: {time.perf_counter() - start:.2f}s")

    for qid in ("Q015", "Q018"):
        item = questions[qid]
        question, expected = item["question"], item["expected_source_docs"][0]
        print(f"\n{'=' * 78}\n{qid} — {question}\n### Nguồn đúng: {expected}\n{'-' * 78}")

        pool = hybrid_search(question, top_k=CANDIDATE_K, table_boost=0.0)
        print(f"  baseline (không boost, không rerank) : hạng {doc_rank(pool, expected)}")

        boosted = hybrid_search(question, top_k=CANDIDATE_K)
        print(f"  + boost bảng                         : hạng {doc_rank(boosted, expected)}")

        start = time.perf_counter()
        reranked = rerank(question, pool, top_k=CANDIDATE_K)
        elapsed = time.perf_counter() - start
        print(f"  + reranking                          : hạng {doc_rank(reranked, expected)}")

        both = rerank(question, boosted, top_k=CANDIDATE_K)
        print(f"  + cả hai                             : hạng {doc_rank(both, expected)}")
        print(f"\n  Rerank {len(pool)} ứng viên mất {elapsed:.3f}s")
