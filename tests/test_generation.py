"""Tests for src/generation.py.

Hai câu hỏi được trả lời ở đây, và câu thứ hai mới là lý do module tồn tại:

1. Hệ thống có trích dẫn ĐÚNG doc_id cho câu hỏi hợp lệ không? (nhóm single_source)
2. Hệ thống có TỪ CHỐI thay vì bịa cho câu hỏi bẫy không? (nhóm adversarial)

Phân tầng marker:

* Không marker  — test gate và test trích dẫn. Thuần logic, không gọi API, không nạp
  model. Chạy trong `pytest tests/ -v` bình thường.
* `llm` + `slow` — gọi Claude API THẬT, tốn tiền. pytest.ini đặt `-m "not llm"` nên
  mặc định bị bỏ qua; chạy bằng:

      pytest tests/test_generation.py -m llm -v

Bảng chi phí in ở cuối lần chạy, do hook trong `tests/conftest.py` lo.
"""

import json
import re

import pytest

from src.bm25_retriever import clear_cache, get_index
from src.generation import (
    MIN_TOP_SCORE,
    PRICE_PER_MTOK_IN,
    PRICE_PER_MTOK_OUT,
    REFUSAL_MESSAGE,
    GenerationResult,
    _context_meta,
    _extract_citations,
    generate_answer,
)
from src.vectorstore import PROJECT_ROOT, build_index

EVAL_PATH = PROJECT_ROOT / "data" / "Evaluation" / "evaluation_questions.json"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def eval_questions():
    """The evaluation set, keyed by question id."""
    data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    return {item["id"]: item for item in data["questions"]}


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    """Build the index once into a temp directory, with a matching BM25 index."""
    persist_dir = tmp_path_factory.mktemp("chroma")
    build_index(persist_dir=persist_dir)
    clear_cache()
    get_index(persist_dir, refresh=True)
    return persist_dir


@pytest.fixture
def answer(index, cost_log):
    """Call ``generate_answer`` against the temp index, recording what it cost.

    Mọi test gọi API phải đi qua fixture này — nếu gọi thẳng ``generate_answer`` thì
    chi phí của lần gọi đó không vào bảng tổng, và bảng tổng lặng lẽ báo thiếu tiền.
    """

    def run(label: str, question: str, **kwargs) -> GenerationResult:
        result = generate_answer(question, persist_dir=index, **kwargs)
        cost_log.append(
            (
                label,
                result.input_tokens,
                result.output_tokens,
                result.cost_usd,
                result.model_used is None,
            )
        )
        return result

    return run


class ClientWasCalled(Exception):
    """Raised by the stub client so a gate test can prove the LLM was reached."""


def stub_client(calls: list):
    """A `_get_client` replacement that records the call, then refuses to go further.

    Dùng thay vì mock cả `messages.create`: chỉ cần biết gate có thả xuống tầng LLM hay
    không, không cần giả lập nguyên response của API.
    """

    def _get_client():
        calls.append(1)
        raise ClientWasCalled

    return _get_client


def fake_hits(*scores):
    """Minimal hits shaped like ``hybrid_search`` output, for gate tests."""
    return [
        {
            "chunk_id": f"BR-002#{rank:03d}",
            "content": "nội dung giả",
            "metadata": {"doc_id": "BR-002", "status": "Approved", "chunk_id": f"BR-002#{rank:03d}"},
            "score": score,
            "vector_score": score,
            "bm25_score": 1.0,
        }
        for rank, score in enumerate(scores)
    ]


# --------------------------------------------------------------------------- #
# Gate — không gọi API, không nạp model
# --------------------------------------------------------------------------- #
def test_gate_refuses_below_threshold(monkeypatch):
    """Dưới ngưỡng thì từ chối NGAY và tuyệt đối không chạm tới API."""
    calls = []
    monkeypatch.setattr("src.generation.hybrid_search", lambda *a, **k: fake_hits(0.30))
    monkeypatch.setattr("src.generation._get_client", stub_client(calls))

    result = generate_answer("câu hỏi vớ vẩn")

    assert not calls, "Gate đã để lọt xuống LLM — mất tiền oan."

    assert result.answer == REFUSAL_MESSAGE
    assert result.refused
    assert result.cited_doc_ids == []
    # model_used=None là tín hiệu "chưa gọi model nào", khác hẳn "gọi mà tốn 0 token".
    assert result.model_used is None
    assert result.input_tokens == 0 and result.output_tokens == 0
    assert result.cost_usd == 0.0


