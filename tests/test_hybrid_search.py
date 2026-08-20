"""Tests for src/hybrid_search.py and src/bm25_retriever.py.

Hai thứ được kiểm ở đây, cả hai đều là lý do tồn tại của bước hybrid:

1. Câu hỏi tra SỐ. Vector thuần trả top-3 toàn BRD-002 cho "hạn mức chuyển tiền
   P2P Tier 2", còn đáp án thật (20.000.000 VNĐ) nằm ở BR-002 và trượt khỏi
   top-3. Hybrid phải kéo BR-002 vào.
2. Xung đột phiên bản. KB cố tình chứa BR-002 (Approved, Tier 3 = 100 triệu)
   cạnh BR-002-v1 (Deprecated, 50 triệu). Mặc định phải chặn bản cũ, nhưng câu
   hỏi lịch sử thì bản cũ LẠI là nguồn hợp lệ.

Marker `slow` đặt trên từng test chứ không đặt ở mức module như các file test
khác: nửa số test ở đây là hàm thuần (tokenizer, chuẩn hóa điểm, giải filter),
chạy được mà không phải nạp sentence-transformers 470MB. `-m "not slow"` cho
vòng lặp phát triển nhanh.
"""

import json
import unicodedata

import pytest

from src.bm25_retriever import clear_cache, get_index, search, tokenize
from src.hybrid_search import (
    DEFAULT_STATUS_FILTER,
    _normalize_scores,
    _resolve_filters,
    hybrid_search,
)
from src.vectorstore import PROJECT_ROOT, build_index, query

EVAL_PATH = PROJECT_ROOT / "data" / "Evaluation" / "evaluation_questions.json"

# Q001 — câu hỏi đã đo được là vector thuần thất bại. Đáp án 20.000.000 ở BR-002,
# nhưng BRD-002 (chỉ tham chiếu lại) chiếm hết top-3.
P2P_TIER2_QUESTION = "Hạn mức chuyển tiền P2P mỗi ngày của tài khoản Tier 2 là bao nhiêu?"


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
    # BM25 cache theo persist_dir — ép dựng lại để chắc chắn nó chấm trên đúng
    # tập chunk vừa ghi, không phải tập của một lần build trước trong process.
    clear_cache()
    get_index(persist_dir, refresh=True)
    return persist_dir


def doc_ids(hits):
    """Doc ids of the hits, in rank order, de-duplicated."""
    seen = []
    for hit in hits:
        if hit["metadata"]["doc_id"] not in seen:
            seen.append(hit["metadata"]["doc_id"])
    return seen


def doc_rank(hits, doc_id):
    """1-based rank of the first chunk from ``doc_id``; ``inf`` if absent."""
    ids = doc_ids(hits)
    return ids.index(doc_id) + 1 if doc_id in ids else float("inf")


# --------------------------------------------------------------------------- #
# Tokenizer — không cần model
# --------------------------------------------------------------------------- #
def test_thousands_separated_number_stays_one_token():
    """100.000.000 vỡ thành 100/000/000 là mất đúng token phân biệt nhất."""
    assert tokenize("hạn mức 100.000.000 VNĐ") == ["hạn", "mức", "100000000", "vnđ"]


def test_thousands_separator_style_is_normalized():
    """Excel và Markdown viết khác dấu phân cách nhưng phải khớp nhau."""
    assert tokenize("20.000.000") == tokenize("20,000,000") == ["20000000"]


def test_decimal_is_not_collapsed():
    """Bẫy ngược của quy tắc trên: 1.5% mà gộp thì thành 15, sai một bậc."""
    assert tokenize("phí 1.5%") == ["phí", "1.5"]
    assert tokenize("0,6%") == ["0.6"]


def test_doc_code_is_kept_whole_and_split():
    """Gõ 'BR-002' hay gõ 'BR 002' đều phải khớp."""
    assert tokenize("theo BR-002") == ["theo", "br-002", "br", "002"]
    assert tokenize("US-EPIC-014") == ["us-epic-014", "us", "epic", "014"]


