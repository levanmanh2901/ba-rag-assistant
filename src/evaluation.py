"""RAGAS evaluation over the 32-question benchmark, with a hard budget gate.

Đo chất lượng CÂU TRẢ LỜI CUỐI, khác với :mod:`src.hybrid_search` (chỉ đo Recall@3
ở tầng retrieval). Bốn chỉ số RAGAS:

* **Faithfulness**      — câu trả lời có bịa gì ngoài context không
* **Answer Relevancy**  — có trả lời đúng thứ được hỏi không
* **Context Precision** — context lấy về có sạch không (bao nhiêu phần thực sự hữu ích)
* **Context Recall**    — context có chứa đủ thứ cần để trả lời không

CHẠY THẬT LÀ TỐN TIỀN. Mặc định của module này là ``--dry-run``: in số lượt gọi và
chi phí ước tính rồi dừng, không gọi API. Xem :func:`estimate_cost`.
"""

# --------------------------------------------------------------------------- #
# VÁ BUG ragas 0.4.3 — KHỐI NÀY PHẢI ĐỨNG TRƯỚC MỌI `import ragas`
# --------------------------------------------------------------------------- #
# ragas/llms/base.py:12 import CỨNG `langchain_community.chat_models.vertexai`
# ở top level, dù ta không hề dùng VertexAI. langchain-community 0.4.x đã bỏ
# submodule đó, nên `import ragas` nổ ModuleNotFoundError ngay — kể cả khi chỉ
# chấm điểm bằng Claude API. Đã kiểm chứng trong venv của project:
# ragas 0.4.3 + langchain-community 0.4.2 -> lỗi; chèn stub này vào trước -> chạy.
#
# Bug đã biết, cùng họ với các issue "ChatVertexAI import error" trên
# github.com/explodinggradients/ragas — nguyên nhân là import không lười ở
# ragas/llms/base.py, không phải do cấu hình phía ta.
#
# Stub CỐ TÌNH raise ImportError nếu có ai thật sự khởi tạo ChatVertexAI: ta muốn
# nổ to và rõ, chứ không muốn im lặng chạy nhầm sang provider khác.
import sys
import types

_vertexai_stub = types.ModuleType("langchain_community.chat_models.vertexai")


class ChatVertexAI:
    """Placeholder so that importing ragas does not explode."""

    def __init__(self, *args, **kwargs):
        raise ImportError("Stub - khong dung VertexAI, chi dung Claude API")


_vertexai_stub.ChatVertexAI = ChatVertexAI
sys.modules["langchain_community.chat_models.vertexai"] = _vertexai_stub
# --------------------------------------------------------------------------- #

import argparse
import asyncio
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

from src.generation import (
    MODEL,
    PRICE_PER_MTOK_IN,
    PRICE_PER_MTOK_OUT,
    GenerationResult,
    generate_answer,
)
from src.vectorstore import PROJECT_ROOT

logger = logging.getLogger(__name__)

load_dotenv()

EVAL_PATH = PROJECT_ROOT / "data" / "Evaluation" / "evaluation_questions.json"
RESULTS_PATH = PROJECT_ROOT / "data" / "Evaluation" / "ragas_results.json"
# Cache để chạy lại không mất tiền hai lần cho câu đã xong. Xóa được an toàn.
STORE_PATH = PROJECT_ROOT / "data" / "Evaluation" / "ragas_store.json"

# Judge CÙNG model với generator: rẻ, đổi lại có self-preference bias (model rộng
# lượng hơn khi chấm output của chính nó). Đã cân nhắc và chấp nhận — ghi rõ trong
# metadata của file kết quả để người đọc biết mà trừ hao.
JUDGE_MODEL = MODEL

# Embeddings cho Answer Relevancy. ragas KHÔNG có provider embeddings Anthropic,
# nên dùng chính model đa ngữ mà src.embedding đã nạp: nhất quán cách hiểu tiếng
# Việt với tầng retrieval, và không phải tải thêm model nào.
JUDGE_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# CHỈ đo cấu hình chính thức rerank=False. Nhánh rerank=True đã bỏ hẳn khỏi bước
# đánh giá này: nó vẫn là tham số của generate_answer() và vẫn được
# tests/test_reranking.py đo ở tầng retrieval (Recall@3), nhưng không tiêu tiền
# RAGAS cho nó nữa — một arm subset n=10 chọn sẵn ở hai nhóm có lợi thế thì không
# đủ sức kết luận gì, mà vẫn tốn gần một nửa ngân sách.

