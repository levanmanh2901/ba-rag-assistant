---
doc_id: BR-002
doc_type: BusinessRules
module: Han_Muc_Giao_Dich
title: "Bảng quy tắc nghiệp vụ - Hạn mức giao dịch theo cấp độ tài khoản (Tier)"
version: "3.0"
status: Approved
effective_date: 2026-02-01
last_updated: 2026-02-01
owner: Compliance & Product Team
---

# 1. Mục đích

Tài liệu này là nguồn tham chiếu duy nhất (single source of truth) cho toàn bộ hạn mức giao dịch áp dụng trên sản phẩm ManhPay. Mọi BRD/SOP khác khi đề cập đến hạn mức phải tham chiếu về tài liệu này, không tự định nghĩa lại.

# 2. Phân loại Tier tài khoản

| Tier | Điều kiện xác thực | Mô tả |
|---|---|---|
| Tier 1 | Chưa xác thực eKYC, chỉ đăng ký bằng SĐT | Tài khoản mới, quyền hạn thấp nhất |
| Tier 2 | Đã xác thực eKYC cơ bản (chụp CCCD + selfie) | Tài khoản phổ thông |
| Tier 3 | Đã xác thực eKYC nâng cao + đối chiếu với cơ sở dữ liệu quốc gia về dân cư | Tài khoản đầy đủ quyền hạn |

# 3. Bảng hạn mức chi tiết (áp dụng từ 01/02/2026)

| Loại giao dịch | Tier 1 (/giao dịch) | Tier 1 (/ngày) | Tier 2 (/giao dịch) | Tier 2 (/ngày) | Tier 3 (/giao dịch) | Tier 3 (/ngày) |
|---|---|---|---|---|---|---|
| Nạp tiền | 5.000.000 | 5.000.000 | 20.000.000 | 20.000.000 | 100.000.000 | 100.000.000 |
| Chuyển tiền P2P | 2.000.000 | 5.000.000 | 10.000.000 | 20.000.000 | 50.000.000 | 100.000.000 |
| Thanh toán QR | 1.000.000 | 5.000.000 | 5.000.000 | 20.000.000 | 20.000.000 | 100.000.000 |
| Rút tiền về NH | 2.000.000 | 5.000.000 | 10.000.000 | 20.000.000 | 50.000.000 | 100.000.000 |

Lưu ý quan trọng: hạn mức "/ngày" là tổng cộng dồn của TẤT CẢ giao dịch cùng loại trong ngày, tính theo giờ Việt Nam (GMT+7), reset lúc 00:00.

# 4. Quy tắc nâng Tier

- Từ Tier 1 lên Tier 2: khách hàng tự thực hiện eKYC cơ bản trong app, xử lý tự động dưới 5 phút
- Từ Tier 2 lên Tier 3: yêu cầu xác thực bổ sung qua đối tác định danh điện tử (VNeID hoặc tương đương), xử lý trong vòng 24 giờ làm việc
- Tài khoản bị hạ Tier tự động nếu phát hiện dấu hiệu gian lận (được xử lý theo SOP riêng về phòng chống rửa tiền - AML)

# 5. Ngoại lệ đặc biệt

- Trong giai đoạn khuyến mãi (VD: Tết, Black Friday), Product team có thể đề xuất nâng tạm thời hạn mức Tier 1/Tier 2 lên tối đa 1.5 lần, phải có phê duyệt từ Compliance trước khi triển khai
- Tài khoản doanh nghiệp (Business Account) áp dụng bảng hạn mức riêng, không thuộc phạm vi tài liệu này (xem BR-005 Hạn mức tài khoản doanh nghiệp)

# 6. Lịch sử thay đổi
| Phiên bản | Ngày | Nội dung thay đổi |
|---|---|---|
| 1.0 | 2024-10-01 | Khởi tạo |
| 2.0 | 2025-06-15 | Tăng hạn mức Tier 3 từ 50 triệu lên 100 triệu để cạnh tranh |
| 3.0 | 2026-02-01 | Thống nhất áp dụng hạn mức /ngày theo giờ Việt Nam, làm rõ quy tắc cộng dồn |
