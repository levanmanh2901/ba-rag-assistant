---
doc_id: BRD-003
doc_type: BRD
module: Thanh_Toan_QR
title: "Business Requirement Document - Tính năng Thanh toán qua mã QR"
version: "1.0"
status: Approved
effective_date: 2025-08-01
last_updated: 2025-08-01
owner: Product Team
---

# 1. Mục tiêu nghiệp vụ

Cho phép khách hàng thanh toán tại điểm bán hàng (merchant) bằng cách quét mã QR động (VietQR) hoặc mã QR tĩnh của cửa hàng, hỗ trợ cả 2 chiều: khách quét QR merchant, hoặc merchant quét QR khách hàng.

# 2. Phạm vi

## Trong phạm vi
- Quét mã QR VietQR chuẩn của Napas tại merchant
- Hiển thị mã QR cá nhân để merchant quét thanh toán
- Thanh toán QR tại chuỗi cửa hàng đối tác (F&B, siêu thị mini, quán cà phê)

## Ngoài phạm vi
- Thanh toán QR quốc tế (Alipay+/QR xuyên biên giới) - roadmap Q4/2026

# 3. Yêu cầu nghiệp vụ chi tiết

## 3.1 Hạn mức thanh toán QR
Áp dụng chung theo hạn mức Tier tài khoản, riêng với QR có thêm giới hạn theo giao dịch đơn lẻ:
- Tier 1: tối đa 1.000.000 VNĐ/giao dịch
- Tier 2: tối đa 5.000.000 VNĐ/giao dịch
- Tier 3: tối đa 20.000.000 VNĐ/giao dịch

## 3.2 Phí giao dịch
- Khách hàng thanh toán QR: miễn phí
- Merchant nhận tiền qua QR: phí 0.8% - 1.2% tùy hạng merchant (xem Fee-Pricing-Table, sheet Merchant Fee)

## 3.3 Điều kiện kỹ thuật
- Mã QR động (dynamic QR) có thời hạn hiệu lực 5 phút kể từ khi merchant tạo mã
- Mã QR tĩnh (static QR) của merchant không giới hạn thời gian nhưng khách hàng phải tự nhập số tiền

## 3.4 Xử lý ngoại lệ
- QR hết hạn: hệ thống báo lỗi, yêu cầu merchant tạo lại mã mới
- Merchant chưa được xác thực (chưa hoàn tất KYC merchant): giao dịch bị chặn, hiển thị lỗi "Merchant chưa đủ điều kiện nhận thanh toán"

# 4. Lịch sử thay đổi
| Phiên bản | Ngày | Nội dung thay đổi |
|---|---|---|
| 1.0 | 2025-08-01 | Khởi tạo tài liệu, ra mắt tính năng |
