"""Tests for the pure helpers in ``app.py`` — no API, no model, no index.

Chỉ import được `app` mà không dựng runtime Streamlit vì toàn bộ phần vẽ giao
diện nằm trong `main()`, gọi dưới `if __name__ == "__main__"`. Streamlit chạy
script với `__name__ == "__main__"` nên UI vẫn hiện bình thường, còn pytest
import với `__name__ == "app"` thì không widget nào được render.
"""

from app import (
    build_filters,
    classify_result,
    format_cost,
    group_contexts_by_doc,
    strip_context_header,
)
from src.generation import REFUSAL_MESSAGE, GenerationResult


def make_meta(doc_id: str, chunk_id: str, score: float, **extra) -> dict:
    """A context_meta entry shaped like src.generation._context_meta output."""
    meta = {
        "doc_id": doc_id,
        "doc_type": "BusinessRules",
        "module": "Han_Muc_Giao_Dich",
        "status": "Approved",
        "version": "3.0",
        "title": None,
        "heading_path": "2. Hạn mức",
        "has_table": True,
        "part": 1,
        "n_parts": 1,
        "chunk_id": chunk_id,
        "score": score,
        "vector_score": score,
        "bm25_score": 1.0,
        "table_boost": 0.0,
        "rerank_score": None,
    }
    meta.update(extra)
    return meta


# --------------------------------------------------------------------------- #
# build_filters
# --------------------------------------------------------------------------- #
def test_build_filters_drops_empty_selections():
    """Không chọn gì -> KHÔNG có khóa, chứ không phải khóa với list rỗng.

    Đây là cái bẫy đang canh: `{"module": {"$in": []}}` làm `allowed_ids` rỗng
    -> hybrid_search trả [] -> gate chặn với điểm 0.0, trông y hệt "câu hỏi
    ngoài phạm vi" trong khi thật ra bộ lọc vừa quét sạch corpus.
    """
    assert build_filters([], []) is None
    assert build_filters(None, None) is None
    assert build_filters(["KYC"], []) == {"module": ["KYC"]}
    assert build_filters([], ["FAQ"]) == {"doc_type": ["FAQ"]}
    assert build_filters(["KYC", "Doi_Soat"], ["SOP"]) == {
        "module": ["KYC", "Doi_Soat"],
        "doc_type": ["SOP"],
    }


def test_build_filters_never_sets_status():
    """Truyền tay khóa `status` sẽ GHI ĐÈ mặc định $nin Deprecated.

    `_resolve_filters` dùng `setdefault`, nên chỉ cần UI lỡ chèn `status` là bản
    Deprecated lọt trở lại vào mọi câu hỏi mà không có lỗi nào báo.
    """
    for filters in (
        build_filters(["KYC"], ["SOP"]),
        build_filters(["KYC"], []),
        build_filters([], ["SOP"]),
    ):
        assert "status" not in filters


# --------------------------------------------------------------------------- #
# classify_result
# --------------------------------------------------------------------------- #
def test_classify_result_separates_the_two_refusals():
    """Hai kiểu từ chối phải ra hai nhãn khác nhau.

    CẢ HAI đều có refused=True, nên ai đó "đơn giản hóa" classify_result thành
    rẽ nhánh theo `refused` sẽ gộp chúng làm một — và UI mất luôn khả năng phân
    biệt "ngoài phạm vi, chưa tốn tiền" với "có tài liệu nhưng không đủ căn cứ".
    Test này là thứ duy nhất đỏ lên khi điều đó xảy ra.
    """
    gate = GenerationResult(answer=REFUSAL_MESSAGE, refused=True)
    assert gate.model_used is None and gate.contexts == []
    assert classify_result(gate) == "gate"

    llm_refusal = GenerationResult(
        answer=f"{REFUSAL_MESSAGE}. Tôi chỉ tìm thấy quy định về Tier 1-3.",
        refused=True,
        model_used="claude-sonnet-5",
        contexts=["nội dung chunk"],
        context_meta=[make_meta("BR-002", "BR-002#000", 0.7)],
    )
    assert classify_result(llm_refusal) == "llm_refusal"

    answered = GenerationResult(
        answer="Hạn mức là 20.000.000 VNĐ [BR-002].",
        refused=False,
        model_used="claude-sonnet-5",
        cited_doc_ids=["BR-002"],
        contexts=["nội dung chunk"],
        context_meta=[make_meta("BR-002", "BR-002#000", 0.8)],
    )
    assert classify_result(answered) == "answer"


