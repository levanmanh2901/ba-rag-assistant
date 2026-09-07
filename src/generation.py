"""Grounded answer generation: retrieved chunks -> Vietnamese answer with citations.

Bước cuối của pipeline. Hai việc, và việc thứ hai mới là việc khó:

1. Trả lời câu hỏi nghiệp vụ bằng tiếng Việt, mỗi thông tin kèm ``[doc_id]``.
2. TỪ CHỐI khi Knowledge Base không có đáp án — bịa một con số lãi suất nguy hiểm
   hơn nhiều so với việc nói "không tìm thấy".

Vì sao ngưỡng điểm KHÔNG phải là cơ chế từ chối: xem :data:`MIN_TOP_SCORE`.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

from src.hybrid_search import hybrid_search
from src.reranking import CANDIDATE_K
from src.vectorstore import CHROMA_DIR

logger = logging.getLogger(__name__)

load_dotenv()  # ANTHROPIC_API_KEY nằm trong .env (đã .gitignore, chưa từng commit)

MODEL = "claude-sonnet-5"

# Giá INTRO của Sonnet 5, hết hạn 2026-08-31; sau mốc đó là $3.00 / $15.00.
# Đổi hai hằng số này khi giá đổi — báo cáo chi phí trong test đọc thẳng từ đây.
PRICE_PER_MTOK_IN = 2.0
PRICE_PER_MTOK_OUT = 10.0

# Thoáng tay: thinking token cũng tính vào max_tokens. Câu trả lời thực tế ~200-400
# token, nhưng cắt giữa chừng thì mất luôn phần trích dẫn ở cuối câu.
MAX_TOKENS = 4000

REFUSAL_MESSAGE = "Không tìm thấy thông tin phù hợp trong Knowledge Base"

# --------------------------------------------------------------------------- #
# Ngưỡng từ chối — ĐỌC KỸ TRƯỚC KHI CHỈNH
# --------------------------------------------------------------------------- #
# Con số này là LƯỚI AN TOÀN CHO INPUT RÁC, KHÔNG phải bộ lọc adversarial.
# Đừng nâng nó lên với hy vọng chặn được câu hỏi bẫy — đã đo, không có tác dụng.
#
# Lý do nằm ở `_normalize_scores`: nhánh BM25 được min-max nên chunk BM25 cao nhất
# trong pool LUÔN được đúng 1.0, dù nó khớp tốt hay tệ. Top-1 gần như luôn là chunk
# đó, nên với alpha=0.5:
#
#     score_top1  ≈  0.5 · 1.0 + 0.5 · cosine  =  0.5 + 0.5 · cosine
#
# Kiểm chứng trên index thật: Q005 0.5+0.5·0.032=0.516 ✓, Q029 0.5+0.5·0.186=0.593 ✓,
# Q031 0.5+0.5·0.464=0.732≈0.730 ✓. Tức là điểm có SÀN CỨNG ~0.5 và phần biến thiên
# chỉ là cosine — mà cosine chồng lấn nặng giữa hai nhóm (adversarial 0.186–0.464,
# hợp lệ 0.032–0.706).
#
# Phân bố top-1 đo trên toàn bộ 32 câu evaluation:
#     adversarial (4 câu) : 0.593 · 0.652 · 0.663 · 0.730
#     hợp lệ     (28 câu) : 0.516 · 0.657 · 0.678 · 0.685 · 0.707 ... 0.853
#
# Đánh đổi khi nâng ngưỡng:
#     0.45  -> chặn oan  0/28,  bắt adversarial 0/4
#     0.60  -> chặn oan  1/28,  bắt adversarial 1/4
#     0.67  -> chặn oan  2/28,  bắt adversarial 3/4
#     0.731 -> chặn oan 12/28,  bắt adversarial 4/4   (hỏng hệ thống)
#
# Lập luận quyết định: "What is the capital of France?" được 0.525, CAO HƠN câu hợp lệ
# thấp nhất là Q005 "Float Balance nghĩa là gì?" (0.516). Không tồn tại ngưỡng nào chặn
# được câu hỏi về thủ đô nước Pháp mà không giết luôn Q005. Và ở 0.67, các câu ngoài
# phạm vi nghe-giống-fintech vẫn lọt hết (SWIFT 0.718, cashback VIP 0.706) — đúng loại
# câu người dùng thật sẽ hỏi.
#
# Nên gate chỉ giữ đúng một việc: chặn regime "không token nào khớp corpus" (BM25 toàn
# 0 -> min-max trả 0 hết -> mất luôn sàn 0.5; ví dụ "aaaa bbbb cccc dddd" = 0.203).
# 0.45 nằm dưới giá trị hợp lệ thấp nhất đã đo 0.066 (~13% đệm) và trên regime đó.
#
# Việc từ chối câu adversarial giao HOÀN TOÀN cho LLM qua SYSTEM_PROMPT — tầng duy nhất
# ĐỌC ĐƯỢC nội dung chunk. Điểm số chỉ biết chunk "gần về ngữ nghĩa", không biết chunk
# có CHỨA đáp án hay không: đúng cùng điểm mù đã sinh ra bước hybrid ở Tuần 5.
MIN_TOP_SCORE = 0.45


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = f"""\
Bạn là trợ lý tra cứu tài liệu nghiệp vụ nội bộ của ManhPay (ví điện tử), phục vụ BA/PO.

