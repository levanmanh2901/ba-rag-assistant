"""Streamlit demo UI for the ManhPay RAG assistant.

Chạy: ``streamlit run app.py`` (đã kích hoạt venv).

Giao diện gọi ĐÚNG MỘT hàm của pipeline: :func:`src.generation.generate_answer`.
Mọi thứ khác ở đây chỉ là trình bày — không có logic truy hồi riêng, để UI không
bao giờ hiển thị một tập chunk khác với tập đã thật sự gửi cho mô hình.

KHÔNG BAO GIỜ gọi ``build_index()`` hay ``get_collection(reset=True)`` từ file
này — xem cảnh báo ở :func:`src.vectorstore.get_collection`: process Streamlit
sống lâu và giữ file handle vào HNSW, nên ``rmtree`` sẽ ném WinError 32, còn
client "mới" lại là object lấy từ cache trỏ vào thư mục vừa bị xóa. Index phải
build từ CLI: ``python -m src.vectorstore``.
"""

from __future__ import annotations

import html
import json
import logging
import os
import random
from typing import Any

import anthropic
import streamlit as st

from src.generation import (
    MIN_TOP_SCORE,
    GenerationResult,
    generate_answer,
)
from src.vectorstore import CHROMA_DIR, COLLECTION_NAME, PROJECT_ROOT

logger = logging.getLogger(__name__)

EVAL_PATH = PROJECT_ROOT / "data" / "Evaluation" / "evaluation_questions.json"
CATALOG_PATH = PROJECT_ROOT / "data" / "metadata_catalog.json"

MAX_QUESTION_CHARS = 1000

# Chỉ áp dụng khi in / lưu PDF (Ctrl+P). Không có nó thì: sidebar chiếm 1/3 trang,
# nhãn nút có thể gãy dòng, và nền tối của dark mode bị in ra (Streamlit bật
# print-color-adjust: exact).
PRINT_CSS = """
<style>
@media print {
  html { font-size: 14px; }
  [data-testid='stSidebar'], [data-testid='stHeader'] { display: none !important; }
  [data-testid='stMain'], [data-testid='stMainBlockContainer'] {
    margin: 0 !important; padding: 0 !important;
    max-width: 100% !important; width: 100% !important;
  }
  html, body, .stApp, [data-testid='stAppViewContainer'], [data-testid='stMain'],
  [data-testid='stMain'] * {
    background: #fff !important; color: #111 !important;
  }
  [data-testid='stMain'] textarea, [data-testid='stButton'] button,
  [data-testid='stAlert'] { border: 1px solid #999 !important; }
  [data-testid='stButton'] button, [data-testid='stButton'] p { white-space: nowrap !important; }
  [data-testid='stExpander'], [data-testid='stAlert'] { break-inside: avoid; }
}
</style>
"""

# Dòng chi phí nằm dưới khối trích dẫn, căn sát mép phải và trên MỘT dòng. Cột
# [3, 2] cũ quá hẹp nên chuỗi gãy làm hai dòng và lệch khỏi mép phải.
COST_CSS = """
<style>
.manhpay-cost {
  text-align: right; white-space: nowrap;
  font-size: 0.85rem; opacity: 0.7; margin-top: 0.5rem;
}
</style>
"""

PLACEHOLDER ="Ví dụ: Hạn mức chuyển tiền P2P mỗi ngày của tài khoản Tier 2 là bao nhiêu?"

# Chiều rộng chung (px) của hai nút "Hỏi" và "Thử câu hỏi mẫu" để chúng bằng nhau.
BUTTON_WIDTH = 240


