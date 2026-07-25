import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()

FONT_NAME = "Arial"
HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(name=FONT_NAME, bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(name=FONT_NAME, bold=True, size=14, color="1F4E78")
LABEL_FONT = Font(name=FONT_NAME, bold=True, size=10)
NORMAL_FONT = Font(name=FONT_NAME, size=10)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def style_header_row(ws, row, n_cols):
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER

def style_data_cell(ws, row, col, number_format=None):
    cell = ws.cell(row=row, column=col)
    cell.font = NORMAL_FONT
    cell.border = BORDER
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    if number_format:
        cell.number_format = number_format
    return cell

# ---------- Sheet 1: Bang Phi Khach Hang ----------
ws1 = wb.active
ws1.title = "BangPhi_KhachHang"

ws1["A1"] = "BẢNG PHÍ GIAO DỊCH KHÁCH HÀNG CÁ NHÂN - MANHPAY"
ws1["A1"].font = TITLE_FONT
ws1.merge_cells("A1:F1")

meta = [
    ("Mã tài liệu", "FEE-001"),
    ("Loại tài liệu", "Fee_Pricing_Table"),
    ("Phiên bản", "v2.4"),
    ("Trạng thái", "Approved"),
    ("Ngày hiệu lực", "2026-04-01"),
    ("Chủ sở hữu", "Finance & Product Team"),
]
r = 2
for label, val in meta:
    ws1.cell(row=r, column=1, value=label).font = LABEL_FONT
    ws1.cell(row=r, column=2, value=val).font = NORMAL_FONT
    r += 1

start = r + 1
headers = ["Loại giao dịch", "Phương thức", "Mức phí", "Phí tối thiểu (VNĐ)", "Ví dụ: GD 2.000.000 VNĐ", "Ghi chú"]
for i, h in enumerate(headers, start=1):
    ws1.cell(row=start, column=i, value=h)
style_header_row(ws1, start, len(headers))

rows = [
    ("Nạp tiền", "Liên kết ngân hàng (Napas 247)", 0.0, 0, "Miễn phí"),
    ("Nạp tiền", "Thẻ ATM nội địa", 0.0, 0, "Miễn phí"),
    ("Nạp tiền", "Thẻ quốc tế Visa/Mastercard", 0.015, 5000, "Phí thu hộ đối tác xử lý thẻ quốc tế"),
    ("Chuyển tiền P2P", "Trong hệ sinh thái ManhPay", 0.0, 0, "Miễn phí, không giới hạn số lần"),
    ("Chuyển tiền", "Ra tài khoản ngân hàng khác (Napas 247)", 0.0, 0, "Miễn phí cho giao dịch dưới 10 triệu/lần"),
    ("Chuyển tiền", "Ra tài khoản ngân hàng khác - trên 10 triệu/lần", 0.001, 3000, "Áp dụng phần vượt 10 triệu"),
    ("Thanh toán QR", "Quét QR merchant (khách hàng trả)", 0.0, 0, "Miễn phí"),
    ("Rút tiền", "Về tài khoản ngân hàng liên kết", 0.0, 0, "Miễn phí, tối đa 5 lần/ngày, từ lần thứ 6 phí 0.3%"),
]

row_i = start + 1
for name, method, pct, min_fee, note in rows:
    ws1.cell(row=row_i, column=1, value=name)
    ws1.cell(row=row_i, column=2, value=method)
    ws1.cell(row=row_i, column=3, value=pct)
    ws1.cell(row=row_i, column=4, value=min_fee)
    # formula: fee = MAX(2,000,000 * pct, min_fee) but if pct=0 -> 0
    col_c = get_column_letter(3)
    col_d = get_column_letter(4)
    formula = f'=IF({col_c}{row_i}=0,0,MAX(2000000*{col_c}{row_i},{col_d}{row_i}))'
    ws1.cell(row=row_i, column=5, value=formula)
    ws1.cell(row=row_i, column=6, value=note)
    for c in range(1, 7):
        style_data_cell(ws1, row_i, c)
    ws1.cell(row=row_i, column=3).number_format = "0.0%"
    ws1.cell(row=row_i, column=4).number_format = "#,##0"
    ws1.cell(row=row_i, column=5).number_format = "#,##0"
    row_i += 1

ws1.column_dimensions["A"].width = 20
ws1.column_dimensions["B"].width = 32
ws1.column_dimensions["C"].width = 12
ws1.column_dimensions["D"].width = 16
ws1.column_dimensions["E"].width = 20
ws1.column_dimensions["F"].width = 40

# ---------- Sheet 2: Bang Phi Merchant ----------
ws2 = wb.create_sheet("BangPhi_Merchant")
ws2["A1"] = "BẢNG PHÍ MERCHANT - MANHPAY"
ws2["A1"].font = TITLE_FONT
ws2.merge_cells("A1:E1")

r = 2
for label, val in meta:
    ws2.cell(row=r, column=1, value=label).font = LABEL_FONT
    ws2.cell(row=r, column=2, value=val).font = NORMAL_FONT
    r += 1

start2 = r + 1
headers2 = ["Hạng Merchant", "Doanh thu tháng (VNĐ)", "Phí QR (%)", "Phí thẻ (%)", "Ghi chú"]
for i, h in enumerate(headers2, start=1):
    ws2.cell(row=start2, column=i, value=h)
style_header_row(ws2, start2, len(headers2))

merchant_rows = [
    ("Hạng Đồng", "Dưới 50.000.000", 0.012, 0.022, "Merchant mới, chưa đủ 3 tháng hoạt động"),
    ("Hạng Bạc", "50.000.000 - 200.000.000", 0.010, 0.020, "Merchant hoạt động ổn định"),
    ("Hạng Vàng", "200.000.000 - 1.000.000.000", 0.008, 0.018, "Merchant doanh thu cao"),
    ("Hạng Kim Cương", "Trên 1.000.000.000", 0.006, 0.015, "Merchant chiến lược, có hợp đồng riêng theo thỏa thuận"),
]
row_i = start2 + 1
for tier, rev, qr_fee, card_fee, note in merchant_rows:
    ws2.cell(row=row_i, column=1, value=tier)
    ws2.cell(row=row_i, column=2, value=rev)
    ws2.cell(row=row_i, column=3, value=qr_fee)
    ws2.cell(row=row_i, column=4, value=card_fee)
    ws2.cell(row=row_i, column=5, value=note)
    for c in range(1, 6):
        style_data_cell(ws2, row_i, c)
    ws2.cell(row=row_i, column=3).number_format = "0.0%"
    ws2.cell(row=row_i, column=4).number_format = "0.0%"
    row_i += 1

ws2.column_dimensions["A"].width = 16
ws2.column_dimensions["B"].width = 24
ws2.column_dimensions["C"].width = 12
ws2.column_dimensions["D"].width = 12
ws2.column_dimensions["E"].width = 45

wb.save("BangPhi_ManhPay_v2.4.xlsx")
print("Saved.")
