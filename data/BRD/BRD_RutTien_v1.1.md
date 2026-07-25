---
doc_id: BRD-004
doc_type: BRD
module: Rut_Tien
title: "Business Requirement Document - Tính năng Rút tiền từ ví về tài khoản ngân hàng"
version: "1.1"
status: Approved
effective_date: 2026-03-20
last_updated: 2026-03-20
owner: Product Team
---

# 1. Mục tiêu nghiệp vụ

Cho phép khách hàng rút tiền từ số dư ví ManhPay về tài khoản ngân hàng đã liên kết, đảm bảo khách hàng luôn có toàn quyền kiểm soát tiền của mình trong ví — đây là yêu cầu bắt buộc theo quy định của Ngân hàng Nhà nước đối với tổ chức cung ứng dịch vụ trung gian thanh toán.

# 2. Phạm vi

## Trong phạm vi
- Rút tiền về tài khoản ngân hàng đã liên kết và xác thực
- Rút tiền về thẻ ATM nội địa đã liên kết
- Hiển thị lịch sử rút tiền và trạng thái xử lý từng giao dịch

## Ngoài phạm vi
- Rút tiền mặt tại điểm giao dịch đối tác (chưa triển khai)
- Rút tiền về tài khoản ngân hàng của người khác (không cho phép, theo quy định phòng chống rửa tiền)

# 3. Yêu cầu nghiệp vụ chi tiết

## 3.1 Hạn mức rút tiền
Áp dụng theo hạn mức Tier tài khoản (nguồn tham chiếu: BR-002):
- Tier 1: tối đa 2.000.000 VNĐ/giao dịch, 5.000.000 VNĐ/ngày
- Tier 2: tối đa 10.000.000 VNĐ/giao dịch, 20.000.000 VNĐ/ngày
- Tier 3: tối đa 50.000.000 VNĐ/giao dịch, 100.000.000 VNĐ/ngày

## 3.2 Điều kiện thực hiện
- Tài khoản ngân hàng đích phải trùng khớp thông tin chủ tài khoản với thông tin eKYC của khách hàng (kiểm tra tự động theo họ tên và số CCCD)
- Tài khoản khách hàng phải đạt tối thiểu Tier 2 (đã hoàn tất eKYC cơ bản) mới được sử dụng tính năng rút tiền
- Bắt buộc xác thực OTP hoặc sinh trắc học cho mọi giao dịch rút tiền, không phân biệt giá trị
- Số dư khả dụng phải lớn hơn hoặc bằng số tiền rút cộng phí (nếu có)

## 3.3 Phí giao dịch
- Miễn phí tối đa 5 lần rút tiền mỗi ngày
- Từ lần rút thứ 6 trở đi trong cùng ngày: phí 0.3% giá trị giao dịch (xem chi tiết tại FEE-001)

## 3.4 Thời gian xử lý
- Rút tiền qua Napas 247 trong giờ hành chính: dưới 5 phút
- Rút tiền ngoài giờ hoặc ngày lễ: có thể mất tới 24 giờ do phụ thuộc hệ thống ngân hàng đối tác

## 3.5 Xử lý ngoại lệ
- Tài khoản ngân hàng không khớp tên chủ tài khoản: từ chối giao dịch, hiển thị hướng dẫn liên kết đúng tài khoản chính chủ
- Giao dịch bị treo quá 24 giờ: tự động chuyển sang quy trình đối soát (xem SOP-005), khách hàng được hoàn tiền vào ví nếu ngân hàng báo giao dịch thất bại
- Tài khoản đang trong diện điều tra gian lận (AML flag): tạm khóa chức năng rút tiền, thông báo khách hàng liên hệ hỗ trợ

# 4. Chỉ số đo lường thành công
- Tỷ lệ rút tiền thành công: > 99.5%
- Thời gian xử lý trung bình trong giờ hành chính: < 3 phút
- Tỷ lệ khiếu nại liên quan rút tiền: < 0.1% tổng giao dịch rút

# 5. Lịch sử thay đổi
| Phiên bản | Ngày | Nội dung thay đổi |
|---|---|---|
| 1.0 | 2025-07-01 | Khởi tạo tài liệu |
| 1.1 | 2026-03-20 | Bổ sung điều kiện bắt buộc Tier 2 trở lên mới được rút tiền |
