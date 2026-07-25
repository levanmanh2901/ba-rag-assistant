---
doc_id: US-EPIC-021
doc_type: UserStory
module: Nap_Tien
title: "Epic: Tối ưu tỷ lệ thành công luồng Nạp tiền"
version: "1.0"
status: In Progress
sprint: Sprint 46-49
last_updated: 2026-05-05
owner: PO - Tran Thi B
---

# Epic: MANHPAY-EPIC-021 - Tối ưu tỷ lệ thành công luồng Nạp tiền

**Bối cảnh:** Sau sự cố INC-001 (tháng 02/2026), tỷ lệ thành công giao dịch nạp tiền qua thẻ quốc tế giảm từ 97.2% xuống 94.8% do khách hàng mất niềm tin và bỏ dở giữa chừng.

**Mục tiêu Epic:** Nâng tỷ lệ thành công nạp tiền tổng thể lên trên 99%, giảm tỷ lệ bỏ dở (drop-off) ở bước xác thực OTP xuống dưới 5%.

## User Story 1: MANHPAY-1402
**Là** một khách hàng đang nạp tiền vào ví
**Tôi muốn** thấy rõ trạng thái giao dịch theo thời gian thực (đang xử lý / thành công / thất bại)
**Để** tôi không phải lo lắng và thoát app giữa chừng khi giao dịch chậm

**Acceptance Criteria:**
- Given khách hàng đã xác nhận giao dịch nạp tiền
- When hệ thống đang chờ phản hồi từ ngân hàng/cổng thanh toán
- Then hiển thị màn hình trạng thái với thanh tiến trình và thông báo "Đang xử lý, vui lòng không tắt ứng dụng"
- Nếu quá 30 giây chưa có kết quả, hiển thị thông báo "Giao dịch đang được xử lý, kết quả sẽ được thông báo qua notification"

**Story Points:** 5 | **Priority:** High | **Status:** Done (release 2026-04-10)

---

## User Story 2: MANHPAY-1418
**Là** một khách hàng nạp tiền lần đầu bằng thẻ quốc tế
**Tôi muốn** biết trước mức phí sẽ bị trừ trước khi xác nhận
**Để** tôi không bị bất ngờ khi thấy số tiền thực nhận ít hơn số tiền nạp

**Acceptance Criteria:**
- Given khách hàng chọn phương thức nạp tiền là thẻ quốc tế
- When khách hàng nhập số tiền muốn nạp
- Then hiển thị ngay bảng chi tiết: số tiền nạp, phí (1.5%, tối thiểu 5.000 VNĐ), tổng số tiền bị trừ từ thẻ
- Thông tin phí phải đồng bộ với bảng phí FEE-001, không hardcode trong app

**Story Points:** 3 | **Priority:** High | **Status:** In Progress (dự kiến Sprint 47)

---

## User Story 3: MANHPAY-1425
**Là** một khách hàng có giao dịch nạp tiền bị treo
**Tôi muốn** tự tra cứu được trạng thái đối soát của giao dịch đó
**Để** tôi biết khi nào tiền sẽ về mà không cần gọi tổng đài

**Acceptance Criteria:**
- Given giao dịch nạp tiền ở trạng thái "Đang đối soát"
- When khách hàng mở chi tiết giao dịch trong lịch sử
- Then hiển thị trạng thái đối soát, thời gian dự kiến hoàn tất (theo SLA 24 giờ trong BRD-001), và nút liên hệ hỗ trợ

**Story Points:** 8 | **Priority:** Medium | **Status:** Backlog

**Rủi ro đã ghi nhận:** Cần đội Backend expose thêm API trạng thái đối soát — hiện dữ liệu này chỉ có trong hệ thống nội bộ, chưa có endpoint cho app.