# --------------------------------------------------------------------------- #
# Tài nguyên nặng — nạp một lần, dùng lại qua mọi lần rerun
# --------------------------------------------------------------------------- #
# Ba tài nguyên dưới đây vốn ĐÃ có singleton riêng (`embedding._model`,
# `bm25_retriever._INDEX_CACHE`, `SharedSystemClient` của Chroma), và `sys.modules`
# sống sót qua các lần rerun của Streamlit — nên nghiêm ngặt mà nói chúng cũng
# không bị nạp lại. `@st.cache_resource` mua thêm ba thứ: spinner ở lần nạp đầu,
# một điểm làm nóng tường minh (gọi hết ở đầu main), và tính đúng đắn nếu Streamlit
# đổi sang chạy script trong interpreter mới.
@st.cache_resource(show_spinner="Đang mở Knowledge Base (ChromaDB)...")
def load_collection():
    """The persistent Chroma collection. ``reset=False``, always."""
    from src.vectorstore import get_collection

    return get_collection(CHROMA_DIR)


@st.cache_resource(show_spinner="Đang nạp model embedding (~470MB, chỉ lần đầu)...")
def load_embedding_model():
    """Warm the sentence-transformers singleton so the first question isn't slow."""
    from src.embedding import get_model

    return get_model()


@st.cache_resource(show_spinner="Đang dựng chỉ mục BM25...")
def load_bm25_index():
    """Warm the BM25 index. ``refresh=False`` — đừng tokenize lại 127 chunk mỗi rerun."""
    from src.bm25_retriever import get_index

    return get_index(CHROMA_DIR)


@st.cache_data
def load_sample_questions() -> list[dict[str, Any]]:
    """The 32 evaluation questions, for the "thử câu hỏi mẫu" button."""
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))["questions"]


@st.cache_data
def load_filter_options() -> tuple[list[str], list[str]]:
    """Distinct module / doc_type values, read from the catalog.

    Đọc catalog chứ không hardcode 12 module + 11 doc_type: hardcode thì thêm tài
    liệu mới là dropdown âm thầm thiếu lựa chọn, không có lỗi nào báo.
    """
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return (
        sorted({entry["module"] for entry in catalog}),
        sorted({entry["doc_type"] for entry in catalog}),
    )


# --------------------------------------------------------------------------- #
# Hàm thuần — không chạm Streamlit, đây là phần tests/test_app.py bám vào
# --------------------------------------------------------------------------- #
def build_filters(
    modules: list[str] | None, doc_types: list[str] | None
) -> dict[str, Any] | None:
    """Map the sidebar selections onto the filter dict ``hybrid_search`` expects.

    List -> ``$in`` do :func:`src.vectorstore._build_where` tự bọc; nhiều khóa ->
    ``$and``.

    BẮT BUỘC bỏ hẳn khóa khi không chọn gì. ``{"module": {"$in": []}}`` làm
    ``allowed_ids`` rỗng -> ``hybrid_search`` trả ``[]`` -> gate chặn với điểm
    0.0, trông y hệt "câu hỏi ngoài phạm vi" trong khi thật ra là bộ lọc vừa quét
    sạch corpus. Người demo sẽ đổ lỗi cho retrieval thay vì cho cái dropdown.

    KHÔNG đụng tới khóa ``status``: :func:`src.hybrid_search._resolve_filters` tự
    chèn ``$nin Deprecated``, và truyền tay một khóa ``status`` sẽ ghi đè mặc
    định đó.
    """
    filters: dict[str, Any] = {}
    if modules:
        filters["module"] = list(modules)
    if doc_types:
        filters["doc_type"] = list(doc_types)
    return filters or None


def classify_result(result: GenerationResult) -> str:
    """Which of the three outcomes this is: ``gate`` / ``llm_refusal`` / ``answer``.

    Phân biệt bằng ``model_used is None``, KHÔNG bằng ``refused``: CẢ HAI kiểu từ
    chối đều có ``refused=True``, nên rẽ nhánh theo nó là gộp hai trạng thái
    khác hẳn nhau làm một. ``model_used`` mới là tín hiệu "chưa gọi model nào"
    (xem comment ở src/generation.py, chỗ khai báo field).

    * ``gate``        — điểm top-1 dưới ngưỡng, CHƯA gọi API, không tốn tiền.
    * ``llm_refusal`` — đã gọi API, có context, nhưng model nói không đủ căn cứ.
    * ``answer``      — trả lời bình thường.
    """
    if result.model_used is None:
        return "gate"
    return "llm_refusal" if result.refused else "answer"


