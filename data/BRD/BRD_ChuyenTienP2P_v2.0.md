---
doc_id: BRD-002
doc_type: BRD
module: Chuyen_Tien_P2P
title: "Business Requirement Document - Tính năng Chuyển tiền P2P (Peer-to-Peer)"
version: "2.0"
status: Approved
effective_date: 2026-01-15
last_updated: 2026-01-15
owner: Product Team
---

# 1. Mục tiêu nghiệp vụ

Cho phép người dùng ManhPay chuyển tiền tức thời cho người dùng ManhPay khác thông qua số điện thoại, mã QR cá nhân, hoặc username ManhPay, nhằm thay thế nhu cầu chuyển khoản ngân hàng truyền thống trong các giao dịch giá trị nhỏ giữa cá nhân.

# 2. Phạm vi

## Trong phạm vi
- Chuyển tiền qua số điện thoại đã đăng ký ManhPay
- Chuyển tiền qua quét mã QR cá nhân
- Chuyển tiền theo danh bạ đã lưu (Người nhận yêu thích)
- Tính năng "Lời nhắn" đính kèm giao dịch

## Ngoài phạm vi
- Chuyển tiền ra ngân hàng khác (thuộc BRD-004 Chuyển tiền liên ngân hàng)
- Chia hóa đơn nhóm (Split Bill) - đang trong giai đoạn Discovery, chưa có BRD chính thức

# 3. Yêu cầu nghiệp vụ chi tiết

## 3.1 Hạn mức chuyển tiền P2P
Áp dụng chung theo hạn mức Tier tài khoản (BusinessRules-002):
- Tier 1: tối đa 2.000.000 VNĐ/giao dịch, 5.000.000 VNĐ/ngày
- Tier 2: tối đa 10.000.000 VNĐ/giao dịch, 20.000.000 VNĐ/ngày
- Tier 3: tối đa 50.000.000 VNĐ/giao dịch, 100.000.000 VNĐ/ngày

## 3.2 Điều kiện thực hiện
- Cả người gửi và người nhận đều phải có tài khoản ManhPay ở trạng thái Active
- Số dư khả dụng (Available Balance) của người gửi phải lớn hơn hoặc bằng số tiền chuyển cộng phí (nếu có)
- Nếu người nhận chưa từng nhận tiền từ người gửi, giao dịch đầu tiên trên 1.000.000 VNĐ yêu cầu xác thực OTP bắt buộc (chính sách chống gian lận)

## 3.3 Phí giao dịch
- Chuyển tiền P2P trong hệ sinh thái ManhPay: **miễn phí hoàn toàn**, không giới hạn số lần
- Đây là chính sách khác biệt cạnh tranh chính của sản phẩm (competitive positioning), Product team cần lưu ý khi trả lời câu hỏi liên quan đến pricing

## 3.4 Luồng xử lý chính (Happy path)
1. Người dùng A chọn "Chuyển tiền" → nhập số điện thoại hoặc quét QR của người dùng B
2. Hệ thống kiểm tra người dùng B tồn tại và active
3. Người dùng A nhập số tiền, có thể đính kèm lời nhắn
4. Hệ thống kiểm tra số dư khả dụng và hạn mức
5. Nếu cần OTP: gửi OTP, người dùng A xác nhận
6. Hệ thống trừ tiền người A, cộng tiền người B, ghi nhận giao dịch (transaction log)
7. Cả hai bên nhận thông báo đẩy (push notification) xác nhận giao dịch thành công

## 3.5 Xử lý ngoại lệ
- Người nhận không tồn tại: hiển thị lỗi "Số điện thoại chưa đăng ký ManhPay", gợi ý mời bạn bè (referral flow)
- Giao dịch bị timeout giữa bước trừ tiền và cộng tiền: hệ thống dùng cơ chế idempotency key để đảm bảo không trừ tiền 2 lần, và tự động retry cộng tiền cho người nhận

# 4. Chỉ số đo lường thành công (Success Metrics)
- Tỷ lệ giao dịch P2P thành công: > 99.7%
- Thời gian xử lý trung bình: < 3 giây
- Tỷ lệ người dùng thực hiện P2P ít nhất 1 lần/tháng (P2P MAU ratio): mục tiêu 40%

# 5. Lịch sử thay đổi
| Phiên bản | Ngày | Nội dung thay đổi |
|---|---|---|
| 1.0 | 2025-04-10 | Khởi tạo |
| 1.5 | 2025-09-20 | Bổ sung tính năng Lời nhắn |
| 2.0 | 2026-01-15 | Bổ sung yêu cầu OTP cho giao dịch đầu tiên với người nhận mới trên 1 triệu VNĐ |