def test_tokenizer_is_unicode_normalization_insensitive():
    """`.md`, `.docx`, `.xlsx` qua 3 thư viện — dấu tiếng Việt có thể khác dạng.

    Hai chuỗi dưới đây hiển thị giống hệt nhau nhưng khác codepoint. Không chuẩn
    hóa NFC thì chúng không khớp token, và hỏng hoàn toàn im lặng.
    """
    composed = "hạn mức"  # ạ, ứ dựng sẵn
    decomposed = "hạn mức"  # a + dấu nặng, ư + dấu sắc
    # Nếu file nguồn này bị một công cụ nào đó chuẩn hóa lại thì hai hằng trên
    # sẽ trùng nhau và test âm thầm mất tác dụng — sinh lại dạng tổ hợp tại chỗ.
    decomposed = unicodedata.normalize("NFD", decomposed)
    assert composed != decomposed
    assert tokenize(composed) == tokenize(decomposed)


def test_tokenizer_lowercases():
    assert tokenize("Tier 2") == ["tier", "2"]


# --------------------------------------------------------------------------- #
# Chuẩn hóa điểm BM25 — không cần model
# --------------------------------------------------------------------------- #
def test_normalize_stretches_to_unit_range():
    assert _normalize_scores({"a": 2.0, "b": 12.0, "c": 7.0}) == {
        "a": 0.0,
        "b": 1.0,
        "c": 0.5,
    }


def test_normalize_handles_all_zero_scores():
    """Query không có token nào trong corpus -> không được chia cho 0.

    Trả 0.0 hết là đúng nghĩa: không có tín hiệu từ vựng nào để phân biệt thì
    nhánh từ vựng không đóng góp gì, xếp hạng lùi về thuần vector.
    """
    assert _normalize_scores({"a": 0.0, "b": 0.0}) == {"a": 0.0, "b": 0.0}


def test_normalize_handles_identical_nonzero_scores():
    assert _normalize_scores({"a": 5.0, "b": 5.0}) == {"a": 0.0, "b": 0.0}


def test_normalize_handles_single_and_empty_pool():
    assert _normalize_scores({"a": 9.9}) == {"a": 0.0}
    assert _normalize_scores({}) == {}


# --------------------------------------------------------------------------- #
# Giải filter — không cần model
# --------------------------------------------------------------------------- #
def test_default_filter_only_hides_deprecated():
    """KHÔNG phải status == "Approved".

    Catalog có 4 status; lọc cứng Approved sẽ khóa vĩnh viễn UserStory
    (In Progress) và IncidentReport (Closed) khỏi mọi truy vấn.
    """
    assert _resolve_filters(None, False) == {"status": DEFAULT_STATUS_FILTER}


def test_explicit_status_wins_over_default():
    assert _resolve_filters({"status": "Approved"}, False) == {"status": "Approved"}


def test_include_deprecated_drops_the_status_clause():
    assert _resolve_filters(None, True) is None
    assert _resolve_filters({"module": "Han_Muc_Giao_Dich"}, True) == {
        "module": "Han_Muc_Giao_Dich"
    }


def test_other_filters_are_merged_with_the_default():
    assert _resolve_filters({"doc_type": "BRD"}, False) == {
        "doc_type": "BRD",
        "status": DEFAULT_STATUS_FILTER,
    }


def test_resolve_does_not_mutate_the_caller_dict():
    filters = {"module": "Nap_Tien"}
    _resolve_filters(filters, False)
    assert filters == {"module": "Nap_Tien"}


# --------------------------------------------------------------------------- #
# BM25 trên index thật
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_bm25_returns_id_score_pairs(index):
    hits = search("hạn mức Tier 3", top_k=5, persist_dir=index)
    assert len(hits) == 5
    assert all(isinstance(cid, str) and isinstance(s, float) for cid, s in hits)
    assert [s for _, s in hits] == sorted((s for _, s in hits), reverse=True)


@pytest.mark.slow
def test_bm25_finds_the_exact_number(index):
    """Đúng thứ embedding làm nhòe: tra thẳng con số phải ra tài liệu chứa nó."""
    hits = search("20.000.000", top_k=3, persist_dir=index)
    metas = dict(zip(get_index(index).chunk_ids, get_index(index).metadatas))
    assert "BR-002" in {metas[cid]["doc_id"] for cid, _ in hits}