def strip_context_header(text: str) -> str:
    """Drop the provenance header; the expander title already shows those fields.

    Header do :func:`src.chunking._context_header` chèn là 1-2 dòng rồi một dòng
    trống. Không khớp đúng hình dạng đó thì trả nguyên văn — thà để thừa header
    còn hơn cắt nhầm mất nội dung.
    """
    head, separator, body = text.partition("\n\n")
    if separator and head.startswith("Tài liệu:"):
        return body
    return text


def group_contexts_by_doc(result: GenerationResult) -> list[dict[str, Any]]:
    """Group the chunks sent to the LLM by ``doc_id`` — cited documents first.

    Đây là chỗ ba danh sách gặp nhau mà chỉ HAI trong số đó song song:
    ``contexts[i]`` <-> ``context_meta[i]`` (cùng dựng từ một list ``hits``), còn
    ``cited_doc_ids`` là TẬP CON các doc_id thật sự xuất hiện trong câu trả lời,
    xếp theo lần xuất hiện đầu tiên. Một tài liệu có thể đóng góp NHIỀU chunk,
    nên phải gom nhóm chứ không zip 1-1 với cited_doc_ids.
    """
    by_doc: dict[str, dict[str, Any]] = {}
    for text, meta in zip(result.contexts, result.context_meta):
        entry = by_doc.setdefault(
            meta["doc_id"],
            {
                "doc_id": meta["doc_id"],
                "meta": meta,
                "chunks": [],
                "best_score": 0.0,
                "cited": False,
                "cite_rank": None,
            },
        )
        entry["chunks"].append({"text": text, "meta": meta})
        entry["best_score"] = max(entry["best_score"], meta.get("score") or 0.0)

    for rank, doc_id in enumerate(result.cited_doc_ids, start=1):
        # `if` là bắt buộc: _extract_citations lọc theo whitelist context nên
        # thường khớp, nhưng UI không được nổ nếu tầng dưới đổi cách lọc.
        if doc_id in by_doc:
            by_doc[doc_id]["cited"] = True
            by_doc[doc_id]["cite_rank"] = rank

    cited = [by_doc[doc_id] for doc_id in result.cited_doc_ids if doc_id in by_doc]
    rest = [entry for entry in by_doc.values() if not entry["cited"]]
    rest.sort(key=lambda entry: entry["best_score"], reverse=True)
    return cited + rest


def format_cost(result: GenerationResult) -> str:
    """One-line cost caption for the question just asked.

    Nhánh gate nói rõ "$0 vì chưa gọi API" thay vì chỉ in số 0 — đúng ngữ nghĩa
    ``model_used=None``, và là chỗ thứ hai trong UI phân biệt hai kiểu từ chối.
    ``≈`` vì ``cost_usd`` là ước tính theo giá hardcode trong src/generation.py.
    """
    if classify_result(result) == "gate":
        return "💵 $0.000000 — gate chặn trước LLM, không gọi API"
    suffix = " · đã rerank" if result.reranked else ""
    return (
        f"💵 ≈${result.cost_usd:.6f} · {result.input_tokens:,} token vào / "
        f"{result.output_tokens:,} ra · {result.model_used}{suffix}"
    )