def test_gate_refuses_when_nothing_retrieved(monkeypatch):
    """Filter không khớp gì -> hits rỗng -> không được IndexError."""
    calls = []
    monkeypatch.setattr("src.generation.hybrid_search", lambda *a, **k: [])
    monkeypatch.setattr("src.generation._get_client", stub_client(calls))

    result = generate_answer("bất kỳ")

    assert not calls
    assert result.answer == REFUSAL_MESSAGE
    assert result.refused and result.model_used is None


def test_gate_boundary_is_strictly_below(monkeypatch):
    """Đúng bằng ngưỡng thì PHẢI lọt qua — biên là `<`, không phải `<=`.

    Không có test này thì đổi `<` thành `<=` sẽ không làm đỏ gì cả, trong khi nó âm
    thầm siết ngưỡng lên và bắt đầu từ chối oan các câu ở sát biên.
    """
    calls = []
    monkeypatch.setattr(
        "src.generation.hybrid_search", lambda *a, **k: fake_hits(MIN_TOP_SCORE)
    )
    monkeypatch.setattr("src.generation._get_client", stub_client(calls))

    with pytest.raises(ClientWasCalled):
        generate_answer("câu hỏi sát biên")
    assert calls, "điểm đúng bằng ngưỡng đã bị chặn oan"


def test_threshold_sits_below_every_valid_question():
    """Chốt con số 0.45.

    Câu hợp lệ có điểm top-1 thấp nhất trong toàn bộ bộ đánh giá là Q005 ("Float
    Balance nghĩa là gì?") = 0.516 — đo trên index thật. Ngưỡng phải nằm DƯỚI mốc đó,
    nếu không là từ chối oan một câu có đáp án trong KB.

    Guard chống việc ai đó nâng ngưỡng lên với hy vọng chặn được câu adversarial: cách
    đó đã đo và không hiệu quả (adversarial nằm 0.593–0.730, chồng lấn hoàn toàn), nó
    chỉ đổi lấy việc giết dần các câu hợp lệ. Xem chú thích ở MIN_TOP_SCORE.
    """
    lowest_valid_top1 = 0.516
    assert MIN_TOP_SCORE < lowest_valid_top1


# --------------------------------------------------------------------------- #
# Trích dẫn — hàm thuần
# --------------------------------------------------------------------------- #
def test_citations_follow_order_of_appearance():
    hits = fake_hits(0.9)
    hits[0]["metadata"]["doc_id"] = "BRD-002"
    hits.append(dict(hits[0], metadata={"doc_id": "BR-002", "status": "Approved"}))

    answer = "Hạn mức là 20.000.000 VNĐ [BR-002], áp dụng theo mô tả nghiệp vụ [BRD-002]."
    assert _extract_citations(answer, hits) == ["BR-002", "BRD-002"]


def test_citation_does_not_match_inside_a_longer_code():
    """BR-002 KHÔNG được khớp vào bên trong BR-002-v1.

    Đây là lỗi im lặng duy nhất mà whitelist không tự bắt được: một câu trả lời trích
    bản Deprecated sẽ bị ghi nhận thành trích bản Approved, và mọi assert về nguồn đúng
    vẫn xanh. Đúng thứ nhóm version_conflict sinh ra để bắt.
    """
    hits = fake_hits(0.9)
    hits[0]["metadata"]["doc_id"] = "BR-002"

    assert _extract_citations("Theo bản cũ [BR-002-v1] thì hạn mức là 50 triệu.", hits) == []


def test_citations_reject_doc_ids_outside_the_context():
    """Mã có dạng tài liệu nhưng không nằm trong context = bịa nguồn, phải bị loại."""
    hits = fake_hits(0.9)  # chỉ có BR-002
    answer = "Quy trình gồm 3 bước [SOP-007] và hạn mức theo [BR-002]."
    assert _extract_citations(answer, hits) == ["BR-002"]


def test_citations_empty_when_answer_cites_nothing():
    assert _extract_citations(REFUSAL_MESSAGE, fake_hits(0.9)) == []


# --------------------------------------------------------------------------- #
# context_meta — provenance đi kèm từng context, cho UI
# --------------------------------------------------------------------------- #
def test_gate_block_leaves_both_context_lists_empty(monkeypatch):
    """Gate chặn -> CẢ contexts lẫn context_meta phải rỗng.

    `src/evaluation.py` dùng `not result.contexts` làm cờ `gate_blocked` và bỏ
    qua mọi chỉ số RAGAS khi cờ bật. Nếu có ai điền context_meta ở nhánh gate
    (hoặc điền contexts) thì cờ đó lệch, và điểm 0.0 "chấm rồi, tệ" sẽ bị ghi
    đè lên None "không chấm được" — sai im lặng trong bảng kết quả.
    """
    monkeypatch.setattr("src.generation.hybrid_search", lambda *a, **k: fake_hits(0.30))
    monkeypatch.setattr("src.generation._get_client", stub_client([]))

    result = generate_answer("câu hỏi vớ vẩn")

    assert result.contexts == []
    assert result.context_meta == []