# --------------------------------------------------------------------------- #
# Điểm sửa tay sau khi đối chiếu thủ công
# --------------------------------------------------------------------------- #
# CHỈ dùng khi đã MỞ context ra đọc và chứng minh được judge chấm sai. Không dùng
# để làm đẹp số. Mỗi mục bắt buộc có `ly_do` ghi bằng chứng cụ thể, vì người đọc
# báo cáo phải tự kiểm tra lại được.
#
# Đặt ở đây (không sửa thẳng vào JSON) để lượt chạy lại không xóa mất, và để
# tests/ kiểm được.
MANUAL_OVERRIDES: dict[str, dict[str, Any]] = {
    "Q012": {
        "context_recall": {
            "cu": 0.0,
            "moi": 1.0,
            "ly_do": (
                "LOI GIAM KHAO. Doi chieu tay: chunk 1 trong context DUNG LA "
                "US-EPIC-021 / User Story MANHPAY-1425 va chua nguyen van "
                "'**Status:** Backlog' — tuc dap an nam san trong context. He thong "
                "cung tra loi dung va trich dung [US-EPIC-021] (faithfulness 1.0, "
                "context_precision 1.0), nen recall 0.0 tu no da mau thuan. "
                "Nguyen nhan: ground_truth 'Backlog, chua len sprint.' co 2 ve; ve "
                "'chua len sprint' khong nam trong chunk cua MANHPAY-1425 (no xuat "
                "hien o chunk 5 nhung la cua MANHPAY-1230, mot user story KHAC), nen "
                "judge khong quy duoc va cham 0 ca cau. "
                "Dat 1.0 vi 'Backlog' trong agile CHINH LA 'chua len sprint' — hai ve "
                "la mot y. Ai muon chat che hon co the dat 0.5 (1/2 ve khop nguyen van)."
            ),
        }
    },
}

# Pilot phủ 5 NHÁNH CODE khác nhau, không phải 5 câu đầu bảng:
# Q001 đường đi cơ bản | Q018 câu tra số (TABLE_BOOST) | Q020 gộp nhiều nguồn
# Q028 nhánh include_deprecated=True | Q031 từ chối + nhánh bỏ metric tham chiếu
PILOT_IDS = ["Q001", "Q018", "Q020", "Q028", "Q031"]


# --------------------------------------------------------------------------- #
# Ước tính chi phí — đây là thứ chạy TRƯỚC khi tiêu đồng nào
# --------------------------------------------------------------------------- #
# HIỆU CHỈNH theo lượt pilot thật (5 câu, 2026-09-12), không phải phỏng đoán nữa:
# đo được 3.069 token in, output 62-297 tùy câu (trung bình 160). Làm tròn lên một
# chút cho output vì câu đa nguồn (Q020: 297) dài hơn hẳn.
EST_GEN_IN = 3_100
EST_GEN_OUT = 200

# Số lượt gọi LLM mỗi metric mỗi câu, đọc từ kiến trúc metric trong
# venv/Lib/site-packages/ragas/metrics/collections/*/metric.py:
#   faithfulness      2 lượt : tách statement, rồi NLI từng statement với context
#   answer_relevancy  3 lượt : strictness=3, sinh 3 câu hỏi ngược (embedding local, $0)
#   context_precision 5 lượt : MỘT LƯỢT MỖI CONTEXT trong top-5 — đắt nhất
#   context_recall    1 lượt : đối chiếu reference với toàn bộ context
# SỐ LƯỢT GỌI đã khớp chính xác với pilot (dự đoán 46, đo được 46), nhưng SỐ TOKEN
# ban đầu đoán thiếu 32% — dưới đây đã nhân hệ số hiệu chỉnh theo lượt pilot thật
# (46 lượt, $0.2770): công thức này giờ cho $0.2776 cho đúng bộ 5 câu đó.
# (tên metric, số lượt, token in, token out)
JUDGE_PROFILE = {
    "faithfulness": (2, 5_800, 920),
    "answer_relevancy": (3, 2_770, 400),
    "context_precision": (5, 5_940, 660),
    "context_recall": (1, 5_020, 530),
}

# Metric chạy cho câu adversarial. Xem _metrics_for() để biết vì sao chỉ có một.
ADVERSARIAL_METRICS = ("faithfulness",)
FULL_METRICS = tuple(JUDGE_PROFILE)


def _usd(input_tokens: int, output_tokens: int) -> float:
    """Cost of a call at this project's Sonnet 5 prices."""
    return (
        input_tokens * PRICE_PER_MTOK_IN + output_tokens * PRICE_PER_MTOK_OUT
    ) / 1_000_000