# --------------------------------------------------------------------------- #
# Tiền đề
# --------------------------------------------------------------------------- #
def preflight() -> tuple[int | None, str | None]:
    """Check the knowledge base is usable. Returns ``(chunk_count, error)``.

    KHÔNG build gì cả — chỉ đọc. Xem cảnh báo ở đầu module.
    """
    build_hint = (
        "Mở terminal (đã kích hoạt venv) rồi chạy:\n\n"
        "```\npython -m src.vectorstore\n```\n\n"
        "Lệnh này build index rồi thoát. **Đừng build từ trong app** — process "
        "Streamlit giữ file handle vào HNSW nên sẽ hỏng index."
    )

    if not CHROMA_DIR.exists():
        return None, f"Chưa có Knowledge Base tại `{CHROMA_DIR}`.\n\n{build_hint}"

    try:
        count = load_collection().count()
    except Exception as exc:  # noqa: BLE001 — biên UI, phải hiện lỗi chứ không sập
        logger.exception("Không mở được ChromaDB")
        return None, (
            f"Không mở được ChromaDB: `{type(exc).__name__}: {exc}`\n\n{build_hint}"
        )

    if count == 0:
        return None, f"Collection `{COLLECTION_NAME}` rỗng (0 chunk).\n\n{build_hint}"
    return count, None


# --------------------------------------------------------------------------- #
# Gọi pipeline
# --------------------------------------------------------------------------- #
def run_query(question: str, **kwargs: Any) -> tuple[GenerationResult | None, str | None]:
    """Call ``generate_answer``, turning every known failure into Vietnamese copy.

    THỨ TỰ ``except`` KHÔNG ĐƯỢC ĐỔI: ``AuthenticationError``,
    ``PermissionDeniedError``, ``RateLimitError`` và ``BadRequestError`` đều là
    con của ``APIStatusError``; đặt lớp cha lên trước là nuốt sạch các nhánh con
    và chỉ còn đúng một thông báo chung vô dụng. ``APITimeoutError`` là con của
    ``APIConnectionError`` nên đã được gộp sẵn.
    """
    try:
        return generate_answer(question, **kwargs), None

    except RuntimeError as exc:
        # Chỉ đúng cái _get_client ném ra khi thiếu key. RuntimeError khác (torch,
        # chroma) phải để nổ tiếp — che nó đi là giấu mất lỗi thật.
        if "ANTHROPIC_API_KEY" not in str(exc):
            raise
        return None, (
            f"{exc}\n\nTạo file `.env` ở gốc project với dòng "
            "`ANTHROPIC_API_KEY=sk-ant-...` rồi **khởi động lại app** — "
            "`load_dotenv()` chỉ chạy một lần lúc import `src.generation`."
        )
    except anthropic.AuthenticationError:
        return None, (
            "API key không hợp lệ hoặc đã bị thu hồi (HTTP 401). Kiểm tra lại "
            "`ANTHROPIC_API_KEY` trong `.env`, rồi khởi động lại app."
        )
    except anthropic.PermissionDeniedError:
        return None, (
            "API key không có quyền dùng model `claude-sonnet-5` (HTTP 403). "
            "Kiểm tra quyền của key trong Anthropic Console."
        )
    except anthropic.RateLimitError:
        return None, (
            "Đã chạm giới hạn tốc độ của Anthropic API (HTTP 429). Chờ vài giây "
            "rồi hỏi lại — câu hỏi vẫn còn trong ô nhập."
        )
    except anthropic.BadRequestError as exc:
        return None, (
            f"Anthropic API từ chối request (HTTP 400): {exc}\n\nThường là do tham "
            "số model không hợp lệ trong `src/generation.py`."
        )
    except anthropic.APIConnectionError:
        return None, (
            "Không kết nối được tới Anthropic API. Kiểm tra mạng/proxy/VPN rồi thử lại."
        )
    except anthropic.APIStatusError as exc:
        return None, (
            f"Anthropic API trả lỗi HTTP {exc.status_code}. Thử lại sau ít phút; "
            "nếu lặp lại, xem status.anthropic.com."
        )
    except Exception as exc:  # noqa: BLE001
        # Lưới cuối ở BIÊN của UI: yêu cầu là app không được sập. Traceback đầy đủ
        # vẫn đi ra terminal qua logger.exception nên không nuốt gì cả.
        logger.exception("Lỗi không lường trước khi trả lời câu hỏi")
        return None, (
            f"Lỗi không lường trước: `{type(exc).__name__}: {exc}`\n\nXem log ở "
            "terminal đang chạy `streamlit run` để biết chi tiết."
        )


