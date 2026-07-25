---
doc_id: SOP-003
doc_type: SOP
module: Khieu_Nai
title: "SOP - Quy trình xử lý khiếu nại giao dịch (Dispute Handling)"
version: "1.5"
status: Approved
effective_date: 2026-01-10
last_updated: 2026-01-10
owner: Customer Support & Risk Team
---

# 1. Mục đích
Chuẩn hóa quy trình tiếp nhận, điều tra và xử lý khiếu nại của khách hàng liên quan đến giao dịch trên ManhPay, đảm bảo thời gian phản hồi nhất quán và tuân thủ quy định bảo vệ người tiêu dùng tài chính.

# 2. Phân loại khiếu nại

| Loại khiếu nại | Mô tả | SLA xử lý |
|---|---|---|
| Giao dịch trùng lặp (Duplicate charge) | Khách hàng bị trừ tiền 2 lần cho 1 giao dịch | 3 ngày làm việc |
| Giao dịch không nhận diện (Unrecognized transaction) | Khách hàng không thực hiện nhưng bị trừ tiền, nghi ngờ gian lận | 7 ngày làm việc |
| Không nhận được tiền (Failed credit) | Trừ tiền người gửi nhưng người nhận không nhận được | 3 ngày làm việc |
| Tranh chấp merchant (Merchant dispute) | Khách hàng không hài lòng với hàng hóa/dịch vụ đã thanh toán qua ManhPay | 10 ngày làm việc |

# 3. Quy trình xử lý chi tiết

## Bước 1: Tiếp nhận
Khách hàng gửi khiếu nại qua app (Lịch sử giao dịch > Báo cáo vấn đề) hoặc qua Hotline. Hệ thống tự động tạo mã ticket (case ID) và gửi email/SMS xác nhận đã tiếp nhận trong vòng 15 phút.

## Bước 2: Phân loại và điều tra sơ bộ
Nhân viên Customer Support phân loại khiếu nại theo bảng ở mục 2, đối chiếu với dữ liệu giao dịch (transaction log), log hệ thống, và log đối soát (reconciliation log) nếu cần.

## Bước 3: Điều tra chuyên sâu (nếu cần)
Với các trường hợp nghi ngờ gian lận (Unrecognized transaction), case được chuyển sang đội Risk & Fraud để điều tra sâu, có thể bao gồm: kiểm tra thiết bị đăng nhập, lịch sử vị trí giao dịch (geolocation), và đối chiếu với các case tương tự trước đó.

## Bước 4: Ra quyết định và hoàn tiền
- Nếu xác định lỗi hệ thống hoặc gian lận không phải do khách hàng: hoàn tiền 100% trong vòng 24 giờ sau khi có kết luận
- Nếu xác định lỗi từ phía khách hàng (VD: tự cung cấp OTP cho người lạ): từ chối hoàn tiền, giải thích rõ lý do bằng văn bản

## Bước 5: Đóng case và khảo sát
Sau khi xử lý xong, hệ thống gửi khảo sát đánh giá mức độ hài lòng (CSAT) cho khách hàng.

# 4. Escalation (Chuyển cấp xử lý)
Nếu khách hàng không hài lòng với kết quả xử lý ở Bước 4, case được chuyển lên cấp Team Lead trong vòng 2 ngày làm việc để review lại. Trường hợp giá trị tranh chấp trên 50.000.000 VNĐ, bắt buộc có sự phê duyệt của Compliance Manager trước khi ra quyết định cuối cùng.

# 5. Lịch sử thay đổi
| Phiên bản | Ngày | Nội dung thay đổi |
|---|---|---|
| 1.0 | 2025-03-01 | Khởi tạo |
| 1.5 | 2026-01-10 | Bổ sung quy trình escalation cho case giá trị lớn (>50 triệu) |
