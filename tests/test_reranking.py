"""Đo lại Q015 và Q018 sau hai kỹ thuật mới, và canh không nhóm nào tụt hạng.

Sản phẩm chính của file này KHÔNG phải mấy dòng assert mà là hai bảng nó in ra:

* bảng 4 cột thứ hạng của Q015/Q018 qua từng kỹ thuật (baseline Tuần 5, +boost
  bảng, +reranking, +cả hai);
* bảng Recall@3 theo nhóm cho cả 4 cấu hình, để chứng minh version_conflict và
  single_source vẫn 100%.

Chạy: ``pytest tests/test_reranking.py -m slow -v -s``
"""

from __future__ import annotations

import json
import time
from typing import Any

import pytest

from src import reranking as _reranking_module
from src.bm25_retriever import clear_cache, get_index
from src.hybrid_search import TABLE_BOOST, hybrid_search, is_numeric_lookup
from src.reranking import CANDIDATE_K, RERANKER_MODEL, get_reranker, rerank
from src.vectorstore import PROJECT_ROOT, build_index

EVAL_PATH = PROJECT_ROOT / "data" / "Evaluation" / "evaluation_questions.json"

# Lấy sâu hơn top-3 rất nhiều ở hai cột không rerank: phải đo được "hạng 5" và
# "hạng 8" thì mới so sánh trước/sau được. top_k=3 chỉ cho ra "không thấy".
RANK_DEPTH = 40

ARMS = ("baseline", "+boost", "+rerank", "+cả hai")


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


def doc_ids(hits: list[dict[str, Any]]) -> list[str]:
    """Doc ids in hit order, de-duplicated."""
    seen: list[str] = []
    for hit in hits:
        if hit["metadata"]["doc_id"] not in seen:
            seen.append(hit["metadata"]["doc_id"])
    return seen


def doc_rank(hits: list[dict[str, Any]], doc_id: str) -> float:
    """1-based rank of ``doc_id`` among DISTINCT docs; ``inf`` if absent.

    Đây là đơn vị mà Recall@3 dùng (``src/hybrid_search.py:257`` gọi ``doc_ids``
    rồi mới cắt 3), nên nó mới là con số quyết định đạt/không đạt.
    """
    ids = doc_ids(hits)
    return ids.index(doc_id) + 1 if doc_id in ids else float("inf")


def chunk_rank(hits: list[dict[str, Any]], doc_id: str) -> float:
    """1-based rank of the first CHUNK from ``doc_id``; ``inf`` if absent.

    Đơn vị của những con số ghi lại ở Tuần 5 ("Q015 hạng 5", "Q018 hạng 8").
    Phải đo riêng, vì hai đơn vị KHÔNG bằng nhau khi một tài liệu chiếm nhiều
    chunk liên tiếp: ở Q018, LIMIT-001#000 là chunk thứ 8 nhưng chỉ là tài liệu
    khác biệt thứ 6 (BR-002 và BRD-004 mỗi cái chiếm hai suất phía trên). Lẫn
    hai đơn vị này là cách dễ nhất để tưởng mình vừa cải thiện được thứ gì đó.
    """
    for rank, hit in enumerate(hits, start=1):
        if hit["metadata"]["doc_id"] == doc_id:
            return rank
    return float("inf")


def show(rank: float) -> str:
    """Render a rank for the table — ``inf`` prints as an em dash."""
    return "—" if rank == float("inf") else str(int(rank))


def four_arms(
    question: str, persist_dir, include_deprecated: bool = False, depth: int = RANK_DEPTH
) -> dict[str, list[dict[str, Any]]]:
    """Run all four configurations on one question, sharing the retrieval pools.

    Hai lần gọi hybrid (một có boost, một không) rồi tái sử dụng chính hai pool
    đó cho hai cột rerank — cross-encoder chấm lại đúng tập ứng viên mà cột
    không-rerank đã xếp, nên chênh lệch thứ hạng quy hết được về bước rerank.
    """
    common = dict(persist_dir=persist_dir, include_deprecated=include_deprecated)
    plain = hybrid_search(question, top_k=depth, table_boost=0.0, **common)
    boosted = hybrid_search(question, top_k=depth, table_boost=TABLE_BOOST, **common)
    return {
        "baseline": plain,
        "+boost": boosted,
        "+rerank": rerank(question, plain[:CANDIDATE_K], top_k=CANDIDATE_K),
        "+cả hai": rerank(question, boosted[:CANDIDATE_K], top_k=CANDIDATE_K),
    }