def test_context_meta_maps_hit_fields_without_requiring_every_key():
    """Lấy đúng doc_id/chunk_id/điểm, và khóa thiếu thì về mặc định chứ không nổ.

    `fake_hits` cố tình KHÔNG có `table_boost` — giống hệt hit do `rerank()` bọc
    lại hay do test dựng tay. Một `KeyError` ở đây sẽ giết cả lượt trả lời SAU
    khi đã trả tiền gọi API, nên phải dùng `.get` toàn bộ.
    """
    meta = _context_meta(fake_hits(0.8)[0])

    assert meta["doc_id"] == "BR-002"
    assert meta["chunk_id"] == "BR-002#000"
    assert meta["status"] == "Approved"
    assert meta["score"] == pytest.approx(0.8)
    assert meta["bm25_score"] == pytest.approx(1.0)
    assert meta["table_boost"] == 0.0  # khóa vắng mặt -> mặc định, không KeyError
    assert meta["rerank_score"] is None  # rerank=False thì không có điểm rerank
    # Trường front-matter chỉ một số tài liệu mới có: vắng thì None, không nổ.
    assert meta["title"] is None


def test_cost_formula():
    result = GenerationResult(answer="x", input_tokens=1000, output_tokens=500)
    expected = (1000 * PRICE_PER_MTOK_IN + 500 * PRICE_PER_MTOK_OUT) / 1_000_000
    assert result.cost_usd == pytest.approx(expected)
    assert result.cost_usd == pytest.approx(0.007)  # $2/$10 -> 0.002 + 0.005


# --------------------------------------------------------------------------- #
# Adversarial — gọi API thật
# --------------------------------------------------------------------------- #
@pytest.mark.llm
@pytest.mark.slow
@pytest.mark.parametrize("qid", ["Q029", "Q030", "Q031", "Q032"])
def test_adversarial_questions_are_refused(answer, eval_questions, qid):
    """4 câu bẫy phải được từ chối, không bịa.

    Lưu ý KHÔNG assert `cited_doc_ids == []`. Với Q032, câu trả lời ĐÚNG lại nên trích
    [SOP-002] để giải thích rằng SOP-007 chỉ được nhắc tới chứ không có nội dung trong
    KB. Ép trích dẫn rỗng là phạt oan đúng hành vi ta muốn.
    """
    item = eval_questions[qid]
    assert item["group"] == "adversarial"
    assert item["expected_source_docs"] == []

    result = answer(f"{qid} adversarial", item["question"])

    assert REFUSAL_MESSAGE in result.answer, (
        f"{qid} KHÔNG từ chối — có nguy cơ bịa. Trả lời: {result.answer!r}"
    )
    assert result.refused
    # Dù từ chối, mã tài liệu nhắc tới vẫn phải là mã có thật trong context.
    assert set(result.cited_doc_ids) <= set(result.retrieved_doc_ids)


@pytest.mark.llm
@pytest.mark.slow
def test_adversarial_interest_rate_invents_no_percentage(answer, eval_questions):
    """Q030 — bẫy dễ khiến LLM bịa con số. Từ chối chung chung là chưa đủ.

    Kiểm thẳng cái sai cụ thể: không được xuất hiện bất kỳ con số phần trăm nào, vì
    ManhPay không có sản phẩm tiền gửi có lãi trong toàn bộ KB.
    """
    result = answer("Q030 lãi suất", eval_questions["Q030"]["question"])

    assert REFUSAL_MESSAGE in result.answer
    percentages = re.findall(r"\d+(?:[.,]\d+)?\s*%", result.answer)
    assert not percentages, f"Q030 bịa ra con số lãi suất {percentages}: {result.answer!r}"