Bạn nhận được một số đoạn trích (CONTEXT) lấy từ Knowledge Base. Trả lời câu hỏi CHỈ dựa
trên CONTEXT đó, theo đúng 6 quy tắc sau:

1. CHỈ DÙNG CONTEXT. Không dùng kiến thức chung của bạn về ví điện tử, ngân hàng, hay quy
   định pháp luật Việt Nam. Nếu CONTEXT không nói, coi như bạn không biết.

2. TRÍCH DẪN BẮT BUỘC. Mỗi thông tin phải kèm doc_id trong ngoặc vuông ngay sau câu chứa
   nó, ví dụ: "Hạn mức là 20.000.000 VNĐ mỗi ngày [BR-002]." Nhiều nguồn thì viết liền
   [BR-002][BRD-002]. Chỉ được dùng doc_id CÓ THẬT trong CONTEXT — tuyệt đối không bịa mã
   tài liệu.

3. TỪ CHỐI KHI KHÔNG ĐỦ CĂN CỨ. Nếu CONTEXT không chứa đủ thông tin để trả lời, câu trả
   lời của bạn PHẢI bắt đầu bằng đúng nguyên văn câu này:
   "{REFUSAL_MESSAGE}"
   rồi nói ngắn gọn bạn đã tìm thấy gì gần đúng (nếu có). Không suy đoán, không ước lượng,
   không dùng các cách nói như "thông thường", "có thể là", "theo quy định chung".

4. "ĐƯỢC NHẮC TỚI" KHÁC "CÓ NỘI DUNG". Một tài liệu tham chiếu tới tài liệu khác không
   khiến tài liệu đó có mặt trong Knowledge Base. Nếu CONTEXT chỉ nhắc TÊN một tài liệu mà
   không có nội dung của nó, bạn phải từ chối theo quy tắc 3 và nói rõ tài liệu đích không
   nằm trong Knowledge Base hiện tại.

5. TIỀN ĐỀ SAI. Nếu câu hỏi giả định một thực thể mà CONTEXT không có (một cấp bậc, một
   sản phẩm, một loại tài khoản không tồn tại), hãy nói thẳng rằng thực thể đó không xuất
   hiện trong tài liệu, và liệt kê những thứ CÓ thật trong CONTEXT. Tuyệt đối KHÔNG suy
   diễn giá trị cho thực thể không tồn tại.

6. SỐ LIỆU SAO CHÉP NGUYÊN VĂN từ CONTEXT, giữ nguyên định dạng (ví dụ "20.000.000 VNĐ",
   "85%", "T+1"). Không tự tính toán, không cộng trừ, không đổi đơn vị.