# --------------------------------------------------------------------------- #
# Nhận diện câu hỏi tra số — nhanh, không nạp model
# --------------------------------------------------------------------------- #
def test_numeric_lookup_bat_het_nhom_table_numeric(eval_questions):
    """Cả 6 câu nhóm table_numeric phải được nhận là câu tra số."""
    missed = [
        qid
        for qid, item in eval_questions.items()
        if item["group"] == "table_numeric" and not is_numeric_lookup(item["question"])
    ]
    assert not missed, f"Bỏ sót câu tra số: {missed} — boost sẽ không chạm tới chúng"


def test_numeric_lookup_bo_qua_cau_khai_niem(eval_questions):
    """Câu hỏi quy trình/khái niệm KHÔNG được kích hoạt boost.

    Lưới an toàn thật sự của cơ chế boost. Nếu bộ từ khóa bắt quá rộng, chunk
    bảng được cộng điểm ở mọi câu hỏi và đẩy đúng đoạn văn chứa đáp án xuống —
    hỏng các nhóm đang ở 100%.
    """
    concept = ("Q003", "Q005", "Q009", "Q011", "Q022", "Q023", "Q032")
    fired = [qid for qid in concept if is_numeric_lookup(eval_questions[qid]["question"])]
    assert not fired, f"Câu khái niệm bị nhận nhầm là câu tra số: {fired}"


def test_numeric_lookup_bo_qua_ma_tai_lieu(eval_questions):
    """Chữ số nằm trong mã tài liệu không biến câu hỏi thành câu tra số.

    Q008 (FR-003), Q010 (INC-001), Q012 (MANHPAY-1425), Q020 (INC-001) đều CÓ
    chữ số nhưng đều đi tìm văn xuôi. Ba trong bốn câu này thuộc single_source
    đang ở 100%, nên đây là hồi quy đắt tiền nếu để lọt.
    """
    for qid in ("Q008", "Q010", "Q012", "Q020"):
        question = eval_questions[qid]["question"]
        assert not is_numeric_lookup(question), f"{qid} bị nhận nhầm: {question}"


# --------------------------------------------------------------------------- #
# Q015 / Q018 — bảng so sánh 4 cột
# --------------------------------------------------------------------------- #
@pytest.mark.slow
@pytest.mark.parametrize(
    ("qid", "expected_doc", "chunk_rank_tuan5"),
    [("Q015", "FEE-001", 5), ("Q018", "LIMIT-001", 8)],
)
def test_thu_hang_qua_tung_ky_thuat(
    qid, expected_doc, chunk_rank_tuan5, index, eval_questions, capsys
):
    """Đo lại thứ hạng của nguồn đúng qua cả 4 cấu hình, in bảng so sánh.

    Test này CỐ TÌNH không đòi phải lọt top-3. Việc của nó là đo và canh không
    tụt; mục tiêu top-3 nằm ở hai test riêng phía dưới, tách ra để khi không đạt
    thì thấy rõ đạt tới đâu chứ không chỉ thấy một chữ FAILED.
    """
    question = eval_questions[qid]["question"]
    arms = four_arms(question, index)
    d_ranks = {name: doc_rank(hits, expected_doc) for name, hits in arms.items()}
    c_ranks = {name: chunk_rank(hits, expected_doc) for name, hits in arms.items()}

    with capsys.disabled():
        print(f"\n\n{'=' * 78}")
        print(f"{qid} — {question}")
        print(f"Nguồn đúng: {expected_doc}")
        print("-" * 78)
        print(f"{'cấu hình':<12}{'hạng doc':>10}{'hạng chunk':>12}   {'top-3 doc_ids':<40}")
        print("-" * 78)
        for name in ARMS:
            top3 = ", ".join(doc_ids(arms[name])[:3])
            print(
                f"{name:<12}{show(d_ranks[name]):>10}{show(c_ranks[name]):>12}   {top3:<40}"
            )
        print("-" * 78)
        print(
            f"Tuần 5 ghi 'hạng {chunk_rank_tuan5}' — khớp cột hạng chunk "
            f"(đo được {show(c_ranks['baseline'])}), KHÔNG phải cột hạng doc."
        )
        print("=" * 78)

    assert c_ranks["baseline"] == pytest.approx(chunk_rank_tuan5), (
        f"Đường cơ sở dịch chuyển: hạng chunk đo được {show(c_ranks['baseline'])}, "
        f"Tuần 5 ghi {chunk_rank_tuan5}. Mọi so sánh phía sau mất ý nghĩa."
    )
    for name in ARMS:
        assert d_ranks[name] <= d_ranks["baseline"], (
            f"{name} làm {expected_doc} TỆ ĐI so với baseline: hạng doc "
            f"{show(d_ranks['baseline'])} -> {show(d_ranks[name])}"
        )