def _metrics_for(item: dict[str, Any]) -> tuple[str, ...]:
    """Which RAGAS metrics are meaningful for this question.

    Nhóm adversarial (Q029-Q032) CÓ ``ground_truth`` — là một câu "không tìm thấy"
    — nhưng ``expected_source_docs`` RỖNG. Ba trong bốn chỉ số vô nghĩa ở đây:

    * **Context Recall**    : không có nguồn đúng nào để mà recall. Cùng lý do
      :mod:`src.hybrid_search` bỏ qua nhóm này khi tính Recall@3.
    * **Context Precision** : cần reference lấy từ tài liệu để chấm "context có hữu
      ích không". Reference ở đây là lời từ chối, chấm ra số vô nghĩa.
    * **Answer Relevancy**  : có bộ phát hiện câu trả lời NÉ TRÁNH và cho điểm ~0.
      Tức là nó PHẠT đúng cái hành vi từ chối mà ta muốn hệ thống làm. Đưa vào
      điểm tổng sẽ bóp méo kết quả theo hướng ngược hẳn.

    Chỉ giữ Faithfulness (bắt trường hợp model bịa thêm SAU câu từ chối), còn thứ
    thực sự đo "có từ chối đúng không" là ``refusal_accuracy`` — deterministic,
    không tốn một đồng API nào. Xem :func:`summarise`.
    """
    return ADVERSARIAL_METRICS if not item["expected_source_docs"] else FULL_METRICS


def estimate_cost(plan: list[tuple[str, bool]], questions: dict[str, dict]) -> dict:
    """Predict the cost of a run before spending anything.

    ``plan`` là danh sách ``(question_id, rerank)`` sắp chạy.
    """
    gen_calls = len(plan)
    gen_in, gen_out = gen_calls * EST_GEN_IN, gen_calls * EST_GEN_OUT

    judge_calls = judge_in = judge_out = 0
    per_metric: dict[str, int] = {}
    for qid, _rerank in plan:
        for name in _metrics_for(questions[qid]):
            calls, tok_in, tok_out = JUDGE_PROFILE[name]
            judge_calls += calls
            judge_in += tok_in
            judge_out += tok_out
            per_metric[name] = per_metric.get(name, 0) + calls

    generation_usd = _usd(gen_in, gen_out)
    judge_usd = _usd(judge_in, judge_out)
    return {
        "generation": {
            "calls": gen_calls,
            "input_tokens": gen_in,
            "output_tokens": gen_out,
            "usd": round(generation_usd, 4),
        },
        "judge": {
            "calls": judge_calls,
            "input_tokens": judge_in,
            "output_tokens": judge_out,
            "usd": round(judge_usd, 4),
            "calls_by_metric": per_metric,
        },
        "total_usd": round(generation_usd + judge_usd, 4),
        "ceiling_usd": round((generation_usd + judge_usd) * 1.5, 4),
    }


# --------------------------------------------------------------------------- #
# Đo chi phí THẬT của judge
# --------------------------------------------------------------------------- #
class UsageMeter:
    """Tally token usage across every judge call ragas makes."""

    def __init__(self) -> None:
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    @property
    def usd(self) -> float:
        return _usd(self.input_tokens, self.output_tokens)

    def as_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "usd": round(self.usd, 4),
        }


def _instrument(client: anthropic.AsyncAnthropic, meter: UsageMeter):
    """Wrap ``client.messages.create`` so judge calls land in ``meter``.

    ragas gọi API qua instructor, và instructor trả về model Pydantic đã parse —
    KHÔNG trả `usage` ra ngoài. Nên muốn biết judge tốn bao nhiêu thì phải đếm ở
    tầng dưới instructor, tức là bọc chính client trước khi giao nó đi.

    Nếu instructor đổi cách gọi ở version khác, ``meter.calls`` sẽ bằng 0 và
    :func:`run_evaluation` chuyển sang ghi chi phí ƯỚC TÍNH (có đánh dấu rõ trong
    JSON), chứ không âm thầm báo $0.
    """
    original = client.messages.create

    async def counting_create(*args, **kwargs):
        response = await original(*args, **kwargs)
        usage = getattr(response, "usage", None)
        if usage is not None:
            meter.calls += 1
            meter.input_tokens += getattr(usage, "input_tokens", 0)
            meter.output_tokens += getattr(usage, "output_tokens", 0)
        return response

    client.messages.create = counting_create
    return client


