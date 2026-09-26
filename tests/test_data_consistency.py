"""Cross-document business-rule consistency checks over the knowledge base.

Khác hẳn ``tests/test_ingestion.py`` và ``tests/test_chunking.py``: hai file đó
kiểm CẤU TRÚC (đọc được không, đủ trường metadata không, bảng có vỡ không). File
này kiểm NỘI DUNG NGHIỆP VỤ có mâu thuẫn nhau không.

Đây là thứ trả lời câu hỏi "tiêu chí nào bảo đảm bộ dữ liệu mô phỏng nhất quán"
bằng một lệnh chạy được, thay vì bằng một lời hứa trong báo cáo. Bộ dữ liệu được
thiết kế quanh nguyên tắc **single source of truth** (BR-002 là nguồn gốc duy
nhất cho hạn mức, FEE-001 cho biểu phí; BRD/SOP/FAQ chỉ tham chiếu lại) — mà một
nguyên tắc không được kiểm tự động thì sẽ âm thầm vỡ ngay lần sửa tài liệu đầu
tiên.

Mọi con số đều ĐỌC TỪ FILE, không hardcode: test hardcode 400.000.000 thì nó chỉ
canh chính nó, không canh được quan hệ giữa hai tài liệu.

KHÔNG gọi API, không nạp model — chỉ dùng :func:`src.ingestion.ingest_all`.
"""

from __future__ import annotations

import json
import re

import pytest

from src.ingestion import DEFAULT_CATALOG, ingest_all

# Số tiền kiểu Việt Nam: 100.000.000 / 20.000.000. Bắt buộc có ít nhất một nhóm
# 3 chữ số, nếu không thì "1.5" trong "1.5%" cũng lọt.
_AMOUNT_RE = re.compile(r"\d{1,3}(?:\.\d{3})+")

# Hạn mức NGÀY của Tier 3, ví dụ "100.000.000 VNĐ/ngày". Cố ý đòi "VNĐ/ngày" dính
# ngay sau số: BRD-003 ghi "Tier 3: tối đa 20.000.000 VNĐ/giao dịch" (hạn mức mỗi
# GIAO DỊCH của QR, đúng theo BR-002) nên không được bắt nhầm sang.
_TIER3_DAILY_RE = re.compile(
    r"tier\s*3\b.*?(\d{1,3}(?:\.\d{3})+)\s*VNĐ\s*/\s*ngày", re.IGNORECASE
)

_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


@pytest.fixture(scope="module")
def docs():
    """Ingest the knowledge base once for the whole module."""
    return {doc["doc_id"]: doc for doc in ingest_all()}


@pytest.fixture(scope="module")
def catalog():
    with open(DEFAULT_CATALOG, encoding="utf-8") as handle:
        return json.load(handle)


# --------------------------------------------------------------------------- #
# Helpers — đọc số ra khỏi bảng Markdown
# --------------------------------------------------------------------------- #
def _to_int(text: str) -> int:
    """``"100.000.000"`` -> ``100000000``."""
    return int(text.replace(".", ""))


def _table_rows(content: str, header_starts_with: str) -> list[list[str]]:
    """Return the rows of the Markdown table whose header starts with the given text.

    Trả về cả dòng header (phần tử 0) để hàm gọi tự tìm chỉ số cột theo TÊN, thay
    vì đếm cột bằng tay — đếm tay thì thêm một cột vào Excel là test sai lặng lẽ.
    """
    rows: list[list[str]] = []
    collecting = False
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if collecting:
                break
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not collecting:
            if stripped.startswith(header_starts_with):
                collecting = True
                rows.append(cells)
            continue
        if set("".join(cells)) <= set("-: "):  # dòng phân cách |---|---|
            continue
        rows.append(cells)
    return rows


def _column_index(header: list[str], *needles: str) -> int:
    """Index of the first header cell containing every needle (case-insensitive)."""
    for index, cell in enumerate(header):
        low = cell.lower()
        if all(needle.lower() in low for needle in needles):
            return index
    raise AssertionError(
        f"Không tìm thấy cột chứa {needles} trong header: {header}"
    )


def _tier3_daily_limit_table(content: str) -> tuple[dict[str, int], int | None]:
    """Parse a Tier limit table into ``({loại giao dịch: hạn mức/ngày}, dòng TỔNG)``.

    Cùng một hình dạng bảng xuất hiện ở BR-002 (`.md`) và LIMIT-001 (`.xlsx`), nên
    một hàm đọc được cả hai — đó chính là điều kiện để so chúng với nhau.
    """
    rows = _table_rows(content, "| Loại giao dịch")
    assert rows, "Không tìm thấy bảng hạn mức theo Tier"

    header, *body = rows
    column = _column_index(header, "tier 3", "/ngày")

    per_type: dict[str, int] = {}
    total: int | None = None
    for cells in body:
        if len(cells) <= column:
            continue
        label, value = cells[0], cells[column]
        match = _AMOUNT_RE.fullmatch(value)
        if match is None:
            continue
        if label.upper().startswith("TỔNG"):
            total = _to_int(value)
        else:
            per_type[label] = _to_int(value)
    return per_type, total