@pytest.mark.slow
def test_q018_lot_top3_nho_boost_bang(index, eval_questions):
    """Q018: boost bảng một mình đã đủ đưa LIMIT-001 vào top-3.

    Đây là kết quả rõ ràng nhất của tuần: hạng doc 6 -> 3. Cơ chế đúng như dự
    đoán — LIMIT-001#000 có vector_score 0.290 (kẹt dưới trần của chunk bảng)
    nhưng BM25 19.40 rất mạnh; cộng 0.11 vào nhánh vector là đủ để nó vượt bốn
    chunk văn xuôi đang chen giữa. Điểm: 0.499958 -> 0.554958, đúng bằng
    ``alpha * TABLE_BOOST = 0.5 * 0.11 = 0.055``.

    CẢNH BÁO CHO NGƯỜI ĐỌC LOG KHI TEST NÀY ĐỎ — biên độ ở đúng hạng 3 chỉ là
    **8e-06**: LIMIT-001#000 được 0.554958, BRD-004#003 ngay dưới được 0.554950.
    Đây gần như một thế hòa. Nâng cấp thư viện, đổi model embedding, hay chỉ cần
    sửa một ký tự trong tài liệu cũng đủ lật thứ tự này. Nếu test đỏ và hạng đo
    được là 4, ĐÓ KHÔNG PHẢI hồi quy thật: cái thực sự quan trọng —
    LIMIT-001 nằm trong top-5 context để generation có căn cứ trả lời — vẫn còn
    nguyên với biên độ thoải mái 0.034 (xem :func:`test_q018_lot_context_top5`,
    test đó mới là cái phải giữ bằng mọi giá).
    """
    hits = hybrid_search(
        eval_questions["Q018"]["question"], top_k=RANK_DEPTH, persist_dir=index
    )
    rank = doc_rank(hits, "LIMIT-001")
    assert rank <= 3, f"LIMIT-001 chỉ ở hạng {show(rank)} sau khi bù điểm bảng"


@pytest.mark.slow
def test_q018_lot_context_top5(index, eval_questions):
    """Q018 phải lọt top-5 context — đúng cái ngưỡng đã làm generation từ chối oan.

    Ở Tuần 6, LIMIT-001 không nằm trong 5 chunk đưa vào context nên model không
    có căn cứ nào và trả về REFUSAL_MESSAGE cho một câu hỏi hợp lệ. Đây là điều
    kiện cần để câu trả lời tồn tại, nên đo bằng đúng cấu hình mà
    ``generate_answer`` sẽ chạy.
    """
    hits = hybrid_search(
        eval_questions["Q018"]["question"], top_k=5, persist_dir=index
    )
    assert "LIMIT-001" in doc_ids(hits), (
        "LIMIT-001 vẫn ngoài top-5 context — generation sẽ lại từ chối oan Q018"
    )