# --------------------------------------------------------------------------- #
# Judge
# --------------------------------------------------------------------------- #
def build_judge(model: str = JUDGE_MODEL, meter: UsageMeter | None = None):
    """Build the ragas judge LLM, backed by the Claude API.

    CHỖ DỄ HỎNG NHẤT CỦA CẢ MODULE. ``InstructorModelArgs`` của ragas mặc định
    gắn ``temperature=0.01`` và ``top_p=0.1``, rồi nhánh Anthropic của
    ``_map_provider_params()`` truyền THẲNG chúng sang API (pass-through, không
    lọc gì). Mà Sonnet 5 trả **400** cho cả hai tham số đó — đúng cái đã ghi
    trong comment ở :func:`src.generation.generate_answer`.

    Truyền ``temperature=None`` qua kwargs KHÔNG cứu được: kwargs chỉ GHI ĐÈ giá
    trị chứ không XÓA được key khỏi dict. Phải pop tay sau khi dựng xong.
    """
    from ragas.llms import llm_factory

    client = anthropic.AsyncAnthropic()
    if meter is not None:
        client = _instrument(client, meter)

    llm = llm_factory(model, provider="anthropic", client=client)
    llm.model_args.pop("temperature", None)
    llm.model_args.pop("top_p", None)
    # Mặc định 1024 dễ cụt giữa chừng khi tách statement từ câu trả lời tiếng Việt
    # dài, và structured output bị cắt thì ragas ném lỗi parse chứ không giảm điểm.
    llm.model_args["max_tokens"] = 4096

    # BẮT BUỘC — đã làm hỏng nguyên một lượt pilot trước khi phát hiện.
    # KHÔNG truyền `thinking` thì Sonnet 5 chạy adaptive thinking, nên content[0]
    # là một ThinkingBlock. instructor 1.3.2 quá cũ, nó lấy thẳng content[0].text
    # -> AttributeError: 'ThinkingBlock' object has no attribute 'text'.
    # Đo thật: mặc định 3/3 lượt trả thinking block; disabled 3/3 lượt trả text.
    # Hỏng NGẦM và KHÔNG ĐỀU: metric nào gọi nhiều lượt càng dễ dính, nên
    # context_precision (5 lượt mỗi câu) hỏng 100% còn context_recall (1 lượt)
    # chỉ thỉnh thoảng — nhìn bảng điểm tưởng là hệ thống kém, thực ra là lỗi parse.
    # Judge ở đây chỉ phân loại theo cấu trúc, không cần suy luận sâu; tắt thinking
    # còn rẻ hơn vì thinking token vẫn bị tính vào output.
    llm.model_args["thinking"] = {"type": "disabled"}
    return llm


def build_metrics(llm) -> dict[str, Any]:
    """Instantiate the four RAGAS metrics.

    Dùng ``ragas.metrics.collections`` chứ KHÔNG phải ``ragas.metrics``: đường
    import cũ (``from ragas.metrics import faithfulness``) phát DeprecationWarning
    và sẽ bị bỏ ở v1.0. Đã kiểm chứng: đường ``collections`` import sạch.
    """
    from ragas.embeddings import embedding_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecisionWithReference,
        ContextRecall,
        Faithfulness,
    )

    embeddings = embedding_factory("huggingface", JUDGE_EMBEDDINGS)
    return {
        "faithfulness": Faithfulness(llm=llm),
        "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=embeddings),
        "context_precision": ContextPrecisionWithReference(llm=llm),
        "context_recall": ContextRecall(llm=llm),
    }


async def score_one(
    metrics: dict[str, Any],
    item: dict[str, Any],
    result: GenerationResult,
) -> dict[str, float | None]:
    """Score a single answered question across the metrics that apply to it."""
    wanted = _metrics_for(item)
    scores: dict[str, float | None] = {name: None for name in FULL_METRICS}

    # Bị gate chặn thì không có context lẫn câu trả lời thật để chấm — mọi chỉ số
    # RAGAS đều vô nghĩa. Ghi None chứ không ghi 0.0: 0.0 nghĩa là "chấm rồi, tệ",
    # None nghĩa là "không chấm được", hai thứ khác hẳn nhau khi đọc bảng.
    if not result.contexts:
        return scores

    for name in wanted:
        metric = metrics[name]
        try:
            if name == "faithfulness":
                out = await metric.ascore(
                    user_input=item["question"],
                    response=result.answer,
                    retrieved_contexts=result.contexts,
                )
            elif name == "answer_relevancy":
                out = await metric.ascore(
                    user_input=item["question"], response=result.answer
                )
            elif name == "context_precision":
                out = await metric.ascore(
                    user_input=item["question"],
                    reference=item["ground_truth"],
                    retrieved_contexts=result.contexts,
                )
            else:  # context_recall
                out = await metric.ascore(
                    user_input=item["question"],
                    retrieved_contexts=result.contexts,
                    reference=item["ground_truth"],
                )
            scores[name] = float(out.value)
        except Exception as exc:  # noqa: BLE001
            # Một metric hỏng không được kéo đổ cả lượt chạy đã tốn tiền. Ghi None
            # và đi tiếp; cuối lượt sẽ thấy ngay cột nào thiếu.
            logger.warning("%s hỏng ở %s: %s", name, item["id"], exc)
    return scores