# --------------------------------------------------------------------------- #
# 1. Quan hệ số học giữa LIMIT-001 (.xlsx) và BR-002 (.md)
# --------------------------------------------------------------------------- #
def test_limit001_total_equals_br002_tier3_times_transaction_types(docs):
    """Dòng TỔNG của LIMIT-001 phải = hạn mức Tier 3/ngày × số loại giao dịch.

    Ràng buộc nghiệp vụ: LIMIT-001 tự khai trong phần đầu sheet rằng nó là "bản
    trích xuất để tra cứu nhanh" từ BR-002 v3.0. Một bản trích xuất mà lệch khỏi
    nguồn gốc thì phá vỡ nguyên tắc single source of truth, và Q018 ("tổng hạn mức
    mỗi ngày của Tier 3") sẽ có hai đáp án khác nhau tùy hệ thống truy hồi trúng
    tài liệu nào.

    Đây là ràng buộc đi XUYÊN hai định dạng file (`.xlsx` và `.md`) và xuyên hai
    thư viện đọc khác nhau, nên nó cũng gián tiếp canh luôn việc ``openpyxl`` đọc
    ra giá trị đã tính chứ không phải chuỗi công thức ``=SUM(...)``.

    Không hardcode 400.000.000: cả hai vế đều đọc từ file.
    """
    br002_per_type, _ = _tier3_daily_limit_table(docs["BR-002"]["content"])
    limit_per_type, limit_total = _tier3_daily_limit_table(docs["LIMIT-001"]["content"])

    assert limit_total is not None, "LIMIT-001 không có dòng TỔNG hạn mức/ngày"
    assert br002_per_type, "BR-002 không đọc ra được hạn mức Tier 3/ngày nào"

    # BR-002 đặt cùng một mức /ngày cho cả 4 loại giao dịch — quy tắc cộng dồn
    # trong tài liệu nói hạn mức ngày áp cho từng loại, còn TỔNG là tổng của chúng.
    distinct = set(br002_per_type.values())
    assert len(distinct) == 1, (
        f"BR-002 có nhiều mức Tier 3/ngày khác nhau: {br002_per_type}. "
        "Phép nhân dưới đây không còn đúng, phải sửa lại test theo quy tắc mới."
    )

    per_type = distinct.pop()
    expected = per_type * len(br002_per_type)
    assert limit_total == expected, (
        f"MÂU THUẪN DỮ LIỆU: LIMIT-001 ghi TỔNG = {limit_total:,} nhưng BR-002 có "
        f"{len(br002_per_type)} loại giao dịch × {per_type:,}/ngày = {expected:,}."
    )

    # Và từng dòng của bản trích xuất cũng phải khớp bản gốc, không chỉ dòng tổng.
    assert set(limit_per_type.values()) == {per_type}, (
        f"LIMIT-001 có dòng lệch khỏi BR-002: {limit_per_type}"
    )


# --------------------------------------------------------------------------- #
# 2. Single source of truth cho hạn mức Tier 3
# --------------------------------------------------------------------------- #
def test_every_document_quotes_the_same_tier3_daily_limit(docs):
    """Mọi tài liệu còn hiệu lực nhắc hạn mức Tier 3/ngày phải khớp BR-002.

    Ràng buộc nghiệp vụ: BR-002 là nguồn gốc duy nhất của hạn mức; BRD-001,
    BRD-002, BRD-004 chỉ được TRÍCH LẠI con số đó. Nếu một BRD ghi lệch, hệ thống
    RAG sẽ trả lời khác nhau tùy chunk nào lọt top-k — đúng loại lỗi mà nhóm câu
    hỏi ``version_conflict`` sinh ra để bắt, nhưng lần này là mâu thuẫn KHÔNG chủ
    đích nên không có gì trong bộ đánh giá phát hiện được.

    BR-002-v1 được miễn trừ: nó là bản Deprecated mang số liệu mâu thuẫn CÓ CHỦ
    ĐÍCH (Tier 3 = 50 triệu), nền tảng của cả nhóm ``version_conflict``. Miễn trừ
    này bám theo ``status`` trong metadata chứ không liệt kê doc_id bằng tay, nên
    thêm một bản Deprecated mới cũng không phải sửa test.

    CR-LOG-001 không bị bắt vì nó viết "từ 50.000.000 lên 100.000.000 VNĐ" — chuỗi
    "VNĐ/ngày" không dính ngay sau số. Đúng về nghĩa: nhật ký thay đổi có quyền
    nhắc cả giá trị cũ lẫn mới.
    """
    br002_per_type, _ = _tier3_daily_limit_table(docs["BR-002"]["content"])
    canonical = set(br002_per_type.values()).pop()

    offenders: list[str] = []
    checked: list[str] = []
    for doc_id, doc in sorted(docs.items()):
        if doc["metadata"].get("status") == "Deprecated":
            continue
        for amount in _TIER3_DAILY_RE.findall(doc["content"]):
            checked.append(doc_id)
            if _to_int(amount) != canonical:
                offenders.append(f"{doc_id} ghi {amount} VNĐ/ngày")

    assert checked, (
        "Không tài liệu nào khớp mẫu 'Tier 3 ... VNĐ/ngày' — regex đã lệch khỏi "
        "cách viết trong tài liệu, test đang không kiểm gì cả."
    )
    assert not offenders, (
        f"MÂU THUẪN DỮ LIỆU: BR-002 quy định Tier 3 = {canonical:,} VNĐ/ngày, "
        f"nhưng {offenders}"
    )