@pytest.mark.slow
@pytest.mark.xfail(
    strict=True,
    reason=(
        "KHOẢNG CÁCH ĐÃ BIẾT, chưa đóng được ở Tuần 7. FEE-001#001 có "
        "vector_score 0.234 trong khi ba chunk trên nó ở 0.518-0.648; để bù đủ "
        "cần boost ~0.34 trên nhánh vector, gấp ba lần khoảng thiếu hụt trung "
        "bình đã ĐO (0.109) — nâng hằng số tới đó là bịa số cho test xanh, nên "
        "không làm. Cross-encoder cũng chỉ kéo được 5 -> 4. Xem báo cáo cuối "
        "tuần để biết hướng tiếp theo."
    ),
)
def test_q015_lot_top3(index, eval_questions):
    """Q015: FEE-001 vào top-3 — MỤC TIÊU, hiện CHƯA ĐẠT.

    Đánh dấu xfail(strict) chứ không xóa: ngày nào nó bắt đầu đạt thì test này
    đỏ lên và bắt phải cập nhật, thay vì lặng lẽ xanh mà không ai biết.
    """
    hits = rerank(
        eval_questions["Q015"]["question"],
        hybrid_search(
            eval_questions["Q015"]["question"], top_k=CANDIDATE_K, persist_dir=index
        ),
        top_k=CANDIDATE_K,
    )
    assert doc_rank(hits, "FEE-001") <= 3


@pytest.mark.slow
def test_rerank_khong_duoc_xoa_cong_cua_boost(index, eval_questions, capsys):
    """Cảnh báo: rerank xếp lại HOÀN TOÀN nên nó vứt luôn phần boost vừa cộng.

    Đo được ở Q018: chỉ boost -> hạng doc 3; boost RỒI rerank -> hạng doc 5.
    Cross-encoder chấm LIMIT-001#000 ở -0.314, dưới cả BRD-004#003 (-0.309),
    nên thứ tự hybrid (nơi boost phát huy tác dụng) bị thay thế sạch.

    Test này không đòi phải sửa — nó ghim con số lại để lần sau có người bật
    rerank mặc định thì thấy ngay cái giá phải trả.
    """
    question = eval_questions["Q018"]["question"]
    boosted = hybrid_search(question, top_k=RANK_DEPTH, persist_dir=index)
    both = rerank(question, boosted[:CANDIDATE_K], top_k=CANDIDATE_K)

    rank_boost = doc_rank(boosted, "LIMIT-001")
    rank_both = doc_rank(both, "LIMIT-001")

    with capsys.disabled():
        print(
            f"\n\n[Q018] chỉ boost: hạng doc {show(rank_boost)}  |  "
            f"boost + rerank: hạng doc {show(rank_both)}"
        )
        if rank_both > rank_boost:
            print(
                "  -> rerank ĐANG LÀM TỆ ĐI câu này. Hướng xử lý là trộn điểm "
                "(w*hybrid + (1-w)*rerank) thay vì để rerank ghi đè thứ tự — "
                "phương án đã cân nhắc và tạm gác ở đầu Tuần 7.\n"
            )

    assert rank_both <= doc_rank(
        hybrid_search(question, top_k=RANK_DEPTH, table_boost=0.0, persist_dir=index),
        "LIMIT-001",
    ), "rerank làm Q018 tệ hơn cả đường cơ sở, không chỉ tệ hơn cột boost"