@pytest.mark.llm
@pytest.mark.slow
def test_adversarial_false_premise_invents_no_tier4_limit(answer, eval_questions):
    """Q031 — tiền đề sai (Tier 4 không tồn tại).

    Được phép NHẮC "Tier 4" để nói nó không tồn tại; KHÔNG được phép gán hạn mức cho nó.
    Nên assert vào con số kiểu tiền tệ, không assert vào chuỗi "Tier 4".
    """
    result = answer("Q031 Tier 4", eval_questions["Q031"]["question"])

    assert REFUSAL_MESSAGE in result.answer
    # Câu trả lời từ chối có thể liệt kê Tier 1/2/3 kèm số thật; điều cấm là gán số cho
    # Tier 4 — bắt bằng cách soi câu nào vừa có "Tier 4" vừa có số tiền.
    for sentence in re.split(r"[.;\n]", result.answer):
        if "tier 4" in sentence.lower():
            assert not re.search(r"\d{1,3}(?:\.\d{3}){2,}", sentence), (
                f"Q031 gán hạn mức cho Tier 4: {sentence!r}"
            )


# --------------------------------------------------------------------------- #
# single_source — gọi API thật
# --------------------------------------------------------------------------- #
# Chọn có chủ đích, không phải 5 câu đầu bảng:
#   Q001 — ca vector thuần thất bại mà hybrid cứu được ở Tuần 5 (đáp án ở BR-002)
#   Q002 — nguồn nằm trong .docx, kiểm cả đường ingest Word
#   Q003 — ca sạch, điểm cao (0.850)
#   Q004 — nguồn SOP
#   Q005 — điểm top-1 THẤP NHẤT toàn bộ eval (0.516); bằng chứng gate 0.45 không giết nó
@pytest.mark.llm
@pytest.mark.slow
@pytest.mark.parametrize("qid", ["Q001", "Q002", "Q003", "Q004", "Q005"])
def test_single_source_cites_the_expected_doc(answer, eval_questions, qid):
    item = eval_questions[qid]
    assert item["group"] == "single_source"

    result = answer(f"{qid} single_source", item["question"])

    assert not result.refused, (
        f"{qid} bị từ chối oan dù có đáp án trong KB. Trả lời: {result.answer!r}"
    )
    # Thông báo lỗi in cả hai tầng để biết ngay hỏng ở retrieval hay ở generation.
    assert set(result.cited_doc_ids) & set(item["expected_source_docs"]), (
        f"{qid}: trích {result.cited_doc_ids}, mong đợi {item['expected_source_docs']}; "
        f"truy hồi được {result.retrieved_doc_ids} "
        f"({'nguồn đúng KHÔNG lọt vào context -> lỗi retrieval' if not set(item['expected_source_docs']) & set(result.retrieved_doc_ids) else 'nguồn đúng CÓ trong context -> lỗi generation'})"
    )
    assert set(result.cited_doc_ids) <= set(result.retrieved_doc_ids), (
        f"{qid} trích nguồn ngoài context: "
        f"{set(result.cited_doc_ids) - set(result.retrieved_doc_ids)}"
    )


@pytest.mark.llm
@pytest.mark.slow
@pytest.mark.parametrize(
    ("qid", "needle"),
    [("Q001", "20.000.000"), ("Q002", "85")],
)
def test_single_source_reproduces_the_exact_number(answer, eval_questions, qid, needle):
    """Trích đúng tài liệu chưa đủ — con số phải xuất hiện, nguyên văn định dạng."""
    result = answer(f"{qid} số liệu", eval_questions[qid]["question"])
    assert needle in result.answer, (
        f"{qid} thiếu con số {needle!r} trong câu trả lời: {result.answer!r}"
    )


def test_cost_formula_counts_cache_tokens():
    """Cache tokens are billed but absent from usage.input_tokens.

    Prompt caching từng được bật ở generate_answer rồi gỡ đi: `input_tokens` khi đó
    chỉ còn 2, phần thật (3.067 token) nằm ở cache_creation_input_tokens và KHÔNG
    được tính tiền -> bảng chi phí báo thiếu gần 5 lần. Test này khóa công thức lại
    để nếu ai bật cache trở lại mà quên, con số vẫn đúng.
    """
    result = GenerationResult(
        answer="x", input_tokens=2, cache_creation_tokens=3000, output_tokens=100
    )
    expected = (2 * PRICE_PER_MTOK_IN + 3000 * PRICE_PER_MTOK_IN * 1.25
                + 100 * PRICE_PER_MTOK_OUT) / 1_000_000
    assert result.cost_usd == pytest.approx(expected)
    # Bỏ qua cache thì chỉ ra $0.001 — nhỏ hơn giá thật một bậc độ lớn.
    assert result.cost_usd > 0.008


def test_cache_read_is_cheaper_than_cache_write():
    write = GenerationResult(answer="x", cache_creation_tokens=1000)
    read = GenerationResult(answer="x", cache_read_tokens=1000)
    assert read.cost_usd < write.cost_usd
