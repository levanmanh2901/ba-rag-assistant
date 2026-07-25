---
doc_id: US-EPIC-014
doc_type: UserStory
module: Thanh_Toan_QR
title: "Epic: Nâng cấp trải nghiệm Thanh toán QR"
version: "1.0"
status: In Progress
sprint: Sprint 42-45
last_updated: 2026-04-10
owner: PO - Nguyen Van A
---

# Epic: MANHPAY-EPIC-014 - Nâng cấp trải nghiệm Thanh toán QR

**Mục tiêu Epic:** Giảm thời gian thanh toán QR trung bình từ 8 giây xuống dưới 4 giây, tăng tỷ lệ chuyển đổi (conversion rate) tại bước quét mã.

## User Story 1: MANHPAY-1201
**Là** một khách hàng đang xếp hàng thanh toán tại cửa hàng tiện lợi
**Tôi muốn** mở nhanh màn hình quét QR chỉ bằng 1 thao tác từ màn hình khóa (lock screen widget)
**Để** tôi không mất thời gian mở app, đăng nhập, tìm tính năng

**Acceptance Criteria:**
- Given khách hàng đã bật widget ManhPay trên màn hình khóa
- When khách hàng nhấn vào widget
- Then app mở thẳng vào màn hình camera quét QR, không qua màn hình chủ
- Yêu cầu xác thực sinh trắc học (vân tay/FaceID) trước khi mở camera nếu số dư > 0

**Story Points:** 5
**Priority:** High
**Status:** Done (release 2026-03-15)

---

## User Story 2: MANHPAY-1215
**Là** một khách hàng thanh toán tại quán cà phê đông khách
**Tôi muốn** thấy xác nhận thanh toán thành công ngay lập tức kèm âm thanh
**Để** cả tôi và nhân viên thu ngân đều biết giao dịch đã hoàn tất, tránh nhầm lẫn thanh toán 2 lần

**Acceptance Criteria:**
- Given giao dịch QR đã xử lý thành công ở backend
- When kết quả trả về app
- Then hiển thị màn hình xác nhận trong vòng 1 giây kèm âm thanh "ting" đặc trưng
- Màn hình xác nhận hiển thị: số tiền, tên merchant, thời gian, mã giao dịch

**Story Points:** 3
**Priority:** High
**Status:** In Progress (dự kiến release Sprint 44)

**Ghi chú từ PO:** Đây là tính năng học hỏi từ phản hồi khách hàng qua khảo sát NPS Q1/2026 - khách hàng phàn nàn không chắc giao dịch đã thành công hay chưa khi ở nơi ồn ào.

---

## User Story 3: MANHPAY-1230
**Là** một merchant nhỏ (quán ăn, tạp hóa)
**Tôi muốn** nhận thông báo biến động số dư ngay khi có khách thanh toán QR
**Để** tôi yên tâm giao hàng/phục vụ mà không cần hỏi khách "chuyển chưa"

**Acceptance Criteria:**
- Given merchant đã cài app ManhPay Merchant
- When có giao dịch QR thành công vào tài khoản merchant
- Then merchant nhận push notification trong vòng 2 giây kèm âm thanh riêng biệt cho merchant

**Story Points:** 8
**Priority:** Medium
**Status:** Backlog (chưa lên sprint, phụ thuộc vào việc hoàn thiện app Merchant riêng)

**Rủi ro đã ghi nhận:** Cần phối hợp với đội Infra vì notification service hiện tại chưa tách riêng luồng cho merchant, có thể ảnh hưởng đến độ trễ chung.