# --------------------------------------------------------------------------- #
# 3. Single source of truth cho biểu phí
# --------------------------------------------------------------------------- #
def test_brd001_quotes_fee001_international_card_fee(docs):
    """Phí nạp thẻ quốc tế nêu trong BRD-001 phải khớp bảng phí FEE-001.

    Ràng buộc nghiệp vụ: FEE-001 là nguồn gốc duy nhất của biểu phí, BRD-001 chỉ
    diễn giải lại ("xem chi tiết đầy đủ tại bảng phí"). Q013 kỳ vọng CẢ HAI tài
    liệu cùng xuất hiện trong nguồn đúng, nên chúng buộc phải nói cùng một con số.

    Kiểm hai giá trị chứ không chỉ một: mức phần trăm (1.5%) VÀ mức phí tối thiểu
    (5.000 VNĐ). Q015 ("nạp 2.000.000 thì bị trừ phí bao nhiêu") phụ thuộc vào cả
    hai — thiếu mức tối thiểu thì không kết luận được 30.000 là đúng hay sai.
    """
    rows = _table_rows(docs["FEE-001"]["content"], "| Loại giao dịch")
    assert rows, "Không tìm thấy bảng phí trong FEE-001"
    header, *body = rows

    method_col = _column_index(header, "phương thức")
    rate_col = _column_index(header, "mức phí")
    min_col = _column_index(header, "tối thiểu")

    matching = [
        cells
        for cells in body
        if len(cells) > max(method_col, rate_col, min_col)
        and "quốc tế" in cells[method_col].lower()
    ]
    assert len(matching) == 1, (
        f"Cần đúng 1 dòng thẻ quốc tế trong FEE-001, tìm thấy {len(matching)}"
    )
    row = matching[0]

    fee_rate = _PERCENT_RE.search(row[rate_col])
    assert fee_rate, f"Không đọc được mức phí từ ô {row[rate_col]!r}"
    fee_min = _AMOUNT_RE.search(row[min_col]) or re.search(r"\d+", row[min_col])
    assert fee_min, f"Không đọc được phí tối thiểu từ ô {row[min_col]!r}"

    # Câu văn trong BRD-001: "Nạp tiền qua thẻ quốc tế: phí 1.5% giá trị giao dịch,
    # tối thiểu 5.000 VNĐ (...)".
    brd_lines = [
        line
        for line in docs["BRD-001"]["content"].splitlines()
        if "quốc tế" in line.lower() and "%" in line
    ]
    assert len(brd_lines) == 1, (
        f"Cần đúng 1 dòng nêu phí thẻ quốc tế trong BRD-001, tìm thấy {len(brd_lines)}"
    )
    line = brd_lines[0]

    brd_rate = _PERCENT_RE.search(line)
    assert brd_rate, f"Không đọc được mức phí từ BRD-001: {line!r}"
    brd_min = re.search(r"tối thiểu\s+([\d.]+)", line, re.IGNORECASE)
    assert brd_min, f"Không đọc được phí tối thiểu từ BRD-001: {line!r}"

    assert float(brd_rate.group(1)) == float(fee_rate.group(1)), (
        f"MÂU THUẪN DỮ LIỆU: FEE-001 ghi {fee_rate.group(1)}%, "
        f"BRD-001 ghi {brd_rate.group(1)}%"
    )
    assert _to_int(brd_min.group(1).rstrip(".")) == _to_int(fee_min.group(0)), (
        f"MÂU THUẪN DỮ LIỆU: FEE-001 ghi phí tối thiểu {fee_min.group(0)}, "
        f"BRD-001 ghi {brd_min.group(1)}"
    )


