---
doc_id: BRD-001
doc_type: BRD
module: Nap_Tien
title: "Business Requirement Document - Tính năng Nạp tiền vào ví ManhPay"
version: "1.2"
status: Approved
effective_date: 2026-03-01
last_updated: 2026-03-01
owner: Product Team
---

# 1. Mục tiêu nghiệp vụ

Cho phép khách hàng nạp tiền vào ví điện tử ManhPay từ tài khoản ngân hàng liên kết, thẻ ATM nội địa (Napas), hoặc thẻ quốc tế (Visa/Mastercard), nhằm tăng số dư khả dụng để thực hiện các giao dịch thanh toán, chuyển tiền trong hệ sinh thái ManhPay.

# 2. Phạm vi (Scope)

## Trong phạm vi
- Nạp tiền qua liên kết ngân hàng (Napas 247)
- Nạp tiền qua thẻ ATM nội địa
- Nạp tiền qua thẻ quốc tế Visa/Mastercard
- Nạp tiền qua mã QR tại điểm giao dịch đối tác

## Ngoài phạm vi
- Nạp tiền bằng tiền mặt tại quầy giao dịch (thuộc BRD riêng: BRD-Cash-Agent)
- Nạp tiền từ ví điện tử khác (liên thông ví - chưa triển khai)

# 3. Yêu cầu nghiệp vụ chi tiết

## 3.1 Hạn mức nạp tiền
Hạn mức nạp tiền phụ thuộc vào cấp độ tài khoản (xem chi tiết đầy đủ tại BusinessRules-002 - Hạn mức giao dịch):
- Tài khoản Tier 1 (chưa xác thực eKYC): tối đa 5.000.000 VNĐ/ngày
- Tài khoản Tier 2 (đã xác thực eKYC cơ bản): tối đa 20.000.000 VNĐ/ngày
- Tài khoản Tier 3 (đã xác thực eKYC nâng cao + định danh giấy tờ): tối đa 100.000.000 VNĐ/ngày

## 3.2 Điều kiện thực hiện
- Tài khoản phải ở trạng thái Active (không bị khóa/tạm ngưng)
- Phương thức nạp tiền phải được liên kết và xác thực trước đó (xem SOP-002)
- Giao dịch nạp tiền dưới 500.000 VNĐ không yêu cầu xác thực OTP bổ sung; từ 500.000 VNĐ trở lên bắt buộc xác thực OTP qua SMS hoặc Smart OTP

## 3.3 Phí giao dịch
- Nạp tiền qua liên kết ngân hàng: miễn phí
- Nạp tiền qua thẻ ATM nội địa: miễn phí
- Nạp tiền qua thẻ quốc tế: phí 1.5% giá trị giao dịch, tối thiểu 5.000 VNĐ (xem chi tiết đầy đủ tại bảng phí Fee-Pricing-Table)

## 3.4 Xử lý lỗi và ngoại lệ
- Nếu giao dịch trừ tiền thành công ở ngân hàng nhưng không cộng tiền vào ví (do lỗi timeout/network): hệ thống phải tự động đối soát (reconciliation) trong vòng 24 giờ, hoàn tiền hoặc cộng tiền cho khách hàng
- Nếu khách hàng nạp tiền vượt hạn mức: hệ thống từ chối giao dịch và hiển thị thông báo rõ ràng, gợi ý nâng cấp Tier tài khoản

# 4. Yêu cầu phi chức năng
- Thời gian xử lý giao dịch nạp tiền qua Napas 247: dưới 5 giây
- Tỷ lệ thành công giao dịch (success rate): tối thiểu 99.5%

# 5. Lịch sử thay đổi
| Phiên bản | Ngày | Nội dung thay đổi |
|---|---|---|
| 1.0 | 2025-06-01 | Khởi tạo tài liệu |
| 1.1 | 2025-11-15 | Cập nhật hạn mức Tier 3 từ 50 triệu lên 100 triệu |
| 1.2 | 2026-03-01 | Bổ sung yêu cầu OTP cho giao dịch từ 500.000 VNĐ |
