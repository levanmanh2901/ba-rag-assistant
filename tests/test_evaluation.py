"""Tests for src/evaluation.py — none of these call an API.

Giá trị của file này là CHẶN TIỀN CHẢY RA OAN. Một lượt chạy RAGAS đầy đủ tốn ~$2.3
và mất nhiều phút; ba thứ dưới đây, nếu hỏng, chỉ lộ ra ở giữa lượt chạy đó khi tiền
đã tiêu:

1. ``import ragas`` nổ vì bug vertexai của ragas 0.4.3.
2. Judge gửi ``temperature``/``top_p`` sang Sonnet 5 và ăn 400 ngay câu đầu.
3. Nhóm adversarial bị chấm bằng chỉ số tham chiếu (Context Recall/Precision), ra
   một bảng điểm trông hợp lệ nhưng vô nghĩa.

Cả ba đều kiểm được miễn phí, nên chúng nằm ở đây chứ không nằm sau marker ``llm``.
"""

import warnings

import pytest

from src import evaluation
from src.evaluation import (
    ADVERSARIAL_METRICS,
    FULL_METRICS,
    JUDGE_PROFILE,
    PILOT_IDS,
    UsageMeter,
    _metrics_for,
    _usd,
    _uses_deprecated,
    build_plan,
    estimate_cost,
    load_questions,
    summarise,
)


# --------------------------------------------------------------------------- #
# Bản vá ragas
# --------------------------------------------------------------------------- #
def test_vertexai_stub_lets_ragas_import():
    """Importing src.evaluation must make `import ragas` survive."""
    import ragas  # noqa: F401  — chính việc import được là nội dung của test

    assert ragas.__version__.startswith("0.4")


def test_stub_raises_if_anyone_actually_builds_a_vertex_client():
    """The stub must fail loudly, not silently pretend to be VertexAI."""
    with pytest.raises(ImportError, match="khong dung VertexAI"):
        evaluation.ChatVertexAI()


def test_collections_import_emits_no_deprecation_warning():
    """`ragas.metrics.collections` is the non-deprecated path — keep it that way.

    Chặn hồi quy nếu ai đó sửa build_metrics() về `from ragas.metrics import ...`:
    đường cũ vẫn CHẠY, chỉ kèm DeprecationWarning và sẽ bị bỏ ở ragas v1.0, nên
    không có gì báo động ngoài test này.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import ragas.metrics.collections  # noqa: F401

    ragas_deprecations = [
        w
        for w in caught
        if issubclass(w.category, DeprecationWarning) and "ragas.metrics" in str(w.message)
    ]
    assert not ragas_deprecations, [str(w.message) for w in ragas_deprecations]


# --------------------------------------------------------------------------- #
# Judge — cái bẫy 400 của Sonnet 5
# --------------------------------------------------------------------------- #
def test_judge_args_drop_unsupported_sampling_params(monkeypatch):
    """Sonnet 5 returns 400 for temperature/top_p — they must not survive.

    Test đáng giá nhất file này. ragas gắn temperature=0.01 + top_p=0.1 vào
    InstructorModelArgs rồi truyền thẳng sang Anthropic; nếu ai nâng version ragas
    làm hỏng chỗ pop, hỏng sẽ lộ ra ở đây (miễn phí) thay vì ở giữa lượt chạy $2.3.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")

    llm = evaluation.build_judge()

    assert "temperature" not in llm.model_args
    assert "top_p" not in llm.model_args
    assert llm.model_args["max_tokens"] == 4096


def test_usage_meter_prices_at_module_rates():
    meter = UsageMeter()
    meter.input_tokens, meter.output_tokens, meter.calls = 1_000, 500, 1
    assert meter.usd == pytest.approx(_usd(1_000, 500))
    assert meter.usd == pytest.approx(0.007)  # $2/$10 -> 0.002 + 0.005


# --------------------------------------------------------------------------- #
# Chọn metric theo nhóm
# --------------------------------------------------------------------------- #
def test_adversarial_group_skips_reference_metrics():
    """Adversarial questions get Faithfulness only — see _metrics_for's docstring."""
    questions = load_questions()
    adversarial = [q for q in questions.values() if q["group"] == "adversarial"]
    assert len(adversarial) == 4

    for item in adversarial:
        chosen = _metrics_for(item)
        assert chosen == ADVERSARIAL_METRICS
        assert "context_recall" not in chosen
        assert "context_precision" not in chosen
        # Answer Relevancy phạt câu trả lời né tránh -> phạt đúng hành vi ta muốn.
        assert "answer_relevancy" not in chosen