# --------------------------------------------------------------------------- #
# Chạy
# --------------------------------------------------------------------------- #
def load_questions() -> dict[str, dict[str, Any]]:
    """The 32 benchmark questions, keyed by id."""
    payload = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    return {item["id"]: item for item in payload["questions"]}


def _load_store() -> dict[str, dict]:
    if not STORE_PATH.exists():
        return {}
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def _save_store(store: dict[str, dict]) -> None:
    STORE_PATH.write_text(
        json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _uses_deprecated(item: dict[str, Any]) -> bool:
    """Whether this question legitimately needs Deprecated documents.

    Luật LẤY NGUYÊN từ :mod:`src.hybrid_search` (khối ``__main__``, chỗ tính
    Recall@3). Q028 hỏi "TRƯỚC ĐÂY hạn mức Tier 3 là bao nhiêu" và nguồn đúng của
    nó CHÍNH LÀ bản Deprecated BR-002-v1 — không bật cờ này thì Q028 trông như một
    lỗi retrieval, trong khi hệ thống đang làm đúng.
    """
    return item["group"] == "version_conflict" and not item.get("must_not_use_docs")


async def run_evaluation(
    question_ids: list[str] | None = None,
    rerank: bool = False,
    resume: bool = True,
    meter: UsageMeter | None = None,
) -> tuple[list[dict[str, Any]], UsageMeter]:
    """Generate answers and score them, one question at a time.

    Ghi vào store sau MỖI câu chứ không đợi đến cuối: sập giữa chừng thì phần đã
    trả tiền vẫn còn nguyên, chạy lại chỉ tính tiền phần còn thiếu.

    Truyền ``meter`` sẵn có khi chạy nhiều arm liên tiếp — mỗi lượt gọi hàm này
    dựng một judge mới, nên để nó tự tạo meter thì chi phí của arm trước bị mất.
    """
    questions = load_questions()
    ids = question_ids or list(questions)
    store = _load_store()

    meter = meter if meter is not None else UsageMeter()
    llm = build_judge(meter=meter)
    metrics = build_metrics(llm)

    records = []
    for qid in ids:
        item = questions[qid]
        key = f"{qid}|rerank={rerank}"
        if resume and key in store:
            logger.info("resume: bỏ qua %s (đã có trong store)", key)
            records.append(store[key])
            continue

        result = generate_answer(
            item["question"],
            rerank=rerank,
            include_deprecated=_uses_deprecated(item),
        )
        scores = await score_one(metrics, item, result)

        record = {
            "id": qid,
            "group": item["group"],
            "rerank": rerank,
            "question": item["question"],
            "ground_truth": item["ground_truth"],
            # Lưu cả answer lẫn contexts, dù file kết quả phình to: lượt pilot đầu
            # tiên hỏng vì lỗi parse phía judge, và vì không lưu hai trường này nên
            # muốn chấm lại phải TRẢ TIỀN SINH LẠI toàn bộ. Với 32 câu đó là $0.37
            # vứt đi mỗi lần judge có trục trặc. Cũng là thứ duy nhất cho phép đọc
            # lại xem một điểm thấp là do retrieval tồi hay do câu trả lời tồi.
            "answer": result.answer,
            "contexts": result.contexts,
            "scores": scores,
            "refused": result.refused,
            "expected_source_docs": item["expected_source_docs"],
            "retrieved_doc_ids": result.retrieved_doc_ids,
            "cited_doc_ids": result.cited_doc_ids,
            "gate_blocked": not result.contexts,
            "tokens": {"in": result.input_tokens, "out": result.output_tokens},
            "cost_usd": round(result.cost_usd, 6),
        }
        records.append(record)
        store[key] = record
        _save_store(store)
        logger.info("%s xong — %s", key, scores)

    return records, meter


# --------------------------------------------------------------------------- #
# Tổng hợp
# --------------------------------------------------------------------------- #
def _mean(values: list[float | None]) -> float | None:
    real = [v for v in values if v is not None]
    return round(sum(real) / len(real), 4) if real else None


def summarise(records: list[dict]) -> dict[str, Any]:
    """Aggregate per-question scores into the by-group table."""
    groups: dict[str, list[dict]] = {}
    for record in records:
        groups.setdefault(record["group"], []).append(record)

    by_group = {"_unit": "diem trung binh 0..1, cao hon la tot hon"}
    for group, items in sorted(groups.items()):
        by_group[group] = {"n": len(items)} | {
            name: _mean([i["scores"][name] for i in items]) for name in FULL_METRICS
        }
    by_group["TONG"] = {"n": len(records)} | {
        name: _mean([r["scores"][name] for r in records]) for name in FULL_METRICS
    }

    # Chỉ số THẬT SỰ đo "có từ chối đúng không" cho nhóm adversarial. Deterministic,
    # $0 API: đọc thẳng GenerationResult.refused, đúng thứ test_adversarial_
    # questions_are_refused trong tests/test_generation.py đã assert.
    adversarial = [r for r in records if not r["expected_source_docs"]]
    refusal = {
        "_note": (
            "Chi so chinh cua nhom adversarial. Context Recall/Precision bi bo vi "
            "khong co nguon dung; Answer Relevancy bi bo vi no PHAT cau tra loi ne "
            "tranh, tuc phat dung hanh vi ma ta muon."
        ),
        "n": len(adversarial),
        "refusal_accuracy": (
            round(sum(r["refused"] for r in adversarial) / len(adversarial), 4)
            if adversarial
            else None
        ),
        "per_question": {r["id"]: r["refused"] for r in adversarial},
    }
    return {"scores_by_group": by_group, "adversarial": refusal}


def apply_overrides(records: list[dict]) -> list[dict]:
    """Apply hand-verified score corrections, keeping the original value visible.

    Ghi đè TẠI CHỖ nhưng không xóa số cũ: mỗi bản ghi bị sửa sẽ mang thêm khóa
    ``_dieu_chinh_thu_cong`` chứa điểm gốc và lý do, để người đọc kiểm tra lại được
    và để không ai tưởng đây là điểm máy chấm.
    """
    for record in records:
        override = MANUAL_OVERRIDES.get(record["id"])
        if not override:
            continue
        for metric, spec in override.items():
            current = record["scores"].get(metric)
            if current != spec["cu"]:
                # Điểm đã khác giá trị lúc đối chiếu tay -> dữ liệu đã đo lại,
                # bản sửa tay không còn căn cứ. Báo động chứ không im lặng đè lên.
                logger.warning(
                    "%s: bỏ qua sửa tay cho %s — điểm hiện tại %s, lúc đối chiếu là %s.",
                    record["id"], metric, current, spec["cu"],
                )
                continue
            record["scores"][metric] = spec["moi"]
            record.setdefault("_dieu_chinh_thu_cong", {})[metric] = {
                "diem_may_cham": spec["cu"],
                "diem_sau_doi_chieu": spec["moi"],
                "ly_do": spec["ly_do"],
            }
    return records


def _existing_ket_luan() -> list[str]:
    """Carry hand-written conclusions across re-runs."""
    if not RESULTS_PATH.exists():
        return []
    try:
        return json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("ket_luan", [])
    except (json.JSONDecodeError, OSError):
        return []


def _precision_recall_gap(records: list[dict]) -> dict[str, Any]:
    """Quantify the Tuần 8 headline finding: high recall, much lower precision.

    Recall@3 của Tuần 5-7 chỉ hỏi "có lấy được tài liệu đúng không" nên không thấy
    được nhiễu. Context Precision hỏi tiếp "trong 5 chunk đưa cho LLM thì bao nhiêu
    phần thực sự dùng được". Chênh lệch giữa hai con số CHÍNH LÀ lượng nhiễu — thứ
    số liệu cũ mù hoàn toàn.
    """
    scored = [r for r in records if r["expected_source_docs"]]
    precision = [r["scores"]["context_precision"] for r in scored]
    recall = [r["scores"]["context_recall"] for r in scored]

    buckets = {"1.00": 0, "0.75-0.99": 0, "0.50-0.74": 0, "0.25-0.49": 0, "<0.25": 0}
    for value in (p for p in precision if p is not None):
        key = (
            "1.00" if value >= 0.999
            else "0.75-0.99" if value >= 0.75
            else "0.50-0.74" if value >= 0.5
            else "0.25-0.49" if value >= 0.25
            else "<0.25"
        )
        buckets[key] += 1

    mean_p, mean_r = _mean(precision), _mean(recall)
    return {
        "_note": (
            "Recall cao + Precision thap = LAY DU nhung LAY THUA. Recall@3 cua Tuan "
            "5-7 khong nhin thay duoc chieu nay."
        ),
        "n_cau_cham": len(scored),
        "context_recall_tb": mean_r,
        "context_precision_tb": mean_p,
        "khoang_cach": round(mean_p - mean_r, 4) if None not in (mean_p, mean_r) else None,
        "phan_bo_precision": buckets,
        "_doc_hieu": (
            f"{buckets['1.00']}/{len(scored)} cau co context sach tuyet doi; "
            f"{buckets['0.25-0.49'] + buckets['<0.25']}/{len(scored)} cau co qua nua "
            "so chunk la nhieu."
        ),
    }


def print_table(summary: dict[str, Any], title: str) -> None:
    """Print the by-group table, mirroring the cost table in tests/conftest.py."""
    by_group = summary["scores_by_group"]
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")
    header = f"{'nhóm':<18}{'n':>4}" + "".join(f"{n[:11]:>13}" for n in FULL_METRICS)
    print(header)
    print("-" * 78)
    for group, row in by_group.items():
        if group.startswith("_"):
            continue
        cells = "".join(
            f"{(f'{row[n]:.3f}' if row[n] is not None else '—'):>13}"
            for n in FULL_METRICS
        )
        print(f"{group:<18}{row['n']:>4}{cells}")
    adv = summary["adversarial"]
    if adv["refusal_accuracy"] is not None:
        print(
            f"\nrefusal_accuracy (nhóm adversarial, n={adv['n']}): "
            f"{adv['refusal_accuracy']:.3f}"
        )


def print_estimate(estimate: dict[str, Any], plan_label: str) -> None:
    """Print the pre-flight budget so a human can approve it."""
    gen, judge = estimate["generation"], estimate["judge"]
    print(f"\n{'=' * 78}\nƯỚC TÍNH CHI PHÍ — {plan_label}\n{'=' * 78}")
    print(f"  Giá áp dụng: ${PRICE_PER_MTOK_IN:.2f} in / ${PRICE_PER_MTOK_OUT:.2f} out mỗi 1M token ({JUDGE_MODEL})")
    print(
        f"\n  Sinh câu trả lời : {gen['calls']:>4} lượt  "
        f"{gen['input_tokens']:>8,} in {gen['output_tokens']:>7,} out  ${gen['usd']:.4f}"
    )
    print(
        f"  Chấm điểm RAGAS  : {judge['calls']:>4} lượt  "
        f"{judge['input_tokens']:>8,} in {judge['output_tokens']:>7,} out  ${judge['usd']:.4f}"
    )
    for name, calls in sorted(judge["calls_by_metric"].items()):
        print(f"      {name:<20}{calls:>5} lượt")
    print(f"\n  TỔNG DỰ KIẾN               ${estimate['total_usd']:.4f}")
    print(f"  Trần an toàn (x1.5)        ${estimate['ceiling_usd']:.4f}")


def build_plan(mode: str) -> list[tuple[str, bool]]:
    """The (question_id, rerank) pairs a given mode will run.

    Chỉ còn một cấu hình (``rerank=False``) nên phần tử thứ hai luôn là False —
    giữ hình dạng cặp để :func:`estimate_cost` và store không phải đổi schema nếu
    sau này có ai muốn đo lại một cấu hình khác.
    """
    questions = load_questions()
    full = [(qid, False) for qid in questions]
    if mode == "pilot":
        return [(qid, False) for qid in PILOT_IDS]
    if mode == "run":
        # --run chạy phần CÒN LẠI: pilot đã làm 5 câu rồi.
        return [p for p in full if p[0] not in PILOT_IDS]
    return full  # all / dry-run


def export(
    base: list[dict], meter: UsageMeter, estimate: dict
) -> dict[str, Any]:
    """Assemble ragas_results.json in the style of results_tuan7.json."""
    base = apply_overrides(base)
    summary = summarise(base)
    gen_cost = sum(r["cost_usd"] for r in base)
    judge_measured = meter.calls > 0

    payload = {
        "metadata": {
            "week": 8,
            "date": date.today().isoformat(),
            "reproduce": "python -m src.evaluation --run",
            "judge_model": JUDGE_MODEL,
            "judge_note": (
                "Judge CUNG model voi generator -> co self-preference bias, diem "
                "tuyet doi nen doc rong tay; so sanh giua hai arm van hop le."
            ),
            "judge_embeddings": JUDGE_EMBEDDINGS,
            "prices_usd_per_mtok": {
                "in": PRICE_PER_MTOK_IN,
                "out": PRICE_PER_MTOK_OUT,
                "_note": "Gia CHINH THUC Sonnet 5; dot tang $3/$15 da bi huy.",
            },
            "cache_note": (
                "SYSTEM_PROMPT ~750 token < nguong cache toi thieu 1.024 token cua "
                "Sonnet 5 -> cache_control khong kich hoat, tiet kiem $0."
            ),
        },
        "cau_hinh": {
            "rerank": False,
            "_scope": "toan bo 32 cau o cau hinh CHINH THUC (rerank=False)",
            "n_cham_du_4_chi_so": sum(1 for r in base if r["expected_source_docs"]),
            "n_adversarial": sum(1 for r in base if not r["expected_source_docs"]),
            "_note_rerank": (
                "Nhanh rerank=True KHONG duoc do o day. No van duoc danh gia o tang "
                "retrieval bang Recall@3 trong tests/test_reranking.py va "
                "data/Evaluation/results_tuan7.json."
            ),
        },
        "dieu_chinh_thu_cong": {
            "_note": (
                "Diem da sua tay SAU KHI mo context ra doi chieu va chung minh judge "
                "cham sai. Diem may cham goc van duoc giu trong tung ban ghi o "
                "per_question._dieu_chinh_thu_cong de kiem tra lai."
            ),
            "so_o_da_sua": sum(len(v) for v in MANUAL_OVERRIDES.values()),
            "chi_tiet": MANUAL_OVERRIDES,
        },
        "scores_by_group": summary["scores_by_group"],
        "phat_hien_precision_recall": _precision_recall_gap(base),
        "adversarial": summary["adversarial"],
        "per_question": base,
        "cost": {
            "generation_usd": round(gen_cost, 4),
            "judge_usd": round(meter.usd if judge_measured else estimate["judge"]["usd"], 4),
            "judge_calls": meter.calls,
            "_judge_note": (
                "Do that qua UsageMeter."
                if judge_measured
                else "UOC TINH - instructor khong lo usage ra ngoai."
            ),
            "total_usd": round(
                gen_cost + (meter.usd if judge_measured else estimate["judge"]["usd"]), 4
            ),
        },
        # ket_luan là văn xuôi viết tay, không sinh tự động được. Giữ lại bản cũ nếu
        # file đã có: chạy lại để bổ sung câu thiếu thì không được xóa phần nhận xét.
        "ket_luan": _existing_ket_luan(),
    }
    RESULTS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


if __name__ == "__main__":
    # Console Windows mặc định cp1252, nuốt sạch dấu tiếng Việt trong log lẫn bảng.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="in chi phí rồi dừng (mặc định)")
    mode.add_argument("--pilot", action="store_true", help=f"5 câu: {', '.join(PILOT_IDS)}")
    mode.add_argument("--run", action="store_true", help="phần còn lại của 32 câu")
    mode.add_argument("--all", action="store_true", help="chạy tất cả, bỏ cổng duyệt")
    args = parser.parse_args()

    selected = "pilot" if args.pilot else "run" if args.run else "all" if args.all else "dry"
    plan = build_plan(selected if selected != "dry" else "all")
    questions = load_questions()
    estimate = estimate_cost(plan, questions)

    if selected == "dry":
        print_estimate(estimate, "TOÀN BỘ (32 câu + subset rerank 10 câu)")
        for label in ("pilot", "run"):
            print_estimate(estimate_cost(build_plan(label), questions), f"--{label}")
        print("\nDRY RUN — chưa gọi API lần nào. Chạy --pilot để bắt đầu.")
        sys.exit(0)

    print_estimate(estimate, f"--{selected}")
    meter = UsageMeter()
    asyncio.run(run_evaluation([qid for qid, _rr in plan], rerank=False, meter=meter))

    # Bảng và file kết quả luôn dựng từ TOÀN BỘ store, không chỉ phần vừa chạy —
    # nếu không thì sau --pilot rồi --run, file sẽ thiếu 5 câu của pilot.
    all_base = [r for r in _load_store().values() if not r["rerank"]]

    payload = export(all_base, meter, estimate)
    print_table(summarise(all_base), "RAGAS — cấu hình chính thức (rerank=False)")
    print(f"\nChi phí thật: ${payload['cost']['total_usd']:.4f}")
    print(f"Đã ghi: {RESULTS_PATH}")
