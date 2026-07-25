---
doc_id: GL-001
doc_type: Glossary
module: General
title: "Bảng thuật ngữ nghiệp vụ - ManhPay Data Dictionary"
version: "1.4"
status: Approved
last_updated: 2026-04-01
owner: Product & Data Team
---

# Bảng thuật ngữ nghiệp vụ

| Thuật ngữ | Định nghĩa |
|---|---|
| Số dư khả dụng (Available Balance) | Số tiền khách hàng có thể sử dụng ngay để giao dịch, đã trừ đi các khoản đang bị treo (hold) |
| Số dư treo (Pending Balance / Hold) | Số tiền tạm thời bị giữ do giao dịch đang xử lý hoặc đang tranh chấp (dispute), chưa cộng/trừ chính thức |
| Tier | Cấp độ tài khoản dựa trên mức độ xác thực danh tính (eKYC), quyết định hạn mức giao dịch |
| eKYC (electronic Know Your Customer) | Quy trình xác thực danh tính khách hàng điện tử, thường qua chụp giấy tờ tùy thân + nhận diện khuôn mặt |
| Reconciliation (Đối soát) | Quy trình so khớp dữ liệu giao dịch giữa hệ thống ManhPay và đối tác (ngân hàng, Napas) để phát hiện chênh lệch |
| Settlement (Thanh toán bù trừ) | Quy trình chuyển tiền thực tế giữa ManhPay và đối tác/merchant sau khi các giao dịch đã được đối soát |
| Dispute (Tranh chấp/Khiếu nại) | Trường hợp khách hàng không đồng ý với một giao dịch đã thực hiện, yêu cầu điều tra và có thể hoàn tiền |
| Float Balance | Tổng số tiền khách hàng đang gửi trong ví ManhPay nhưng chưa sử dụng, ManhPay có trách nhiệm đảm bảo an toàn 100% số tiền này theo quy định NHNN |
| Idempotency Key | Mã định danh duy nhất gắn với một yêu cầu giao dịch, dùng để đảm bảo hệ thống không xử lý trùng lặp một giao dịch khi có lỗi retry |
| AML (Anti-Money Laundering) | Chính sách và quy trình phòng chống rửa tiền, yêu cầu bắt buộc với mọi tổ chức trung gian thanh toán |
| Merchant | Đối tác cửa hàng/doanh nghiệp chấp nhận thanh toán qua ManhPay |
| VietQR | Chuẩn mã QR thanh toán thống nhất do Napas và NHNN quy định, áp dụng chung cho các ngân hàng và ví điện tử tại Việt Nam |
| Napas 247 | Hệ thống chuyển mạch tài chính quốc gia, cho phép chuyển tiền nhanh liên ngân hàng 24/7 |
| MAU (Monthly Active Users) | Số người dùng thực hiện ít nhất 1 hành động trong app trong vòng 1 tháng, chỉ số đo mức độ sử dụng sản phẩm |
| Success Rate | Tỷ lệ giao dịch xử lý thành công trên tổng số giao dịch được khởi tạo |
| Chargeback | Trường hợp ngân hàng phát hành thẻ quốc tế yêu cầu hoàn tiền cho chủ thẻ do giao dịch bị tranh chấp/gian lận |
