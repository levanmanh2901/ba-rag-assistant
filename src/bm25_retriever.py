"""BM25 lexical retriever over the chunks already stored in ChromaDB.

Nhánh từ vựng của hybrid search. Nó tồn tại để bù đúng một điểm mù của
embedding: vector similarity phân biệt được "tài liệu nói về chủ đề X" nhưng
KHÔNG phân biệt được "tài liệu chứa GIÁ TRỊ của X". Hỏi hạn mức P2P Tier 2 thì
BRD-002 (mô tả nghiệp vụ chuyển tiền, nhắc đi nhắc lại "P2P", "Tier") thắng
BR-002 (bảng hạn mức, chứa con số 20.000.000) ở mọi vị trí top-3. BM25 chấm theo
token hiếm nên con số và mã tài liệu — thứ IDF cao nhất — mới là thứ quyết định.

Corpus lấy thẳng từ collection Chroma chứ không chunk lại, để hai nhánh luôn
chấm trên cùng một tập chunk và cùng một ``chunk_id``.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from src.vectorstore import CHROMA_DIR, get_collection

logger = logging.getLogger(__name__)

# Thứ tự nhánh trong regex là thứ tự ưu tiên — nhánh trước ăn trước.
#   1. số có dấu phân cách hàng nghìn: 20.000.000 / 20,000,000
#   2. số thập phân:                   1.5 / 0,6
#   3. mã có gạch nối:                 BR-002 / US-EPIC-014
#   4. từ hoặc số trần
_TOKEN_RE = re.compile(
    r"\d{1,3}(?:[.,]\d{3})+"
    r"|\d+[.,]\d+"
    r"|[^\W_]+(?:-[^\W_]+)+"
    r"|[^\W_]+"
)
_THOUSANDS_RE = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")
_DECIMAL_RE = re.compile(r"^\d+[.,]\d+$")


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #
def tokenize(text: str) -> list[str]:
    """Split Vietnamese business text into BM25 terms.

    Bốn quy tắc, mỗi quy tắc chống một lỗi đã gặp hoặc chắc chắn sẽ gặp:

    1. Chuẩn hóa NFC trước khi hạ chữ thường. Chunk đến từ ``.md``, ``.docx`` và
       ``.xlsx`` qua ba thư viện khác nhau; tiếng Việt có hai cách mã hóa dấu
       (``ạ`` một codepoint, hoặc ``a`` + dấu tổ hợp). Không NFC thì hai chuỗi
       hiển thị giống hệt nhau lại không khớp token, và hỏng hoàn toàn im lặng.

    2. Số có dấu phân cách hàng nghìn là MỘT token, rồi bỏ dấu phân cách:
       ``20.000.000`` -> ``20000000``. Tách theo dấu chấm thì ``100.000.000`` vỡ
       thành ``100``/``000``/``000`` — mất đúng token phân biệt nhất của nhóm câu
       hỏi version_conflict, mà ``000`` thì có ở khắp nơi nên IDF gần 0.
       :mod:`src.ingestion` đã cố ý render số Excel theo kiểu ``5.000.000`` để
       khớp được với Markdown; hàm này tôn trọng ý đồ đó.
       Chỉ gộp khi các nhóm sau đều đúng 3 chữ số — nếu không thì ``1.5%`` sẽ
       thành ``15`` và ``0.6%`` thành ``06``, sai hẳn nghĩa.

    3. Mã có gạch nối vừa giữ nguyên vừa tách nhỏ: ``BR-002`` ->
       ``br-002``, ``br``, ``002``. Người dùng gõ kiểu nào cũng khớp. Header
       provenance ở đầu MỌI chunk (xem :func:`src.chunking._context_header`) đều
       chứa doc_id, nên đây là tín hiệu rất mạnh.

    4. KHÔNG dùng stopword list. IDF của BM25 tự dìm "là / của / bao nhiêu" về
       gần 0 rồi. Ngược lại, ``"không"`` là từ MANG NGHĨA trong KB này (câu
       adversarial, điều kiện nghiệp vụ dạng "không được phép..."), mà mọi danh
       sách stopword tiếng Việt phổ thông đều xóa nó.
    """
    text = unicodedata.normalize("NFC", text).lower()

    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text):
        if _THOUSANDS_RE.match(raw):
            tokens.append(raw.replace(".", "").replace(",", ""))
        elif _DECIMAL_RE.match(raw):
            # Gộp 1,5 và 1.5 về một dạng; giữ phần thập phân nguyên vẹn.
            tokens.append(raw.replace(",", "."))
        elif "-" in raw:
            tokens.append(raw)
            tokens.extend(part for part in raw.split("-") if part)
        else:
            tokens.append(raw)
    return tokens


# --------------------------------------------------------------------------- #
# Index
# --------------------------------------------------------------------------- #
@dataclass
class BM25Index:
    """A BM25 model plus the chunk ids/metadata it was built from, in order."""

    chunk_ids: list[str]
    metadatas: list[dict]
    bm25: BM25Okapi

    def __len__(self) -> int:
        return len(self.chunk_ids)


# Cache theo persist_dir: dựng lại index là phải gọi collection.get() rồi tokenize
# lại toàn bộ corpus, không đáng làm mỗi lần search.
_INDEX_CACHE: dict[str, BM25Index] = {}


def build_bm25_index(persist_dir: Path | str = CHROMA_DIR) -> BM25Index:
    """Read every chunk out of ChromaDB and fit BM25Okapi over it."""
    collection = get_collection(persist_dir)
    records = collection.get(include=["documents", "metadatas"])

    chunk_ids = list(records["ids"])
    if not chunk_ids:
        raise RuntimeError(
            f"Collection tại {persist_dir} rỗng — chạy src.vectorstore.build_index() trước."
        )

    corpus = [tokenize(doc) for doc in records["documents"]]
    logger.info("BM25: đã index %d chunk từ %s", len(chunk_ids), persist_dir)
    return BM25Index(
        chunk_ids=chunk_ids,
        metadatas=list(records["metadatas"]),
        bm25=BM25Okapi(corpus),
    )


def get_index(persist_dir: Path | str = CHROMA_DIR, refresh: bool = False) -> BM25Index:
    """Return the cached BM25 index for ``persist_dir``, building it if needed.

    ``refresh=True`` bắt buộc dựng lại — cần gọi sau mỗi lần ``build_index()``
    ghi lại collection, nếu không BM25 sẽ chấm trên tập chunk cũ trong khi nhánh
    vector đã dùng tập mới.
    """
    key = str(Path(persist_dir).resolve())
    if refresh or key not in _INDEX_CACHE:
        _INDEX_CACHE[key] = build_bm25_index(persist_dir)
    return _INDEX_CACHE[key]


def clear_cache() -> None:
    """Drop every cached index (dùng giữa các lần rebuild trong cùng process)."""
    _INDEX_CACHE.clear()


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
def search(
    query_text: str,
    top_k: int = 5,
    persist_dir: Path | str = CHROMA_DIR,
    allowed_ids: set[str] | None = None,
) -> list[tuple[str, float]]:
    """Rank chunks lexically. Returns ``[(chunk_id, bm25_score), ...]``, best first.

    ``allowed_ids`` là cách áp metadata filter cho nhánh từ vựng: BM25 không có
    ``where`` như Chroma nên tập ứng viên phải được cắt ở đây, TRƯỚC khi xếp hạng
    và trước khi bước hybrid chuẩn hóa điểm. Quan trọng ở chỗ chuẩn hóa: một
    chunk Deprecated điểm cao mà lọt vào lúc tính ``max`` sẽ nén điểm của tất cả
    chunk còn lại xuống, dù sau đó có bị loại khỏi kết quả.

    Điểm BM25 KHÔNG có thang cố định (xem :mod:`src.hybrid_search`) — chỉ so sánh
    được giữa các chunk trong cùng một query, không so được giữa hai query.
    """
    index = get_index(persist_dir)
    scores = index.bm25.get_scores(tokenize(query_text))

    ranked = [
        (chunk_id, float(score))
        for chunk_id, score in zip(index.chunk_ids, scores)
        if allowed_ids is None or chunk_id in allowed_ids
    ]
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return ranked[:top_k]


if __name__ == "__main__":
    import sys

    # Console Windows mặc định là cp1252, không in được tiếng Việt.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("Tokenizer:")
    for sample in ("Hạn mức 20.000.000 VNĐ", "phí 1.5% theo BR-002", "US-EPIC-014 v2.1"):
        print(f"  {sample:<28} -> {tokenize(sample)}")

    idx = get_index()
    meta_by_id = dict(zip(idx.chunk_ids, idx.metadatas))
    print(f"\nĐã index {len(idx)} chunk\n{'=' * 78}")

    for q in (
        "hạn mức chuyển tiền P2P Tier 2",
        "20.000.000",
        "quy trình đối soát chênh lệch",
    ):
        print(f"\n### {q}")
        print("-" * 78)
        for chunk_id, score in search(q, top_k=5):
            meta = meta_by_id[chunk_id]
            print(
                f"  {score:7.3f}  {meta['doc_id']:<12} {meta['status']:<12}"
                f"{str(meta.get('heading_path', ''))[:38]}"
            )