# --------------------------------------------------------------------------- #
# Trạng thái phiên
# --------------------------------------------------------------------------- #
def init_state() -> None:
    """Declare every session_state key in one place."""
    defaults: dict[str, Any] = {
        "question_text": "",  # gắn với widget st.text_area(key=...)
        "pending_question": None,  # câu đã nhận, chờ chạy ở lượt in-flight
        "running": False,
        "result": None,
        "asked_question": "",  # câu hỏi đã sinh ra `result`
        "error": None,
        "sample_meta": None,
        "last_sample_id": None,
        "session_cost": 0.0,
        "n_queries": 0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def on_sample_click() -> None:
    """Callback: load a random evaluation question into the input box.

    PHẢI là callback ``on_click``, không phải thân ``if st.button(...)``. Callback
    chạy TRƯỚC khi script rerun dựng lại widget, nên gán vào
    ``st.session_state.question_text`` là hợp lệ; gán sau khi
    ``st.text_area(key="question_text")`` đã render trong cùng một lượt sẽ ném
    ``StreamlitAPIException`` ("cannot be modified after the widget is
    instantiated"). Dùng callback thì cũng không cần gọi ``st.rerun()`` tay.
    """
    questions = load_sample_questions()
    # Loại câu vừa bốc lần trước để demo không ra trùng hai lần liên tiếp.
    pool = [q for q in questions if q["id"] != st.session_state.last_sample_id] or questions
    sample = random.choice(pool)

    st.session_state.question_text = sample["question"]
    st.session_state.last_sample_id = sample["id"]
    st.session_state.sample_meta = {
        "id": sample["id"],
        "group": sample["group"],
        "question": sample["question"],
        "ground_truth": sample.get("ground_truth", ""),
    }
    st.session_state.result = None
    st.session_state.error = None


def on_clear_click() -> None:
    """Callback: clear the input box and the last result."""
    st.session_state.question_text = ""
    st.session_state.result = None
    st.session_state.error = None
    st.session_state.asked_question = ""
    st.session_state.sample_meta = None


# --------------------------------------------------------------------------- #
# Hiển thị
# --------------------------------------------------------------------------- #
def render_chunk(chunk: dict[str, Any]) -> None:
    """One retrieved chunk: its scores, then its text."""
    meta = chunk["meta"]
    bits = [
        meta.get("heading_path") or "(không có heading)",
        str(meta.get("chunk_id") or ""),
        f"vector {meta.get('vector_score', 0.0):.3f}",
        f"bm25 {meta.get('bm25_score', 0.0):.2f}",
    ]
    if meta.get("table_boost"):
        bits.append(f"+boost bảng {meta['table_boost']:.2f}")
    if meta.get("rerank_score") is not None:
        bits.append(f"rerank {meta['rerank_score']:.2f}")

    st.caption(" · ".join(bit for bit in bits if bit))
    st.markdown(strip_context_header(chunk["text"]))


def doc_label(entry: dict[str, Any]) -> str:
    """Expander title for one source document."""
    meta = entry["meta"]
    prefix = "🚫 " if meta.get("status") == "Deprecated" else ""
    parts = [
        f"{prefix}[{entry['doc_id']}]",
        str(meta.get("doc_type") or "?"),
        f"module {meta.get('module') or '?'}",
        f"v{meta.get('version') or '?'}",
    ]
    return f"{' · '.join(parts)} — điểm {entry['best_score']:.3f}"


def render_sources(result: GenerationResult, refused: bool = False) -> None:
    """The citation panel: cited documents first, then the rest of the context."""
    if len(result.contexts) != len(result.context_meta):
        # Bất biến vỡ -> báo to rồi đổ nguyên văn. TUYỆT ĐỐI không đoán doc_id:
        # gán nhầm nguồn cho một con số là đúng thứ cả hệ thống này sinh ra để tránh.
        st.warning(
            "Số context và số metadata không khớp — hiển thị nguyên văn, không nhóm "
            "theo tài liệu. (Dấu hiệu `src/generation.py` bị sửa lệch bất biến.)"
        )
        for text in result.contexts:
            st.markdown(text)
        return

    groups = group_contexts_by_doc(result)
    cited = [entry for entry in groups if entry["cited"]]
    others = [entry for entry in groups if not entry["cited"]]

    if cited:
        st.subheader(f"Nguồn trích dẫn ({len(cited)})")
        st.caption("Bấm để mở trích đoạn gốc mà câu trả lời dựa vào.")
        for position, entry in enumerate(cited):
            with st.expander(doc_label(entry), expanded=(position == 0)):
                for chunk in entry["chunks"]:
                    render_chunk(chunk)

    if others:
        # Khi model từ chối thì KHÔNG có nguồn nào được trích dẫn, nên panel này
        # là panel nguồn duy nhất: mở sẵn và đặt tên theo đúng ngữ cảnh, để người
        # xem tự kiểm chứng là hệ thống từ chối đúng chứ không phải retrieval hỏng.
        sole_panel = refused and not cited
        if sole_panel:
            title = f"Đoạn đã truy hồi — không đoạn nào chứa đáp án ({len(others)})"
            hint = (
                "Đây là toàn bộ những gì mô hình được đọc. Không đoạn nào trả lời "
                "được câu hỏi, nên nó từ chối thay vì suy đoán."
            )
        else:
            title = f"Đoạn đã truy hồi nhưng KHÔNG được trích dẫn ({len(others)})"
            hint = (
                "Những đoạn này đã được gửi cho mô hình nhưng không đi vào câu trả "
                "lời — xem ở đây để biết retrieval trượt chỗ nào."
            )
        with st.expander(title, expanded=sole_panel):
            st.caption(hint)
            for entry in others:
                # Streamlit KHÔNG cho lồng expander trong expander -> cấp hai dùng
                # container có viền.
                with st.container(border=True):
                    st.markdown(f"**{doc_label(entry)}**")
                    for chunk in entry["chunks"]:
                        render_chunk(chunk)


def render_result(result: GenerationResult, filters_active: bool) -> None:
    """Render the answer, visually distinct per outcome."""
    kind = classify_result(result)

    if kind == "gate":
        message = (
            "**🚫 Câu hỏi nằm ngoài phạm vi Knowledge Base**\n\n"
            "Không có đoạn tài liệu nào đủ liên quan để trả lời — điểm khớp cao "
            f"nhất nằm dưới ngưỡng {MIN_TOP_SCORE:.2f}. Hệ thống đã dừng **trước "
            "khi gọi mô hình**, nên lượt hỏi này không tốn chi phí.\n\n"
            "Thử diễn đạt lại bằng từ ngữ có trong tài liệu (\"hạn mức\", \"phí\", "
            "\"đối soát\", \"eKYC\", \"khiếu nại\")."
        )
        if filters_active:
            message += (
                "\n\n⚠️ Bộ lọc ở thanh bên đang bật — rất có thể chính nó đã loại "
                "hết tài liệu liên quan. Thử bỏ bớt bộ lọc."
            )
        st.error(message)
        return  # gate chặn -> contexts rỗng, không có nguồn để hiện

    if kind == "llm_refusal":
        st.warning(
            "**⚠️ Không đủ căn cứ trong Knowledge Base**\n\n"
            "Đã tìm thấy tài liệu liên quan nhưng không tài liệu nào chứa đáp án. "
            "Đây là hành vi **đúng**: thà nói không biết còn hơn bịa một con số."
        )
        st.markdown(result.answer)  # model tự nói nó tìm thấy gì gần đúng
    else:
        st.markdown(result.answer)
        st.caption(f"✅ Đã trả lời · {len(result.cited_doc_ids)} nguồn được trích dẫn")

    render_sources(result, refused=(kind == "llm_refusal"))


# --------------------------------------------------------------------------- #
# Giao diện
# --------------------------------------------------------------------------- #
def main() -> None:  # noqa: PLR0915 — một trang Streamlit, tách nhỏ sẽ rối hơn
    """Draw the whole page. Streamlit chạy lại hàm này sau mỗi tương tác."""
    st.set_page_config(page_title="ManhPay RAG Assistant", page_icon="💬", layout="wide")
    # Tăng cỡ chữ bằng CSS thay vì [theme] baseFontSize trong config.toml: khai báo
    # [theme] biến app thành "Custom Theme" và mất nút chuyển Light/Dark.
    # Caption mặc định vừa nhỏ vừa nhạt mà app dùng cho nhiều ghi chú cần đọc
    # (giải thích bộ lọc, trạng thái trả lời, chi phí) nên nới lên gần bằng chữ thường.
    st.html(
        "<style>"
        "html { font-size: 20px; }"
        "[data-testid='stCaptionContainer'] { font-size: 0.95rem; }"
        "</style>"
    )
    st.html(PRINT_CSS)
    st.html(COST_CSS)
    init_state()

    chunk_count, preflight_error = preflight()
    if preflight_error:
        st.title("💬 ManhPay RAG Assistant")
        st.error(preflight_error)
        st.stop()

    # Làm nóng ở đây để trả giá nạp nguội một lần lúc khởi động, có spinner nhìn
    # thấy được, thay vì trả rải rác ở giữa câu hỏi đầu tiên.
    load_embedding_model()
    load_bm25_index()

    modules, doc_types = load_filter_options()
    has_api_key = bool(os.getenv("ANTHROPIC_API_KEY"))

    # ----------------------------- Sidebar ---------------------------------- #
    with st.sidebar:
        st.title("⚙️ Bộ lọc")
        st.caption(f"Knowledge Base: {chunk_count} chunk · 20 tài liệu")

        selected_modules = st.multiselect(
            "Module", modules, disabled=st.session_state.running
        )
        selected_doc_types = st.multiselect(
            "Loại tài liệu", doc_types, disabled=st.session_state.running
        )
        include_deprecated = st.toggle(
            "Bao gồm tài liệu đã hết hiệu lực (Deprecated)",
            value=False,
            disabled=st.session_state.running,
        )
        use_rerank = st.toggle(
            "Rerank bằng cross-encoder",
            value=False,
            disabled=st.session_state.running,
        )

        filters = build_filters(selected_modules, selected_doc_types)
        st.divider()
        st.caption(f"`filters` đang áp dụng: `{filters}`")
        st.caption(f"`include_deprecated`: `{include_deprecated}`")
        st.caption(f"`rerank`: `{use_rerank}`")
        st.divider()
        st.caption(
            f"Phiên này: {st.session_state.n_queries} câu · "
            f"≈${st.session_state.session_cost:.4f}"
        )
        st.button("Xóa kết quả", on_click=on_clear_click, disabled=st.session_state.running)

    # ------------------------------ Header ---------------------------------- #
    st.title("💬 ManhPay RAG Assistant")
    st.caption(
        "Tra cứu tài liệu nghiệp vụ ví điện tử ManhPay. Mọi câu trả lời đều kèm "
        "trích dẫn; không tìm thấy căn cứ thì hệ thống từ chối thay vì đoán."
    )

    if not has_api_key:
        st.error(
            "**Thiếu `ANTHROPIC_API_KEY`.** Tạo file `.env` ở gốc project với dòng "
            "`ANTHROPIC_API_KEY=sk-ant-...` rồi **khởi động lại app** — "
            "`load_dotenv()` chỉ chạy một lần lúc import `src.generation`."
        )

    # ------------------------------- Input ---------------------------------- #
    st.text_area(
        "Câu hỏi nghiệp vụ",
        key="question_text",
        height=100,
        placeholder=PLACEHOLDER,
        disabled=st.session_state.running,
    )

    # Container ngang + CÙNG một chiều rộng cố định (px) cho cả hai nút. Cột tỷ lệ
    # [1, 1, 4] cũ quá hẹp ở màn hình laptop, "Thử câu hỏi mẫu" gãy 2 dòng và cao
    # lệch nút "Hỏi"; width="content" thì hết gãy nhưng hai nút rộng khác nhau.
    # BUTTON_WIDTH phải đủ cho nhãn dài nhất ("🎲 Thử câu hỏi mẫu" ~225px).
    with st.container(horizontal=True):
        ask_clicked = st.button(
            "🔍 Hỏi",
            type="primary",
            width=BUTTON_WIDTH,
            disabled=st.session_state.running or not has_api_key,
        )
        st.button(
            "🎲 Thử câu hỏi mẫu",
            on_click=on_sample_click,
            width=BUTTON_WIDTH,
            disabled=st.session_state.running,
        )

    sample = st.session_state.sample_meta
    if sample and st.session_state.question_text == sample["question"]:
        st.caption(f"Câu mẫu **{sample['id']}** · nhóm `{sample['group']}`")

    # ------------------- Máy trạng thái ba lượt ----------------------------- #
    # Lượt 1 (bấm) -> nhận câu hỏi, bật cờ running, rerun.
    # Lượt 2 (in-flight) -> widget bị disable, chạy query, tắt cờ, rerun.
    # Lượt 3 -> hiện kết quả.
    #
    # Đáng để tốn thêm hai lần rerun (vài ms): không có nó, bấm lần hai trong lúc
    # generate_answer đang chặn sẽ xếp hàng một rerun và GỌI API LẦN THỨ HAI.
    if ask_clicked:
        question = st.session_state.question_text.strip()
        if not question:
            st.session_state.error = (
                "Nhập câu hỏi trước đã — ví dụ: "
                '"Hạn mức chuyển tiền P2P mỗi ngày của Tier 2 là bao nhiêu?"'
            )
        elif len(question) > MAX_QUESTION_CHARS:
            st.session_state.error = (
                f"Câu hỏi quá dài ({len(question):,} ký tự). Rút ngắn xuống dưới "
                f"{MAX_QUESTION_CHARS:,} ký tự."
            )
        else:
            st.session_state.pending_question = question
            st.session_state.running = True
            st.session_state.result = None
            st.session_state.error = None
        st.rerun()

    if st.session_state.running and st.session_state.pending_question:
        question = st.session_state.pending_question
        with st.spinner("Đang truy hồi Knowledge Base và gọi Claude…"):
            result, error = run_query(
                question,
                filters=filters,
                include_deprecated=include_deprecated,
                rerank=use_rerank,
            )
        st.session_state.result = result
        st.session_state.error = error
        st.session_state.asked_question = question
        st.session_state.pending_question = None
        st.session_state.running = False
        if result is not None:
            st.session_state.session_cost += result.cost_usd
            st.session_state.n_queries += 1
        st.rerun()

    # ------------------------------ Kết quả --------------------------------- #
    if st.session_state.error:
        st.error(st.session_state.error)

    result = st.session_state.result
    if result is not None:
        st.divider()
        render_result(result, filters_active=filters is not None)

        # Câu mẫu thì hiện luôn đáp án tham chiếu -> demo tự kiểm chứng được.
        if sample and st.session_state.asked_question == sample["question"]:
            if sample["ground_truth"]:
                with st.expander("Đáp án tham chiếu (bộ đánh giá)", expanded=False):
                    st.markdown(sample["ground_truth"])

        # Chi phí: dưới khối trích dẫn, góc phải (COST_CSS). html.escape vì chuỗi
        # đi qua unsafe_allow_html.
        st.markdown(
            f"<div class='manhpay-cost'>{html.escape(format_cost(result))}</div>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
