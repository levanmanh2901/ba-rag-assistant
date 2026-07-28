"""Tests for src/vectorstore.py.

Index được dựng vào thư mục tạm nên không đụng `chroma_db/` thật. Trọng tâm là
metadata filter: KB cố tình chứa BR-002 (Approved, Tier 3 = 100 triệu) cạnh
BR-002-v1 (Deprecated, 50 triệu), không lọc thì retrieval trả về số sai.
"""

import pytest

from src.chunking import chunk_documents
from src.ingestion import ingest_all
from src.vectorstore import _build_where, build_index, get_collection, query

pytestmark = pytest.mark.slow

TIER_QUESTION = "Hạn mức giao dịch một ngày của tài khoản Tier 3 là bao nhiêu?"


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    """Build the index once into a temp directory."""
    persist_dir = tmp_path_factory.mktemp("chroma")
    count = build_index(persist_dir=persist_dir)
    return persist_dir, count


# --------------------------------------------------------------------------- #
# Dựng index
# --------------------------------------------------------------------------- #
def test_all_chunks_indexed(index):
    persist_dir, count = index
    assert count == len(chunk_documents(ingest_all()))
    assert get_collection(persist_dir).count() == count


def test_rebuild_is_idempotent(index):
    """Chạy lại build không được nhân đôi số bản ghi."""
    persist_dir, count = index
    assert build_index(persist_dir=persist_dir) == count


def test_metadata_survives_the_round_trip(index):
    persist_dir, _ = index
    hit = query(TIER_QUESTION, top_k=1, persist_dir=persist_dir)[0]
    for key in ("doc_id", "doc_type", "module", "status", "version", "heading_path"):
        assert key in hit["metadata"]
    assert hit["chunk_id"] == hit["metadata"]["chunk_id"]


# --------------------------------------------------------------------------- #
# Truy vấn
# --------------------------------------------------------------------------- #
def test_query_returns_ranked_results(index):
    persist_dir, _ = index
    hits = query(TIER_QUESTION, top_k=5, persist_dir=persist_dir)

    assert len(hits) == 5
    assert [h["score"] for h in hits] == sorted((h["score"] for h in hits), reverse=True)
    for hit in hits:
        assert set(hit) == {"chunk_id", "content", "metadata", "distance", "score"}
        assert hit["score"] == pytest.approx(1.0 - hit["distance"])


def test_top_k_is_respected(index):
    persist_dir, _ = index
    assert len(query(TIER_QUESTION, top_k=3, persist_dir=persist_dir)) == 3


# --------------------------------------------------------------------------- #
# Metadata filter — lý do tồn tại của cả bước này
# --------------------------------------------------------------------------- #
def test_status_filter_excludes_deprecated(index):
    persist_dir, _ = index
    hits = query(
        TIER_QUESTION, filters={"status": "Approved"}, top_k=10, persist_dir=persist_dir
    )
    assert hits
    assert all(hit["metadata"]["status"] == "Approved" for hit in hits)
    assert not any(hit["metadata"]["doc_id"] == "BR-002-v1" for hit in hits)


def test_deprecated_doc_is_reachable_without_the_filter(index):
    """Chứng minh bộ lọc thực sự có tác dụng: không lọc thì bản cũ vẫn lọt vào.

    Nếu test này hỏng thì test trên trở nên vô nghĩa — nó sẽ xanh chỉ vì
    BR-002-v1 không bao giờ được truy hồi, chứ không phải vì bộ lọc làm việc.
    """
    persist_dir, _ = index
    hits = query(TIER_QUESTION, top_k=25, persist_dir=persist_dir)
    assert any(hit["metadata"]["doc_id"] == "BR-002-v1" for hit in hits)


def test_module_filter(index):
    persist_dir, _ = index
    hits = query(
        "quy trình đối soát", filters={"module": "Doi_Soat"}, persist_dir=persist_dir
    )
    assert hits
    assert all(hit["metadata"]["module"] == "Doi_Soat" for hit in hits)


def test_multi_key_filter(index):
    """Từ 2 điều kiện trở lên Chroma bắt buộc phải bọc trong $and."""
    persist_dir, _ = index
    hits = query(
        "hạn mức nạp tiền",
        filters={"doc_type": "BRD", "status": "Approved"},
        persist_dir=persist_dir,
    )
    assert hits
    for hit in hits:
        assert hit["metadata"]["doc_type"] == "BRD"
        assert hit["metadata"]["status"] == "Approved"


def test_list_filter_uses_in_operator(index):
    persist_dir, _ = index
    hits = query(
        "quy trình xử lý",
        filters={"doc_type": ["SOP", "BRD"]},
        top_k=10,
        persist_dir=persist_dir,
    )
    assert hits
    assert all(hit["metadata"]["doc_type"] in {"SOP", "BRD"} for hit in hits)


def test_table_chunks_are_retrievable(index):
    """Bảng phí trong Excel phải tìm được, không bị chìm hoàn toàn."""
    persist_dir, _ = index
    hits = query(
        "bảng phí merchant theo hạng",
        filters={"doc_type": "Fee_Pricing_Table"},
        persist_dir=persist_dir,
    )
    assert any(hit["metadata"]["has_table"] for hit in hits)
    assert any("0.6%" in hit["content"] for hit in hits)


# --------------------------------------------------------------------------- #
# _build_where
# --------------------------------------------------------------------------- #
def test_build_where_empty():
    assert _build_where(None) is None
    assert _build_where({}) is None


def test_build_where_single_key():
    assert _build_where({"status": "Approved"}) == {"status": {"$eq": "Approved"}}


def test_build_where_list_value():
    assert _build_where({"doc_type": ["BRD", "SOP"]}) == {
        "doc_type": {"$in": ["BRD", "SOP"]}
    }


def test_build_where_multiple_keys_wrapped_in_and():
    where = _build_where({"status": "Approved", "module": "Nap_Tien"})
    assert where == {
        "$and": [{"status": {"$eq": "Approved"}}, {"module": {"$eq": "Nap_Tien"}}]
    }