def test_non_adversarial_questions_get_all_four_metrics():
    questions = load_questions()
    scored = [q for q in questions.values() if q["group"] != "adversarial"]
    assert len(scored) == 28
    for item in scored:
        assert _metrics_for(item) == FULL_METRICS


def test_adversarial_questions_do_have_ground_truth():
    """The 4 adversarial questions have ground_truth; what they lack is source docs.

    Ghi lại một hiểu nhầm dễ mắc: chúng KHÔNG thiếu ground_truth (đó là một câu
    "không tìm thấy"), chúng thiếu expected_source_docs — và đó mới là lý do các
    chỉ số tham chiếu không dùng được.
    """
    questions = load_questions()
    for item in (q for q in questions.values() if q["group"] == "adversarial"):
        assert item["ground_truth"].strip()
        assert item["expected_source_docs"] == []


# --------------------------------------------------------------------------- #
# Cờ include_deprecated
# --------------------------------------------------------------------------- #
def test_history_question_uses_include_deprecated():
    """Q028 asks about the past — its correct source IS the Deprecated document."""
    questions = load_questions()
    assert _uses_deprecated(questions["Q028"]) is True
    assert "BR-002-v1" in questions["Q028"]["expected_source_docs"]


def test_current_value_questions_keep_deprecated_out():
    """Q026/Q027 must NOT see the Deprecated doc — they carry must_not_use_docs."""
    questions = load_questions()
    for qid in ("Q026", "Q027"):
        assert questions[qid].get("must_not_use_docs")
        assert _uses_deprecated(questions[qid]) is False


def test_no_deprecated_flag_outside_version_conflict():
    questions = load_questions()
    for item in questions.values():
        if item["group"] != "version_conflict":
            assert _uses_deprecated(item) is False


# --------------------------------------------------------------------------- #
# Phạm vi chạy và ngân sách
# --------------------------------------------------------------------------- #
def test_plan_only_runs_the_official_configuration():
    """rerank=True was dropped from this step — nothing may schedule it.

    Chặn hồi quy nếu ai đó thêm lại arm phụ: nó từng chiếm gần một nửa ngân sách.
    Rerank vẫn được đo ở tầng retrieval trong tests/test_reranking.py, chỉ là
    không tiêu tiền RAGAS cho nó.
    """
    for label in ("pilot", "run", "all"):
        assert all(rerank is False for _qid, rerank in build_plan(label)), label


def test_pilot_covers_every_distinct_code_path():
    """The 5 pilot questions hit 5 different branches, not just the first 5 rows."""
    questions = load_questions()
    assert len(PILOT_IDS) == 5
    assert len({questions[qid]["group"] for qid in PILOT_IDS}) == 5
    # Phải có đúng một câu adversarial (nhánh bỏ metric) và một câu lịch sử
    # (nhánh include_deprecated) — nếu không, pilot không kiểm được hai nhánh đó.
    assert any(questions[qid]["group"] == "adversarial" for qid in PILOT_IDS)
    assert any(_uses_deprecated(questions[qid]) for qid in PILOT_IDS)


def test_pilot_plus_run_covers_everything_exactly_once():
    """--pilot then --run must equal --all, with no question paid for twice."""
    combined = build_plan("pilot") + build_plan("run")
    assert sorted(combined) == sorted(build_plan("all"))
    assert len(combined) == len(set(combined))


def test_full_plan_is_the_whole_32_question_set_once():
    plan = build_plan("all")
    assert len(plan) == 32
    assert len({qid for qid, _rerank in plan}) == 32


def test_estimate_stays_within_the_approved_ceiling():
    """Budget after dropping the rerank arm, recalibrated on the real pilot.

    Số token của judge ban đầu đoán thiếu 32%; JUDGE_PROFILE đã hiệu chỉnh lại theo
    lượt pilot thật nên dự toán giờ khớp số đo trong khoảng 0,1%.
    """
    estimate = estimate_cost(build_plan("all"), load_questions())
    assert estimate["total_usd"] == pytest.approx(2.14, abs=0.10)
    assert estimate["ceiling_usd"] <= 3.25


