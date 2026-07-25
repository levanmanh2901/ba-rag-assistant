---
doc_id: BR-004
doc_type: BusinessRules
module: Phong_Chong_Gian_Lan
title: "Quy tắc nghiệp vụ - Phòng chống gian lận và rửa tiền (AML/Fraud Rules)"
version: "2.0"
status: Approved
effective_date: 2026-01-05
last_updated: 2026-01-05
owner: Risk & Compliance Team
---

# 1. Mục đích
Quy định các quy tắc tự động phát hiện và xử lý giao dịch có dấu hiệu bất thường, tuân thủ quy định phòng chống rửa tiền (AML) của Ngân hàng Nhà nước.

# 2. Các quy tắc cảnh báo tự động

| Mã rule | Điều kiện kích hoạt | Hành động hệ thống | Mức độ |
|---|---|---|---|
| FR-001 | Trên 10 giao dịch P2P trong 5 phút từ cùng một tài khoản | Tạm dừng giao dịch, yêu cầu xác thực lại OTP | Trung bình |
| FR-002 | Nhận tiền từ trên 20 tài khoản khác nhau trong 24 giờ | Gắn cờ theo dõi, chuyển đội Risk review | Cao |
| FR-003 | Đăng nhập từ thiết bị mới + rút tiền toàn bộ số dư trong 30 phút | Chặn giao dịch rút tiền, gọi xác minh khách hàng | Rất cao |
| FR-004 | Tổng giao dịch trong ngày vượt 400.000.000 VNĐ | Báo cáo giao dịch giá trị lớn theo quy định NHNN | Cao |
| FR-005 | Tài khoản mới tạo dưới 24 giờ thực hiện giao dịch trên 20.000.000 VNĐ | Tạm giữ giao dịch 2 giờ để review thủ công | Cao |
| FR-006 | Địa chỉ IP giao dịch thay đổi trên 3 quốc gia trong 24 giờ | Khóa tạm thời tài khoản, yêu cầu xác thực lại eKYC | Rất cao |

# 3. Quy tắc khóa tài khoản

## 3.1 Khóa tạm thời (Temporary Suspension)
Áp dụng khi kích hoạt rule mức Cao trở lên. Tài khoản bị hạn chế các chức năng giao dịch (chuyển tiền, rút tiền, thanh toán) nhưng vẫn xem được số dư và lịch sử. Thời hạn tối đa 72 giờ để đội Risk hoàn tất điều tra.

## 3.2 Khóa vĩnh viễn (Permanent Closure)
Áp dụng khi xác định chắc chắn có hành vi gian lận, giả mạo giấy tờ, hoặc theo yêu cầu của cơ quan chức năng. Số dư còn lại được xử lý theo quy trình hoàn trả riêng, có sự phê duyệt của Compliance Manager.

## 3.3 Hạ Tier tự động
Tài khoản bị phát hiện dùng giấy tờ giả mạo trong quá trình eKYC sẽ tự động bị hạ về Tier 1 và chặn chức năng nâng Tier, đồng thời chuyển hồ sơ sang đội Compliance điều tra (liên quan SOP-002).

# 4. Ngưỡng báo cáo bắt buộc
Theo quy định phòng chống rửa tiền hiện hành, các giao dịch có giá trị lớn hoặc giao dịch đáng ngờ phải được báo cáo cho cơ quan quản lý nhà nước có thẩm quyền. Đội Compliance chịu trách nhiệm rà soát và lập báo cáo định kỳ. Lưu ý: ngưỡng giá trị cụ thể cần đối chiếu văn bản pháp luật hiện hành tại thời điểm áp dụng, không sử dụng con số trong tài liệu nội bộ làm căn cứ pháp lý.

# 5. Lịch sử thay đổi
| Phiên bản | Ngày | Nội dung thay đổi |
|---|---|---|
| 1.0 | 2025-02-01 | Khởi tạo bộ rule FR-001 đến FR-004 |
| 2.0 | 2026-01-05 | Bổ sung FR-005, FR-006; làm rõ quy trình khóa tài khoản |