# --------------------------------------------------------------------------- #
# Độ trễ — thay ước lượng bằng số đo thật
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_do_tre_rerank(index, eval_questions, capsys):
    """Đo chi phí thật của bước rerank, tách khỏi chi phí nạp model.

    Không assert ngưỡng thời gian: máy nào cũng khác, và một test đỏ vì máy
    đang bận thì chỉ dạy người ta bỏ qua nó. Việc của test này là IN RA con số
    để thay mấy dòng ước lượng trong plan bằng phép đo.
    """
    question = eval_questions["Q015"]["question"]

    # get_reranker() là singleton, và các test phía trên trong module này đã nạp
    # nó rồi — đo ở đây gần như chắc chắn ra 0.00s. Ghi rõ trạng thái thay vì in
    # một con số vô nghĩa trông như phép đo khởi động nguội.
    already_warm = _reranking_module._model is not None
    start = time.perf_counter()
    get_reranker()
    load_seconds = time.perf_counter() - start

    pool = hybrid_search(question, top_k=CANDIDATE_K, persist_dir=index)

    start = time.perf_counter()
    hybrid_search(question, top_k=CANDIDATE_K, persist_dir=index)
    hybrid_seconds = time.perf_counter() - start

    # Chạy vài lần rồi lấy trung bình: lần đầu sau khi nạp model còn dính chi
    # phí khởi tạo lười bên trong torch, không đại diện cho lúc chạy thật.
    runs = 3
    start = time.perf_counter()
    for _ in range(runs):
        rerank(question, pool, top_k=5)
    rerank_seconds = (time.perf_counter() - start) / runs

    with capsys.disabled():
        print(f"\n\n{'=' * 78}\nĐộ trễ đo thật — {RERANKER_MODEL}\n{'=' * 78}")
        if already_warm:
            print("  nạp model                       : (đã nạp sẵn ở test trước —")
            print("                                     chạy riêng file này để đo nguội)")
        else:
            print(f"  nạp model (một lần mỗi process) : {load_seconds:6.2f}s")
        print(f"  hybrid search ({CANDIDATE_K} ứng viên)      : {hybrid_seconds:6.3f}s")
        print(f"  rerank {len(pool)} cặp                    : {rerank_seconds:6.3f}s")
        print(f"  -> rerank tốn gấp {rerank_seconds / max(hybrid_seconds, 1e-9):.0f} lần hybrid")
        print("  -> chi phí API cộng thêm        : $0.00 (chạy CPU cục bộ)")
        print("=" * 78)


# --------------------------------------------------------------------------- #
# Chống tụt hạng trên toàn bộ 28 câu có nguồn xác định
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_recall_at_3_khong_tut_o_nhom_nao(index, eval_questions, capsys):
    """Recall@3 theo nhóm cho cả 4 cấu hình; không nhóm nào được tụt."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in eval_questions.values():
        # Câu adversarial không có nguồn đúng nào — recall không đo được.
        if item["expected_source_docs"]:
            groups.setdefault(item["group"], []).append(item)

    hits_by_group: dict[str, dict[str, int]] = {}

    for group, items in groups.items():
        counts = dict.fromkeys(ARMS, 0)
        for item in items:
            expected = set(item["expected_source_docs"])
            # Q028 hỏi về quá khứ: bản Deprecated mới là nguồn hợp lệ.
            history = group == "version_conflict" and not item.get("must_not_use_docs")
            for name, hits in four_arms(
                item["question"], index, include_deprecated=history
            ).items():
                counts[name] += bool(expected & set(doc_ids(hits)[:3]))
        hits_by_group[group] = counts

    with capsys.disabled():
        print(f"\n\n{'=' * 78}\nRecall@3 theo nhóm — 4 cấu hình\n{'=' * 78}")
        print(f"{'nhóm':<18}{'n':>4}" + "".join(f"{name:>12}" for name in ARMS))
        print("-" * 78)
        for group, counts in hits_by_group.items():
            n = len(groups[group])
            row = "".join(f"{counts[name] / n:>11.0%} " for name in ARMS)
            print(f"{group:<18}{n:>4}{row}")
        print("-" * 78)
        total_n = sum(len(items) for items in groups.values())
        totals = {
            name: sum(counts[name] for counts in hits_by_group.values()) for name in ARMS
        }
        row = "".join(f"{totals[name] / total_n:>11.0%} " for name in ARMS)
        print(f"{'TỔNG':<18}{total_n:>4}{row}")
        print("=" * 78)

    for group in ("version_conflict", "single_source"):
        n = len(groups[group])
        for name in ARMS:
            assert hits_by_group[group][name] == n, (
                f"{group} tụt xuống {hits_by_group[group][name]}/{n} ở cột {name} "
                f"— nhóm này đạt 100% ở Tuần 5 và không được phép tụt"
            )

    for group, counts in hits_by_group.items():
        for name in ARMS:
            assert counts[name] >= counts["baseline"], (
                f"{group} tụt ở cột {name}: {counts[name]}/{len(groups[group])} "
                f"so với baseline {counts['baseline']}/{len(groups[group])}"
            )

    assert totals["+cả hai"] >= totals["baseline"], (
        f"Tổng Recall@3 tụt: {totals['+cả hai']}/{total_n} so với "
        f"baseline {totals['baseline']}/{total_n}"
    )