def test_format_cost_marks_the_gate_branch_as_a_free_refusal():
    """Gate chặn phải nói rõ "$0 vì chưa gọi API", không chỉ in số 0."""
    gate = GenerationResult(answer=REFUSAL_MESSAGE, refused=True)
    assert "không gọi API" in format_cost(gate)

    answered = GenerationResult(
        answer="x", model_used="claude-sonnet-5", input_tokens=1000, output_tokens=500
    )
    caption = format_cost(answered)
    assert "claude-sonnet-5" in caption
    assert "0.007" in caption  # 1000*$2 + 500*$10 mỗi triệu token


# --------------------------------------------------------------------------- #
# strip_context_header
# --------------------------------------------------------------------------- #
def test_strip_context_header_keeps_body_and_is_safe_without_header():
    """Bóc đúng header, và không cắt gì khi chuỗi không có header.

    Header dùng ở đây là hình dạng thật của BR-002 — tiêu đề có chứa "(Tier)".
    Chính ca này làm vỡ phương án regex bóc doc_id từ dấu ngoặc, và là lý do
    provenance được truyền qua `context_meta` chứ không parse lại từ text.
    """
    text = (
        "Tài liệu: Business Rules - Hạn mức giao dịch theo cấp độ tài khoản (Tier) "
        "(BR-002, BusinessRules, module Han_Muc_Giao_Dich, v3.0)\n"
        "Mục: 2. Hạn mức chuyển tiền P2P\n"
        "\n"
        "| Tier | Hạn mức/ngày |\n| --- | --- |\n| Tier 2 | 20.000.000 VNĐ |"
    )
    body = strip_context_header(text)
    assert body.startswith("| Tier |")
    assert "20.000.000 VNĐ" in body
    assert "Tài liệu:" not in body

    # Không có header -> trả nguyên văn, thà thừa còn hơn cắt mất nội dung.
    plain = "Một đoạn văn bản\n\nkhông có header provenance."
    assert strip_context_header(plain) == plain
    assert strip_context_header("một dòng duy nhất") == "một dòng duy nhất"


# --------------------------------------------------------------------------- #
# group_contexts_by_doc
# --------------------------------------------------------------------------- #
def test_group_contexts_by_doc_orders_cited_first_and_merges_chunks():
    """Gom nhiều chunk cùng doc_id làm một nhóm, nhóm được trích dẫn xếp trước.

    `cited_doc_ids` là TẬP CON của các doc_id đã truy hồi, còn một tài liệu có
    thể đóng góp nhiều chunk — nên zip 1-1 với cited_doc_ids là sai, phải gom.
    """
    result = GenerationResult(
        answer="… [BRD-002] …",
        cited_doc_ids=["BRD-002"],
        model_used="claude-sonnet-5",
        contexts=["chunk BR-002 phần 1", "chunk BRD-002", "chunk BR-002 phần 2"],
        context_meta=[
            make_meta("BR-002", "BR-002#000", 0.90),
            make_meta("BRD-002", "BRD-002#003", 0.60),
            make_meta("BR-002", "BR-002#001", 0.50),
        ],
    )

    groups = group_contexts_by_doc(result)

    assert [entry["doc_id"] for entry in groups] == ["BRD-002", "BR-002"]

    cited = groups[0]
    assert cited["cited"] is True
    assert cited["cite_rank"] == 1
    assert len(cited["chunks"]) == 1

    # Cả hai chunk của BR-002 nằm trong CÙNG một nhóm, best_score là điểm cao nhất.
    uncited = groups[1]
    assert uncited["cited"] is False
    assert uncited["cite_rank"] is None
    assert len(uncited["chunks"]) == 2
    assert uncited["best_score"] == 0.90


def test_group_contexts_by_doc_handles_gate_block():
    """Gate chặn -> hai list rỗng -> không nhóm nào, và không được nổ."""
    gate = GenerationResult(answer=REFUSAL_MESSAGE, refused=True)
    assert group_contexts_by_doc(gate) == []
