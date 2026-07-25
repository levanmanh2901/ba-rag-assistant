---
doc_id: INT-001
doc_type: IntegrationSpec
module: Tich_Hop_Ngan_Hang
title: "Đặc tả tích hợp nghiệp vụ - Kết nối Napas 247"
version: "1.3"
status: Approved
effective_date: 2026-02-01
last_updated: 2026-02-01
owner: Engineering & Product Team
---

# 1. Mục đích
Mô tả ở mức nghiệp vụ (business level) cách hệ thống ManhPay tích hợp với hệ thống chuyển mạch tài chính quốc gia Napas 247, phục vụ các luồng nạp tiền, rút tiền và chuyển tiền liên ngân hàng. Tài liệu này dành cho BA/PO, không đi sâu chi tiết kỹ thuật cấp mã nguồn.

# 2. Các luồng nghiệp vụ sử dụng Napas 247

| Luồng | Mô tả | Tài liệu nghiệp vụ liên quan |
|---|---|---|
| Nạp tiền từ ngân hàng liên kết | Khách hàng chuyển tiền từ tài khoản ngân hàng vào ví | BRD-001 |
| Rút tiền về ngân hàng | Khách hàng chuyển tiền từ ví về tài khoản ngân hàng | BRD-004 |
| Liên kết tài khoản ngân hàng | Xác thực chủ tài khoản trước khi cho phép giao dịch | SOP-002 |

# 3. Các trường dữ liệu nghiệp vụ quan trọng

| Trường | Ý nghĩa nghiệp vụ | Lưu ý |
|---|---|---|
| transaction_reference | Mã tham chiếu duy nhất của giao dịch | Dùng để đối soát với đối tác, độ dài có thể thay đổi theo đối tác (xem INC-001) |
| idempotency_key | Khóa chống xử lý trùng lặp | Bắt buộc với mọi giao dịch ghi nợ/ghi có |
| account_holder_name | Tên chủ tài khoản ngân hàng | Phải khớp với thông tin eKYC của khách hàng |
| response_code | Mã kết quả giao dịch từ Napas | Quyết định trạng thái hiển thị cho khách hàng |
| settlement_date | Ngày bù trừ thực tế | Dùng cho báo cáo đối soát tài chính |

# 4. Nguyên tắc xử lý lỗi nghiệp vụ

- **Timeout không có phản hồi:** không được coi là thất bại. Giao dịch chuyển sang trạng thái "Đang xử lý", đưa vào hàng đợi đối soát theo SOP-005.
- **Phản hồi thành công nhưng số dư không khớp:** ưu tiên bảo vệ quyền lợi khách hàng, tạm ghi nhận theo phản hồi của Napas, đánh dấu chênh lệch để đối soát cuối ngày.
- **Giao dịch trùng lặp:** hệ thống phải từ chối dựa trên idempotency_key, không được ghi nhận hai lần.

# 5. Cam kết dịch vụ (SLA) với đối tác
- Thời gian phản hồi trung bình của Napas 247: dưới 3 giây
- Cửa sổ bảo trì định kỳ: thường vào khung 23:00 - 01:00, đối tác thông báo trước tối thiểu 48 giờ
- Trong thời gian bảo trì, hệ thống ManhPay phải hiển thị thông báo rõ ràng cho khách hàng thay vì báo lỗi kỹ thuật chung chung

# 6. Lịch sử thay đổi
| Phiên bản | Ngày | Nội dung thay đổi |
|---|---|---|
| 1.0 | 2025-01-15 | Khởi tạo |
| 1.2 | 2025-09-01 | Bổ sung nguyên tắc xử lý timeout |
| 1.3 | 2026-02-01 | Bổ sung lưu ý về độ dài transaction_reference sau sự cố INC-001 |