# --------------------------------------------------------------------------- #
# 4. Tham chiếu chéo không được trỏ vào hư không
# --------------------------------------------------------------------------- #
# Hai mã này CỐ Ý không tồn tại trong Knowledge Base. Cả hai đều nói về tài khoản
# doanh nghiệp, và chúng là nền tảng của câu bẫy Q032 ("Quy trình mở tài khoản
# doanh nghiệp gồm những bước nào?") — câu kiểm tra hệ thống có phân biệt được
# "ĐƯỢC NHẮC TỚI" với "CÓ NỘI DUNG" hay không (quy tắc 4 của SYSTEM_PROMPT).
#
# Khai báo tường minh ở đây để chúng là NGOẠI LỆ ĐƯỢC KIỂM SOÁT chứ không phải dữ
# liệu thiếu: ai xóa hai mã này khỏi tài liệu sẽ làm Q032 mất ý nghĩa mà không có
# gì báo, còn ai thêm một mã treo mới sẽ bị test này chặn.
DANGLING_BY_DESIGN = {
    "SOP-007": "Quy trình mở tài khoản doanh nghiệp — nhắc trong SOP-002, dùng cho Q032",
    "BR-005": "Hạn mức tài khoản doanh nghiệp — nhắc trong BR-002, dùng cho Q032",
}

_DOC_CODE_RE = re.compile(r"\b[A-Z]{2,}(?:-[A-Z]+)*-\d+(?:-v\d+)?\b")


def _doc_family(doc_id: str) -> str:
    """``"BR-002-v1"`` -> ``"BR"``, ``"US-EPIC-014"`` -> ``"US-EPIC"``."""
    return re.sub(r"-\d+(?:-v\d+)?$", "", doc_id)


def test_every_referenced_doc_id_exists_in_the_catalog(docs, catalog):
    """Mã tài liệu nhắc trong nội dung phải tồn tại trong metadata_catalog.json.

    Ràng buộc nghiệp vụ: bộ dữ liệu được xây quanh một mạng tham chiếu chéo
    (BR-002 ← các BRD; INC-001 → SOP-005 + INT-001 → US-EPIC-021). Một tham chiếu
    trỏ vào tài liệu không tồn tại sẽ khiến hệ thống trả lời "có tài liệu X" trong
    khi không truy hồi được nội dung nào của X — đúng kiểu hallucination gián tiếp
    mà quy tắc 4 của SYSTEM_PROMPT phải chặn.

    Chỉ xét mã thuộc các HỌ TÀI LIỆU có thật trong catalog (BR, BRD, SOP, FEE,
    LIMIT, INC, INT, FAQ, GL, CR-LOG, US-EPIC), và họ được suy ra TỪ CHÍNH CATALOG
    chứ không liệt kê tay. Nhờ vậy các mã cùng hình dạng nhưng không phải tài liệu
    được bỏ qua đúng cách:

    * ``FR-001``..``FR-006`` — mã rule chống gian lận, nội dung nằm trong BR-004;
    * ``MANHPAY-1425``, ``MANHPAY-EPIC-021`` — mã ticket/epic Jira;
    * ``CR-2025-018`` — mã change request bên trong CR-LOG-001.

    Liệt kê tay các họ này sẽ hỏng ngay khi catalog có thêm loại tài liệu mới.
    """
    known = {entry["doc_id"] for entry in catalog}
    families = {_doc_family(doc_id) for doc_id in known}

    dangling: dict[str, set[str]] = {}
    for doc_id, doc in docs.items():
        for code in set(_DOC_CODE_RE.findall(doc["content"])):
            if code in known or _doc_family(code) not in families:
                continue
            dangling.setdefault(code, set()).add(doc_id)

    unexpected = {
        code: sorted(where)
        for code, where in dangling.items()
        if code not in DANGLING_BY_DESIGN
    }
    assert not unexpected, (
        f"Tham chiếu trỏ vào tài liệu KHÔNG tồn tại: {unexpected}. Hoặc thêm tài "
        f"liệu vào catalog, hoặc khai báo vào DANGLING_BY_DESIGN kèm lý do."
    )

    # Chiều ngược lại: ngoại lệ đã khai báo thì phải thật sự còn được nhắc tới.
    # Không có vế này thì DANGLING_BY_DESIGN sẽ mục ruỗng dần mà không ai biết,
    # và Q032 lặng lẽ mất mất tiền đề.
    missing = sorted(set(DANGLING_BY_DESIGN) - set(dangling))
    assert not missing, (
        f"{missing} được khai là tham chiếu treo có chủ đích nhưng KHÔNG còn tài "
        "liệu nào nhắc tới — câu bẫy Q032 mất tiền đề. Gỡ khỏi DANGLING_BY_DESIGN "
        "hoặc khôi phục câu tham chiếu trong tài liệu."
    )