Trả lời bằng tiếng Việt, ngắn gọn, đi thẳng vào câu hỏi."""


def _build_context(hits: list[dict[str, Any]]) -> str:
    """Render hits as numbered source blocks for the prompt.

    ``content`` đã mang sẵn header provenance do :func:`src.chunking._context_header`
    chèn ("Tài liệu: ... (doc_id, doc_type, module, version)" + "Mục: heading_path"),
    nên ở đây KHÔNG lặp lại mấy trường đó — chỉ thêm ``doc_id`` ở dạng đúng cú pháp
    trích dẫn ta muốn model dùng, và ``status`` (trường duy nhất header không có).
    """
    blocks = []
    for rank, hit in enumerate(hits, start=1):
        meta = hit["metadata"]
        blocks.append(
            f"--- NGUỒN {rank} | doc_id: {meta['doc_id']} | status: {meta.get('status', '?')} ---\n"
            f"{hit['content']}"
        )
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------- #
# Trích dẫn
# --------------------------------------------------------------------------- #
# Khớp dạng mã tài liệu của KB: BR-002, BRD-002, SOP-002, FEE-001, LIMIT-001,
# US-EPIC-014, CR-LOG-001, và bản cũ BR-002-v1.
_DOC_CODE_RE = re.compile(r"\b[A-Z]{2,}(?:-[A-Z]+)*-\d+(?:-v\d+)?\b")


def _extract_citations(answer: str, hits: list[dict[str, Any]]) -> list[str]:
    """Doc ids the answer actually cites, in order of first appearance.

    Whitelist chứ không phải regex tự do: chỉ chấp nhận doc_id CÓ trong ``hits``.
    Mã nào có dạng tài liệu nhưng không thuộc context thì bị loại và ghi log — đó là
    dấu hiệu model bịa nguồn, thứ cần thấy được chứ không nên nuốt im lặng.

    Lookahead ``(?![\\w-])`` là bắt buộc: không có nó thì ``BR-002`` khớp nhầm vào bên
    trong ``BR-002-v1``, và một câu trả lời trích bản Deprecated sẽ bị ghi nhận thành
    trích bản Approved — sai hoàn toàn im lặng, đúng thứ nhóm version_conflict để bắt.
    """
    in_context = {hit["metadata"]["doc_id"] for hit in hits}

    found: list[tuple[int, str]] = []
    for doc_id in in_context:
        match = re.search(rf"{re.escape(doc_id)}(?![\w-])", answer)
        if match:
            found.append((match.start(), doc_id))
    found.sort()
    cited = [doc_id for _, doc_id in found]

    fabricated = {code for code in _DOC_CODE_RE.findall(answer) if code not in in_context}
    if fabricated:
        logger.warning(
            "Câu trả lời trích mã tài liệu KHÔNG có trong context: %s — dấu hiệu bịa nguồn.",
            sorted(fabricated),
        )
    return cited


# --------------------------------------------------------------------------- #
# Kết quả
# --------------------------------------------------------------------------- #
@dataclass
class GenerationResult:
    """One answered (or refused) question, with the cost of answering it."""

    answer: str
    cited_doc_ids: list[str] = field(default_factory=list)
    # None nghĩa là CHƯA GỌI model nào (bị gate chặn), khác hẳn với "gọi mà tốn 0 token".
    model_used: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    refused: bool = False
    retrieved_doc_ids: list[str] = field(default_factory=list)
    # Context đã qua cross-encoder hay chưa — cần để đối chiếu khi so kết quả
    # giữa hai chế độ, vì answer không mang dấu vết nào của bước retrieval.
    reranked: bool = False

    @property
    def cost_usd(self) -> float:
        """Estimated cost of this call at the prices in this module."""
        return (
            self.input_tokens * PRICE_PER_MTOK_IN
            + self.output_tokens * PRICE_PER_MTOK_OUT
        ) / 1_000_000


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    """The shared Anthropic client, created on first use.

    Khởi tạo lười chứ không phải ở module level: import ``src.generation`` không được
    nổ khi thiếu ANTHROPIC_API_KEY, nếu không thì mọi test offline (gate, trích dẫn)
    đều chết theo dù chúng không cần API.
    """
    global _client
    if _client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "Thiếu ANTHROPIC_API_KEY — đặt trong file .env ở gốc project."
            )
        _client = anthropic.Anthropic()
    return _client


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def generate_answer(
    question: str,
    top_k: int = 5,
    filters: dict[str, Any] | None = None,
    include_deprecated: bool = False,
    min_score: float = MIN_TOP_SCORE,
    rerank: bool = False,
    candidate_k: int = CANDIDATE_K,
    persist_dir: Path | str = CHROMA_DIR,
) -> GenerationResult:
    """Answer ``question`` from the knowledge base, with citations, or refuse.

    ``include_deprecated=True`` cho câu hỏi lịch sử (Q028: "trước đây hạn mức Tier 3 là
    bao nhiêu"), ở đó bản Deprecated LẠI là nguồn hợp lệ.

    Khi ``hits[0]["score"] < min_score`` thì trả :data:`REFUSAL_MESSAGE` NGAY, không gọi
    API — xem :data:`MIN_TOP_SCORE` để biết gate này làm gì và (quan trọng hơn) KHÔNG
    làm gì.

    ``rerank=True`` lấy ``candidate_k`` ứng viên rồi cho cross-encoder chọn lại
    ``top_k`` cuối cùng (xem :mod:`src.reranking`). MẶC ĐỊNH TẮT: mọi con số đã
    đo ở Tuần 5-6 — phân bố điểm top-1, ngưỡng 0.45, 4/4 câu adversarial bị từ
    chối — đều đo ở chế độ không rerank, nên bật mặc định sẽ làm chúng hết hiệu
    lực cùng lúc. Bật lên sau khi ``tests/test_reranking.py`` chứng minh không
    nhóm nào tụt hạng.

    THỨ TỰ QUAN TRỌNG: gate chạy TRƯỚC rerank. Vì :func:`hybrid_search` sắp xếp
    rồi mới cắt ``top_k``, điểm top-1 giống hệt nhau dù lấy 5 hay ``candidate_k``
    ứng viên — nên gate hoạt động y nguyên như Tuần 6 ở cả hai chế độ. Gate sau
    rerank thì hỏng: cross-encoder có thể đưa lên đầu một chunk có điểm hybrid
    thấp hơn, và ngưỡng 0.45 (hiệu chỉnh trên thang hybrid) sẽ chặn oan.
    """
    hits = hybrid_search(
        question,
        filters=filters,
        top_k=candidate_k if rerank else top_k,
        include_deprecated=include_deprecated,
        persist_dir=persist_dir,
    )

    if not hits or hits[0]["score"] < min_score:
        top = hits[0]["score"] if hits else 0.0
        logger.info(
            "Gate chặn trước LLM: điểm top-1 %.3f < %.2f — không gọi API.", top, min_score
        )
        return GenerationResult(answer=REFUSAL_MESSAGE, refused=True)

    if rerank:
        from src.reranking import rerank as rerank_hits

        hits = rerank_hits(question, hits, top_k=top_k)

    retrieved = list(dict.fromkeys(hit["metadata"]["doc_id"] for hit in hits))

    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"CONTEXT:\n\n{_build_context(hits)}\n\nCÂU HỎI: {question}",
            }
        ],
        # Sonnet 5 KHÔNG nhận temperature/top_p/budget_tokens (trả 400) và không cho
        # prefill. Adaptive thinking giữ lại vì phán đoán "context có đủ căn cứ không"
        # mới là việc khó nhất ở đây; effort low vì phần còn lại chỉ là trích xuất.
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},
    )

    if response.stop_reason == "max_tokens":
        logger.warning(
            "Câu trả lời bị cắt vì chạm max_tokens=%d — phần trích dẫn cuối câu có thể mất.",
            MAX_TOKENS,
        )

    answer = "\n".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    return GenerationResult(
        answer=answer,
        cited_doc_ids=_extract_citations(answer, hits),
        model_used=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        refused=REFUSAL_MESSAGE in answer,
        retrieved_doc_ids=retrieved,
        reranked=rerank,
    )


if __name__ == "__main__":
    import sys

    # Console Windows mặc định là cp1252, không in được tiếng Việt.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    samples = [
        ("Q001 (hợp lệ)", "Hạn mức chuyển tiền P2P mỗi ngày của tài khoản Tier 2 là bao nhiêu?"),
        ("Q031 (adversarial)", "Hạn mức giao dịch của tài khoản Tier 4 là bao nhiêu?"),
        ("rác (gate chặn)", "aaaa bbbb cccc dddd"),
    ]

    total = 0.0
    for label, question in samples:
        result = generate_answer(question)
        total += result.cost_usd
        print(f"\n{'=' * 78}\n### {label}: {question}\n{'=' * 78}")
        print(result.answer)
        print(f"\n  trích dẫn : {result.cited_doc_ids}")
        print(f"  truy hồi  : {result.retrieved_doc_ids}")
        print(f"  từ chối   : {result.refused}")
        print(
            f"  model     : {result.model_used or '— (gate chặn, không gọi API)'}"
            f"  |  {result.input_tokens} in / {result.output_tokens} out"
            f"  |  ${result.cost_usd:.6f}"
        )

    print(f"\n{'=' * 78}\nTổng chi phí: ${total:.6f}")