@pytest.mark.slow
def test_bm25_respects_allowed_ids(index):
    """Nhánh từ vựng không có `where` — filter phải áp qua allowed_ids."""
    allowed = {cid for cid in get_index(index).chunk_ids if cid.startswith("BR-002#")}
    hits = search("hạn mức", top_k=20, persist_dir=index, allowed_ids=allowed)
    assert hits
    assert all(cid in allowed for cid, _ in hits)


# --------------------------------------------------------------------------- #
# Hình dạng kết quả hybrid
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_hit_shape_and_ordering(index):
    hits = hybrid_search(P2P_TIER2_QUESTION, top_k=5, persist_dir=index)

    assert len(hits) == 5
    assert [h["score"] for h in hits] == sorted((h["score"] for h in hits), reverse=True)
    for hit in hits:
        assert set(hit) == {
            "chunk_id",
            "content",
            "metadata",
            "score",
            "vector_score",
            "bm25_score",
        }
        assert hit["chunk_id"] == hit["metadata"]["chunk_id"]


@pytest.mark.slow
def test_alpha_selects_the_branch(index):
    """alpha=1.0 là vector thuần, alpha=0.0 là BM25 thuần."""
    vector_only = hybrid_search(P2P_TIER2_QUESTION, top_k=5, alpha=1.0, persist_dir=index)
    for hit in vector_only:
        assert hit["score"] == pytest.approx(hit["vector_score"])

    lexical_only = hybrid_search(P2P_TIER2_QUESTION, top_k=5, alpha=0.0, persist_dir=index)
    # Điểm đã min-max nên chunk BM25 cao nhất trong pool luôn được đúng 1.0.
    assert lexical_only[0]["score"] == pytest.approx(1.0)


@pytest.mark.slow
def test_top_k_is_respected(index):
    assert len(hybrid_search(P2P_TIER2_QUESTION, top_k=3, persist_dir=index)) == 3


# --------------------------------------------------------------------------- #
# Nhóm version_conflict — Q026, Q027, Q028
# --------------------------------------------------------------------------- #
@pytest.mark.slow
@pytest.mark.parametrize("qid", ["Q026", "Q027"])
def test_version_conflict_returns_the_approved_source(index, eval_questions, qid):
    """Câu hỏi về hiện tại: phải ra BR-002, tuyệt đối không ra BR-002-v1.

    `must_not_use_docs` đọc thẳng từ evaluation_questions.json chứ không viết
    cứng, để bộ đánh giá mở rộng thì test tự theo.
    """
    item = eval_questions[qid]
    assert item["group"] == "version_conflict"

    hits = hybrid_search(item["question"], top_k=5, persist_dir=index)
    retrieved = set(doc_ids(hits))

    assert retrieved & set(item["expected_source_docs"]), (
        f"{qid}: không truy hồi được nguồn đúng {item['expected_source_docs']}, "
        f"chỉ có {sorted(retrieved)}"
    )
    assert not retrieved & set(item["must_not_use_docs"]), (
        f"{qid}: tài liệu Deprecated {item['must_not_use_docs']} lọt vào kết quả"
    )
    assert all(hit["metadata"]["status"] != "Deprecated" for hit in hits)


@pytest.mark.slow
def test_history_question_can_reach_the_deprecated_doc(index, eval_questions):
    """Q028 hỏi "trước đây hạn mức là bao nhiêu" — ở đây bản cũ LÀ nguồn hợp lệ.

    Đây là lý do `include_deprecated` tồn tại: hệ thống phải phân biệt được câu
    hỏi về hiện tại với câu hỏi về lịch sử, chứ không chặn cứng một chiều.
    """
    item = eval_questions["Q028"]
    assert "BR-002-v1" in item["expected_source_docs"]

    hits = hybrid_search(
        item["question"], top_k=10, include_deprecated=True, persist_dir=index
    )
    assert "BR-002-v1" in doc_ids(hits)


@pytest.mark.slow
def test_deprecated_is_blocked_by_default_on_the_same_question(index, eval_questions):
    """Cặp với test trên: cùng câu hỏi, không bật cờ thì bản cũ phải biến mất.

    Nếu test này hỏng thì test chặn Deprecated ở trên thành vô nghĩa — nó sẽ xanh
    chỉ vì BR-002-v1 không bao giờ được truy hồi, chứ không phải vì filter làm việc.
    """
    question = eval_questions["Q028"]["question"]
    assert "BR-002-v1" not in doc_ids(
        hybrid_search(question, top_k=10, persist_dir=index)
    )