def test_estimate_matches_the_measured_pilot():
    """The pilot cost $0.2770 for 46 judge calls — the estimator must reproduce it.

    Khóa lại phép hiệu chỉnh: nếu ai sửa JUDGE_PROFILE mà không đo lại, test này
    hỏng trước khi con số sai kịp dùng để duyệt ngân sách.
    """
    estimate = estimate_cost(build_plan("pilot"), load_questions())
    assert estimate["judge"]["calls"] == 46
    assert estimate["judge"]["usd"] == pytest.approx(0.2770, abs=0.01)


def test_estimate_charges_adversarial_questions_less():
    """Adversarial questions run 1 metric, so they must cost strictly less."""
    questions = load_questions()
    full = estimate_cost([("Q001", False)], questions)
    adversarial = estimate_cost([("Q031", False)], questions)
    assert adversarial["total_usd"] < full["total_usd"]
    assert adversarial["judge"]["calls"] == sum(
        JUDGE_PROFILE[m][0] for m in ADVERSARIAL_METRICS
    )


# --------------------------------------------------------------------------- #
# Tổng hợp
# --------------------------------------------------------------------------- #
def _record(qid, group, expected_docs, scores, refused=False):
    return {
        "id": qid,
        "group": group,
        "rerank": False,
        "scores": {name: scores.get(name) for name in FULL_METRICS},
        "refused": refused,
        "expected_source_docs": expected_docs,
        "retrieved_doc_ids": [],
        "cited_doc_ids": [],
        "gate_blocked": False,
        "tokens": {"in": 0, "out": 0},
        "cost_usd": 0.0,
    }


def test_summarise_ignores_none_instead_of_treating_it_as_zero():
    """A skipped metric must not drag the average down.

    None nghĩa "không chấm được", 0.0 nghĩa "chấm rồi, tệ". Gộp None thành 0 sẽ
    làm điểm nhóm adversarial kéo tụt điểm tổng một cách vô căn cứ.
    """
    records = [
        _record("Q001", "single_source", ["BR-002"], {"faithfulness": 1.0}),
        _record("Q031", "adversarial", [], {"faithfulness": None}),
    ]
    summary = summarise(records)
    assert summary["scores_by_group"]["TONG"]["faithfulness"] == 1.0
    assert summary["scores_by_group"]["adversarial"]["faithfulness"] is None


def test_refusal_accuracy_counts_only_adversarial():
    records = [
        _record("Q001", "single_source", ["BR-002"], {}, refused=False),
        _record("Q029", "adversarial", [], {}, refused=True),
        _record("Q030", "adversarial", [], {}, refused=True),
        _record("Q031", "adversarial", [], {}, refused=False),
        _record("Q032", "adversarial", [], {}, refused=True),
    ]
    adversarial = summarise(records)["adversarial"]
    assert adversarial["n"] == 4
    assert adversarial["refusal_accuracy"] == pytest.approx(0.75)


