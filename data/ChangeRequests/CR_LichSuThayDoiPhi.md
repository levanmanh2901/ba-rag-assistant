---
doc_id: CR-LOG-001
doc_type: ChangeRequest
module: General
title: "Nhật ký yêu cầu thay đổi - Chính sách phí và hạn mức"
version: "1.0"
status: Approved
last_updated: 2026-04-15
owner: Product & Finance Team
---

# Nhật ký yêu cầu thay đổi (Change Request Log)

Tài liệu này ghi nhận các yêu cầu thay đổi đã được phê duyệt liên quan đến chính sách phí và hạn mức, giúp BA/PO truy vết lý do phía sau mỗi con số hiện tại.

## CR-2025-018: Nâng hạn mức Tier 3
- **Ngày đề xuất:** 20/05/2025 | **Ngày hiệu lực:** 15/06/2025
- **Người đề xuất:** Product Team
- **Nội dung:** Nâng hạn mức giao dịch/ngày của Tier 3 từ 50.000.000 lên 100.000.000 VNĐ
- **Lý do:** Khảo sát cho thấy 12% khách hàng Tier 3 chạm trần hạn mức ít nhất 1 lần/tháng, dẫn tới việc họ chuyển sang dùng ví đối thủ cho các giao dịch lớn
- **Tài liệu bị ảnh hưởng:** BR-002 (từ v1.0 lên v2.0), BRD-001, BRD-002
- **Trạng thái:** Đã triển khai

## CR-2025-034: Áp dụng phí rút tiền từ lần thứ 6
- **Ngày đề xuất:** 10/09/2025 | **Ngày hiệu lực:** 01/11/2025
- **Người đề xuất:** Finance Team
- **Nội dung:** Miễn phí 5 lần rút tiền/ngày, từ lần thứ 6 thu phí 0.3%
- **Lý do:** Phát hiện nhóm nhỏ người dùng (dưới 0.5%) thực hiện hàng chục lần rút tiền giá trị nhỏ mỗi ngày, gây chi phí xử lý qua Napas vượt doanh thu
- **Tài liệu bị ảnh hưởng:** FEE-001, BRD-004
- **Trạng thái:** Đã triển khai

## CR-2026-005: Bổ sung OTP cho giao dịch nạp tiền từ 500.000 VNĐ
- **Ngày đề xuất:** 15/01/2026 | **Ngày hiệu lực:** 01/03/2026
- **Người đề xuất:** Risk & Compliance Team
- **Nội dung:** Yêu cầu xác thực OTP bắt buộc với giao dịch nạp tiền từ 500.000 VNĐ trở lên
- **Lý do:** Sau sự cố gian lận thẻ quốc tế quý 4/2025, cần siết chặt xác thực để giảm tỷ lệ chargeback
- **Tài liệu bị ảnh hưởng:** BRD-001 (từ v1.1 lên v1.2)
- **Trạng thái:** Đã triển khai

## CR-2026-011: Giảm phí merchant hạng Kim Cương
- **Ngày đề xuất:** 01/03/2026 | **Ngày hiệu lực:** 01/04/2026
- **Người đề xuất:** Business Development Team
- **Nội dung:** Giảm phí QR merchant hạng Kim Cương từ 0.8% xuống 0.6%
- **Lý do:** Giữ chân 3 chuỗi bán lẻ lớn đang đàm phán chuyển sang đối thủ
- **Tài liệu bị ảnh hưởng:** FEE-001 (từ v2.3 lên v2.4), BRD-003
- **Trạng thái:** Đã triển khai

## CR-2026-019: Yêu cầu Tier 2 mới được rút tiền
- **Ngày đề xuất:** 25/02/2026 | **Ngày hiệu lực:** 20/03/2026
- **Người đề xuất:** Risk & Compliance Team
- **Nội dung:** Chỉ tài khoản từ Tier 2 trở lên mới được sử dụng chức năng rút tiền về ngân hàng
- **Lý do:** Tài khoản Tier 1 chưa xác thực danh tính, rủi ro cao bị lợi dụng làm trung gian rửa tiền
- **Tài liệu bị ảnh hưởng:** BRD-004 (từ v1.0 lên v1.1), BR-004
- **Trạng thái:** Đã triển khai