# --------------------------------------------------------------------------- #
# Q001 — bằng chứng hybrid sửa được lỗi đã đo
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_p2p_tier2_puts_br002_in_top3(index, eval_questions, capsys):
    """Vector thuần để BR-002 trượt khỏi top-3; hybrid phải kéo nó vào.

    Chỉ assert cứng phía hybrid. Không assert "vector-only phải trượt": đó là
    ràng buộc lên một thứ ta muốn nó tệ, đổi embedding tốt hơn sau này sẽ làm
    test đỏ oan. Chiều so sánh được assert ở dạng yếu — hybrid không được xếp
    BR-002 thấp hơn vector thuần.
    """
    item = eval_questions["Q001"]
    assert item["expected_source_docs"] == ["BR-002"]

    before = query(item["question"], top_k=20, persist_dir=index)
    after = hybrid_search(item["question"], top_k=20, persist_dir=index)

    rank_before = doc_rank(before, "BR-002")
    rank_after = doc_rank(after, "BR-002")

    with capsys.disabled():
        print(f"\n  Q001: {item['question']}")
        print(f"  vector-only top-3 : {doc_ids(before)[:3]}  (BR-002 hạng {rank_before})")
        print(f"  hybrid     top-3 : {doc_ids(after)[:3]}  (BR-002 hạng {rank_after})")

    assert rank_after <= 3, f"BR-002 chỉ ở hạng {rank_after} trong kết quả hybrid"
    assert rank_after <= rank_before


@pytest.mark.slow
def test_hybrid_surfaces_the_answer_text(index, eval_questions):
    """Truy hồi đúng tài liệu chưa đủ — chunk trả về phải chứa con số."""
    hits = hybrid_search(eval_questions["Q001"]["question"], top_k=3, persist_dir=index)
    assert any(
        "20.000.000" in hit["content"] and hit["metadata"]["doc_id"] == "BR-002"
        for hit in hits
    )


# --------------------------------------------------------------------------- #
# Metadata filter
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_module_filter(index):
    hits = hybrid_search(
        "quy trình đối soát", filters={"module": "Doi_Soat"}, persist_dir=index
    )
    assert hits
    assert all(hit["metadata"]["module"] == "Doi_Soat" for hit in hits)


@pytest.mark.slow
def test_doc_type_list_filter(index):
    hits = hybrid_search(
        "quy trình xử lý", filters={"doc_type": ["SOP", "BRD"]}, top_k=10, persist_dir=index
    )
    assert hits
    assert all(hit["metadata"]["doc_type"] in {"SOP", "BRD"} for hit in hits)


@pytest.mark.slow
def test_explicit_status_filter_narrows_to_approved(index):
    hits = hybrid_search(
        "user story quét mã QR", filters={"status": "Approved"}, top_k=10, persist_dir=index
    )
    assert hits
    assert all(hit["metadata"]["status"] == "Approved" for hit in hits)


@pytest.mark.slow
def test_in_progress_and_closed_docs_stay_reachable_by_default(index):
    """Chốt quyết định dùng $nin thay vì == "Approved".

    Guard chống việc ai đó "đơn giản hóa" filter mặc định thành status ==
    "Approved" — làm vậy sẽ khóa vĩnh viễn UserStory (In Progress) và
    IncidentReport (Closed), hỏng các câu Q010/Q012/Q020 của bộ đánh giá mà
    không có test nào đỏ.
    """
    stories = hybrid_search("user story quét mã QR thanh toán", top_k=5, persist_dir=index)
    assert "US-EPIC-014" in doc_ids(stories)

    incident = hybrid_search("sự cố ví điện tử báo cáo incident", top_k=10, persist_dir=index)
    assert "INC-001" in doc_ids(incident)


@pytest.mark.slow
def test_empty_candidate_pool_returns_nothing(index):
    """Filter không khớp tài liệu nào -> trả list rỗng, không nổ."""
    assert hybrid_search("bất kỳ", filters={"module": "Khong_Ton_Tai"}, persist_dir=index) == []