def test_judge_disables_thinking(monkeypatch):
    """Sonnet 5 thinks by default, and instructor 1.3.2 cannot parse ThinkingBlock.

    Lỗi này đã làm hỏng nguyên một lượt pilot: content[0] là ThinkingBlock, còn
    instructor lấy thẳng content[0].text -> AttributeError. Nó hỏng NGẦM (ragas
    nuốt lỗi thành điểm None) và KHÔNG ĐỀU (metric nhiều lượt gọi dính nặng hơn),
    nên nhìn bảng điểm sẽ tưởng hệ thống kém chứ không nghĩ là lỗi parse.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")

    llm = evaluation.build_judge()

    assert llm.model_args["thinking"] == {"type": "disabled"}


# --------------------------------------------------------------------------- #
# Điểm sửa tay
# --------------------------------------------------------------------------- #
def test_every_override_carries_evidence():
    """A hand-edited score without a reason is indistinguishable from fudging."""
    for qid, metrics in evaluation.MANUAL_OVERRIDES.items():
        for metric, spec in metrics.items():
            assert set(spec) == {"cu", "moi", "ly_do"}, (qid, metric)
            assert len(spec["ly_do"]) > 100, f"{qid}/{metric}: lý do quá sơ sài"
            assert metric in FULL_METRICS


def test_override_keeps_the_original_machine_score_visible():
    records = [_record("Q012", "single_source", ["US-EPIC-021"], {"context_recall": 0.0})]
    out = evaluation.apply_overrides(records)

    assert out[0]["scores"]["context_recall"] == 1.0
    audit = out[0]["_dieu_chinh_thu_cong"]["context_recall"]
    assert audit["diem_may_cham"] == 0.0
    assert audit["diem_sau_doi_chieu"] == 1.0
    assert "US-EPIC-021" in audit["ly_do"]


def test_override_refuses_to_fire_when_the_score_changed(caplog):
    """If a re-run produced a different score, the hand check no longer applies.

    Bản sửa tay gắn với MỘT lần đối chiếu cụ thể. Nếu chạy lại mà judge cho điểm
    khác, đè bừa lên là làm giả số liệu — phải kêu to và bỏ qua.
    """
    records = [_record("Q012", "single_source", ["US-EPIC-021"], {"context_recall": 0.5})]
    out = evaluation.apply_overrides(records)

    assert out[0]["scores"]["context_recall"] == 0.5
    assert "_dieu_chinh_thu_cong" not in out[0]


# --------------------------------------------------------------------------- #
# Arm rerank=True (cờ --rerank)
# --------------------------------------------------------------------------- #
def test_rerank_plan_covers_the_28_sourced_questions():
    """--rerank --pilot then --run = 28 sourced questions + Q031 from the pilot.

    Q031 là adversarial, NGOÀI 28 câu; nó chỉ chạy ở pilot để kiểm nhánh
    gate-trước-rerank và không được vào bảng so sánh.
    """
    scope = set(evaluation.rerank_scope())
    assert len(scope) == 28
    assert all(rerank is True for _q, rerank in build_plan("all", rerank=True))
    assert {q for q, _ in build_plan("all", rerank=True)} == scope

    combined = build_plan("pilot", rerank=True) + build_plan("run", rerank=True)
    assert len(combined) == len(set(combined))
    assert {q for q, _ in combined} == scope | {"Q031"}


def test_rerank_export_never_touches_the_official_results(monkeypatch, tmp_path):
    """The rerank arm writes its own file and does not apply Q012's hand fix."""
    official = tmp_path / "ragas_results.json"
    monkeypatch.setattr(evaluation, "RESULTS_PATH", official)
    monkeypatch.setattr(evaluation, "RESULTS_RERANK_PATH", tmp_path / "rerank.json")

    questions = load_questions()
    ids = evaluation.rerank_scope(questions)
    # Q012 ở arm rerank ra đúng điểm 0.0 như lúc đối chiếu: vẫn KHÔNG được sửa.
    make = lambda qid, rr, recall: dict(
        _record(qid, questions[qid]["group"], questions[qid]["expected_source_docs"],
                {n: recall if n == "context_recall" else 1.0 for n in FULL_METRICS}),
        rerank=rr,
    )
    baseline = evaluation.apply_overrides(
        [make(q, False, 0.0 if q == "Q012" else 1.0) for q in ids]
    )
    import json
    official.write_text(json.dumps({"per_question": baseline}), encoding="utf-8")
    before = official.read_text(encoding="utf-8")

    rerank = [make(q, True, 0.0 if q == "Q012" else 1.0) for q in ids]
    payload = evaluation.export_rerank(rerank, {"total_usd": 0.0})

    assert official.read_text(encoding="utf-8") == before
    q012 = next(r for r in payload["per_question"] if r["id"] == "Q012")
    assert q012["scores"]["context_recall"] == 0.0
    assert "_dieu_chinh_thu_cong" not in q012
    assert payload["dieu_chinh_thu_cong"]["co_che_chan"]["Q012.context_recall"][
        "co_che_chan_se_cho_qua"
    ] is True

    cmp_ = payload["so_sanh_voi_rerank_false"]
    # Baseline chính thức đã sửa tay Q012 -> 1.0; điểm gốc máy chấm là 0.0.
    official_row = cmp_["baseline_chinh_thuc"]["TONG"]["context_recall"]
    raw_row = cmp_["baseline_diem_may_cham_goc"]["TONG"]["context_recall"]
    assert official_row["rerank_false"] == 1.0
    assert raw_row["rerank_false"] == raw_row["rerank_true"]
    assert raw_row["chenh_lech"] == 0.0


def test_compare_arms_refuses_mismatched_question_sets():
    a = [_record("Q001", "single_source", ["BR-002"], {"faithfulness": 1.0})]
    b = [_record("Q002", "single_source", ["BR-002"], {"faithfulness": 1.0})]
    with pytest.raises(ValueError):
        evaluation.compare_arms(a, b)
