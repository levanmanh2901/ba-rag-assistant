import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()

FONT_NAME = "Arial"
HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
SUBHEADER_FILL = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
HEADER_FONT = Font(name=FONT_NAME, bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(name=FONT_NAME, bold=True, size=14, color="1F4E78")
LABEL_FONT = Font(name=FONT_NAME, bold=True, size=10)
NORMAL_FONT = Font(name=FONT_NAME, size=10)
WARN_FONT = Font(name=FONT_NAME, size=10, italic=True, color="C00000")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

meta = [
    ("Mã tài liệu", "LIMIT-001"),
    ("Loại tài liệu", "Limit_SLA_Matrix"),
    ("Phiên bản", "v1.2"),
    ("Trạng thái", "Approved"),
    ("Ngày hiệu lực", "2026-02-01"),
    ("Nguồn gốc số liệu", "BR-002 v3.0 (bản trích xuất để tra cứu nhanh)"),
    ("Chủ sở hữu", "Compliance & Product Team"),
]

def write_meta(ws, start_row=2):
    r = start_row
    for label, val in meta:
        ws.cell(row=r, column=1, value=label).font = LABEL_FONT
        ws.cell(row=r, column=2, value=val).font = NORMAL_FONT
        r += 1
    return r

def style_header_row(ws, row, n_cols):
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER

def style_data(ws, row, n_cols, number_cols=()):
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = NORMAL_FONT
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center" if c > 1 else "left",
                                   vertical="center", wrap_text=True)
        if c in number_cols:
            cell.number_format = "#,##0"

# ---------------- Sheet 1: Han muc theo Tier ----------------
ws1 = wb.active
ws1.title = "HanMuc_Theo_Tier"
ws1["A1"] = "MA TRẬN HẠN MỨC GIAO DỊCH THEO TIER - MANHPAY"
ws1["A1"].font = TITLE_FONT
ws1.merge_cells("A1:G1")
r = write_meta(ws1)

ws1.cell(row=r, column=1, value="Lưu ý: đây là bản trích xuất từ BR-002. Khi có mâu thuẫn, lấy BR-002 làm chuẩn.").font = WARN_FONT
r += 2

headers = ["Loại giao dịch", "Tier 1 (/giao dịch)", "Tier 1 (/ngày)",
           "Tier 2 (/giao dịch)", "Tier 2 (/ngày)",
           "Tier 3 (/giao dịch)", "Tier 3 (/ngày)"]
for i, h in enumerate(headers, start=1):
    ws1.cell(row=r, column=i, value=h)
style_header_row(ws1, r, len(headers))
header_row_1 = r

rows = [
    ("Nạp tiền", 5000000, 5000000, 20000000, 20000000, 100000000, 100000000),
    ("Chuyển tiền P2P", 2000000, 5000000, 10000000, 20000000, 50000000, 100000000),
    ("Thanh toán QR", 1000000, 5000000, 5000000, 20000000, 20000000, 100000000),
    ("Rút tiền về ngân hàng", 2000000, 5000000, 10000000, 20000000, 50000000, 100000000),
]
r += 1
for row_data in rows:
    for i, v in enumerate(row_data, start=1):
        ws1.cell(row=r, column=i, value=v)
    style_data(ws1, r, 7, number_cols=(2, 3, 4, 5, 6, 7))
    r += 1

# Row tinh tong dung cong thuc
r += 1
ws1.cell(row=r, column=1, value="TỔNG hạn mức/ngày (mọi loại GD)").font = LABEL_FONT
for col in (3, 5, 7):
    letter = get_column_letter(col)
    ws1.cell(row=r, column=col,
             value=f"=SUM({letter}{header_row_1+1}:{letter}{header_row_1+4})")
    ws1.cell(row=r, column=col).number_format = "#,##0"
    ws1.cell(row=r, column=col).font = LABEL_FONT
    ws1.cell(row=r, column=col).border = BORDER
    ws1.cell(row=r, column=col).alignment = Alignment(horizontal="center")

widths1 = [26, 18, 16, 18, 16, 18, 16]
for i, w in enumerate(widths1, start=1):
    ws1.column_dimensions[get_column_letter(i)].width = w

# ---------------- Sheet 2: SLA xu ly ----------------
ws2 = wb.create_sheet("SLA_Xu_Ly")
ws2["A1"] = "MA TRẬN SLA XỬ LÝ NGHIỆP VỤ - MANHPAY"
ws2["A1"].font = TITLE_FONT
ws2.merge_cells("A1:E1")
r = write_meta(ws2)
r += 1

headers2 = ["Nghiệp vụ", "Loại xử lý", "SLA cam kết", "Tài liệu nguồn", "Ghi chú"]
for i, h in enumerate(headers2, start=1):
    ws2.cell(row=r, column=i, value=h)
style_header_row(ws2, r, len(headers2))
r += 1

sla_rows = [
    ("Xác thực eKYC Tier 1 → Tier 2", "Tự động", "Dưới 5 phút", "SOP-002", "Tỷ lệ tự động thành công mục tiêu > 80%"),
    ("Xác thực eKYC Tier 2 → Tier 3", "Bán tự động", "Dưới 24 giờ làm việc", "SOP-002", "Phụ thuộc đối tác định danh"),
    ("Xét duyệt eKYC thủ công", "Thủ công", "Dưới 4 giờ làm việc", "SOP-002", "Khi face matching dưới 85%"),
    ("Khiếu nại giao dịch trùng lặp", "Thủ công", "3 ngày làm việc", "SOP-003", ""),
    ("Khiếu nại giao dịch không nhận diện", "Thủ công", "7 ngày làm việc", "SOP-003", "Có thể cần điều tra Risk & Fraud"),
    ("Khiếu nại không nhận được tiền", "Thủ công", "3 ngày làm việc", "SOP-003", ""),
    ("Tranh chấp với merchant", "Thủ công", "10 ngày làm việc", "SOP-003", ""),
    ("Đối soát giao dịch nạp/rút tiền", "Tự động", "Trong 24 giờ", "SOP-005 / BRD-001", "Chạy tự động lúc 02:00 hàng ngày"),
    ("Xử lý chênh lệch đối soát", "Thủ công", "Trước 17:00 ngày kế tiếp", "SOP-005", ""),
    ("Xét duyệt hồ sơ merchant mới", "Thủ công", "3-5 ngày làm việc", "FAQ-002", ""),
]
for row_data in sla_rows:
    for i, v in enumerate(row_data, start=1):
        ws2.cell(row=r, column=i, value=v)
    style_data(ws2, r, 5)
    ws2.cell(row=r, column=1).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws2.cell(row=r, column=5).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    r += 1

widths2 = [34, 16, 24, 20, 42]
for i, w in enumerate(widths2, start=1):
    ws2.column_dimensions[get_column_letter(i)].width = w

wb.save("MaTran_HanMuc_SLA_ManhPay_v1.2.xlsx")
print("Saved.")
