---
doc_id: INC-001
doc_type: IncidentReport
module: Nap_Tien
title: "Báo cáo sự cố - Lỗi đối soát giao dịch nạp tiền qua thẻ quốc tế"
version: "1.0"
status: Closed
incident_date: 2026-02-08
resolved_date: 2026-02-10
severity: P1
last_updated: 2026-02-12
owner: Engineering & Operations Team
---

# 1. Tóm tắt sự cố

Ngày 08/02/2026, trong khoảng 09:15 - 13:40 (giờ Việt Nam), khoảng 1.240 giao dịch nạp tiền qua thẻ quốc tế bị trừ tiền ở phía ngân hàng phát hành thẻ nhưng không được cộng vào số dư ví ManhPay. Tổng giá trị bị ảnh hưởng ước tính 890.000.000 VNĐ.

# 2. Mức độ ảnh hưởng
- Số khách hàng bị ảnh hưởng: 1.187 tài khoản
- Số lượng khiếu nại phát sinh: 412 ticket trong vòng 24 giờ (tăng gấp 6 lần so với ngày thường)
- Ảnh hưởng danh tiếng: xuất hiện phản ánh trên mạng xã hội, đội Marketing phải phát thông cáo xin lỗi

# 3. Nguyên nhân gốc rễ (Root Cause)

Đối tác cổng thanh toán thẻ quốc tế thay đổi định dạng trường `transaction_reference` trong callback trả về (từ 20 ký tự lên 24 ký tự) mà không thông báo trước. Hệ thống ManhPay validate độ dài trường này và từ chối các callback không hợp lệ, dẫn đến giao dịch được ghi nhận thành công ở phía đối tác nhưng thất bại ở phía ManhPay.

Nguyên nhân sâu xa: hệ thống không có cơ chế cảnh báo khi tỷ lệ callback bị từ chối tăng đột biến, nên sự cố kéo dài hơn 4 giờ trước khi được phát hiện thủ công qua báo cáo của Customer Support.

# 4. Diễn biến xử lý (Timeline)

| Thời gian | Sự kiện |
|---|---|
| 09:15 | Sự cố bắt đầu, callback đầu tiên bị từ chối |
| 11:30 | Customer Support ghi nhận lượng khiếu nại tăng bất thường, báo lên đội Engineering |
| 12:10 | Đội Engineering xác định nguyên nhân từ log hệ thống |
| 13:40 | Triển khai hotfix nới lỏng validate độ dài trường, sự cố dừng phát sinh mới |
| 09/02 14:00 | Hoàn tất đối soát thủ công với đối tác, xác định chính xác danh sách giao dịch bị ảnh hưởng |
| 10/02 16:30 | Hoàn tất cộng tiền bù cho toàn bộ 1.187 khách hàng bị ảnh hưởng |

# 5. Biện pháp khắc phục đã thực hiện
- Hotfix nới lỏng validate độ dài trường transaction_reference (đã triển khai 08/02)
- Cộng tiền bù thủ công cho toàn bộ khách hàng bị ảnh hưởng (hoàn tất 10/02)
- Gửi thông báo xin lỗi và tặng mã khuyến mãi cho khách hàng bị ảnh hưởng

# 6. Biện pháp phòng ngừa (Preventive Actions)
- Bổ sung cảnh báo tự động khi tỷ lệ callback thất bại vượt 2% trong 15 phút (hoàn thành 20/02)
- Thiết lập kênh thông báo thay đổi kỹ thuật với đối tác cổng thanh toán, yêu cầu báo trước tối thiểu 30 ngày
- Rà soát toàn bộ logic validate dữ liệu đầu vào từ đối tác, ưu tiên chấp nhận linh hoạt thay vì từ chối cứng

# 7. Bài học rút ra
Việc phụ thuộc vào định dạng dữ liệu của đối tác bên ngoài mà không có cơ chế giám sát tự động là rủi ro vận hành nghiêm trọng. Quy trình đối soát tự động trong 24 giờ (theo BRD-001 mục 3.4) đã hoạt động đúng thiết kế nhưng không đủ nhanh với sự cố quy mô lớn — cần bổ sung cảnh báo thời gian thực.
