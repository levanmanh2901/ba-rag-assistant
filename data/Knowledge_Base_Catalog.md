# Knowledge Base Catalog — RAG Assistant cho BA/PO (ManhPay)

> Mô tả chi tiết toàn bộ Knowledge Base nạp vào hệ thống RAG, tổ chức theo từng **loại tài liệu (doc_type)**.

**Tổng quan bộ dữ liệu**

| Chỉ số | Giá trị |
|---|---|
| Tổng số tài liệu | **20** |
| Số loại tài liệu (doc_type) | 11 |
| Số module nghiệp vụ | 12 |
| Định dạng | 16 file `.md`, 2 file `.docx`, 2 file `.xlsx` |
| Trạng thái | 16 Approved, 1 Deprecated, 2 In Progress, 1 Closed |
| Bộ câu hỏi đánh giá | 32 câu (5 nhóm) |

---

## 1. BRD (Business Requirement Document) — 4 tài liệu

Mô tả **yêu cầu nghiệp vụ** cho từng tính năng: mục tiêu, phạm vi, luồng xử lý, điều kiện, phí, xử lý ngoại lệ.

| doc_id | Tên | Module | Version | Nội dung chính |
|---|---|---|---|---|
| BRD-001 | Nạp tiền vào ví | Nap_Tien | 1.2 | 4 phương thức nạp, OTP từ 500k, xử lý lỗi đối soát 24h |
| BRD-002 | Chuyển tiền P2P | Chuyen_Tien_P2P | 2.0 | Miễn phí hoàn toàn, OTP cho người nhận mới >1 triệu, idempotency key |
| BRD-003 | Thanh toán QR | Thanh_Toan_QR | 1.0 | QR động 5 phút vs QR tĩnh, điều kiện KYC merchant |
| BRD-004 | **Rút tiền về ngân hàng** *(mới)* | Rut_Tien | 1.1 | Bắt buộc Tier 2+, OTP mọi giao dịch, miễn phí 5 lần/ngày |

**Câu hỏi mẫu:** "Tài khoản Tier 1 có rút tiền được không?" → BRD-004 (không, cần Tier 2 trở lên)

---

## 2. SOP (Standard Operating Procedure) — 3 tài liệu

Mô tả **quy trình vận hành từng bước**: ai làm, làm gì, trong bao lâu (SLA).

| doc_id | Tên | Định dạng | Version | Nội dung chính |
|---|---|---|---|---|
| SOP-002 | Xác thực eKYC | **.docx** | 2.1 | Face matching 85%, quy trình Tier 1→2 và 2→3, trường hợp từ chối |
| SOP-003 | Xử lý khiếu nại | .md | 1.5 | 4 loại khiếu nại kèm SLA riêng, escalation khi >50 triệu |
| SOP-005 | **Đối soát & Settlement** *(mới)* | **.docx** | 2.0 | Đối soát tự động 02:00, 4 loại chênh lệch, nguyên tắc ưu tiên khách hàng |

**Lưu ý kỹ thuật:** 2 file `.docx` bắt buộc phải parse bằng `python-docx`/`pandoc` trước khi chunk — đây là điểm khác biệt so với các đồ án RAG chỉ dùng `.txt`/`.md`.

---

## 3. BusinessRules — 3 tài liệu (gồm 1 bản Deprecated)

Loại tài liệu **quan trọng nhất về kiến trúc dữ liệu**: đóng vai trò "single source of truth" cho các con số nghiệp vụ.

| doc_id | Tên | Status | Version | Vai trò |
|---|---|---|---|---|
| BR-002 | Hạn mức giao dịch theo Tier | **Approved** | 3.0 | Nguồn gốc duy nhất cho mọi hạn mức (Tier 3 = 100 triệu/ngày) |
| BR-002-v1 | **Hạn mức — BẢN CŨ** *(mới)* | **Deprecated** | 1.0 | Tier 3 = 50 triệu/ngày — dùng để **test metadata filter theo status** |
| BR-004 | **Phòng chống gian lận (AML)** *(mới)* | Approved | 2.0 | 6 rule FR-001→FR-006, quy tắc khóa tài khoản, hạ Tier tự động |

**Đây là cặp tài liệu quan trọng nhất của bộ dữ liệu:** BR-002 và BR-002-v1 chứa **số liệu mâu thuẫn có chủ đích**. Hệ thống RAG phải lọc `status = Approved` để trả lời đúng 100 triệu, không phải 50 triệu — nếu không có metadata filter, chatbot sẽ trả lời sai hoặc mâu thuẫn.

---

## 4. UserStory — 2 tài liệu

Yêu cầu ở cấp sprint theo chuẩn Agile/Jira, có Acceptance Criteria dạng Given-When-Then.

| doc_id | Epic | Module | Status | Nội dung chính |
|---|---|---|---|---|
| US-EPIC-014 | Nâng cấp trải nghiệm QR | Thanh_Toan_QR | In Progress | 3 story: lock-screen widget (Done), âm thanh xác nhận (In Progress), thông báo merchant (Backlog) |
| US-EPIC-021 | **Tối ưu tỷ lệ thành công Nạp tiền** *(mới)* | Nap_Tien | In Progress | 3 story sinh ra sau sự cố INC-001, có liên kết ngược tới Incident Report |

---

## 5. FAQ — 2 tài liệu

Văn phong đơn giản hướng người dùng cuối, dùng để test khả năng RAG trả lời nhất quán dù văn phong nguồn khác BRD/SOP.

| doc_id | Đối tượng | Version | Nội dung |
|---|---|---|---|
| FAQ-001 | Khách hàng cá nhân | 2.3 | 8 câu về hạn mức, phí, lỗi giao dịch, khiếu nại, khóa tài khoản |
| FAQ-002 | **Merchant** *(mới)* | 1.2 | 7 câu về đăng ký, phí theo hạng, chu kỳ nhận tiền T+1, hoàn tiền |

---

## 6. Glossary — 1 tài liệu

| doc_id | Nội dung |
|---|---|
| GL-001 | 16 thuật ngữ: Số dư khả dụng/treo, Tier, eKYC, Reconciliation, Settlement, Dispute, Float Balance, Idempotency Key, AML, VietQR, Napas 247, MAU, Chargeback... |

---

## 7. Dữ liệu dạng bảng (Excel) — 2 tài liệu

Nhóm tài liệu **thử thách kỹ thuật nhất**: chứa bảng số liệu và công thức, không phải văn bản thuần.

### FEE-001 — Bảng phí ManhPay (`.xlsx`, 2 sheet)
- **Sheet `BangPhi_KhachHang`:** 8 dòng phí, cột "Ví dụ GD 2.000.000" là **công thức Excel** `=IF(...)MAX(...)`
- **Sheet `BangPhi_Merchant`:** 4 hạng merchant (Đồng 1.2% → Kim Cương 0.6%)

### LIMIT-001 — Ma trận hạn mức & SLA *(mới)* (`.xlsx`, 2 sheet)
- **Sheet `HanMuc_Theo_Tier`:** bảng hạn mức trích xuất từ BR-002, có dòng TỔNG dùng công thức `SUM` (Tier 3 = 400.000.000)
- **Sheet `SLA_Xu_Ly`:** 10 dòng SLA nghiệp vụ, mỗi dòng ghi rõ **tài liệu nguồn** — mô phỏng bảng tra cứu nhanh thường gặp trong doanh nghiệp

**Lưu ý kỹ thuật bắt buộc:** đọc bằng `openpyxl` với `data_only=True` để lấy **giá trị đã tính**, không lấy chuỗi công thức. Nếu bỏ qua bước này, RAG sẽ nhận được `=IF(C11=0,0,MAX(...))` thay vì `30000` — lỗi phổ biến nhất khi xử lý Excel trong RAG.

---

## 8. Tài liệu vận hành & tích hợp — 3 tài liệu *(toàn bộ đều mới)*

| doc_id | Loại | Nội dung | Giá trị với hệ thống RAG |
|---|---|---|---|
| INC-001 | IncidentReport | Sự cố đối soát nạp tiền 08/02/2026: 1.240 giao dịch lỗi, root cause, timeline, biện pháp phòng ngừa | Cho phép trả lời câu hỏi kiểu "sự cố tương tự trước đây xử lý ra sao" |
| CR-LOG-001 | ChangeRequest | 5 yêu cầu thay đổi đã duyệt, mỗi CR ghi rõ **lý do phía sau con số** | Trả lời được câu hỏi "vì sao phí lại như hiện tại" — thứ mà BRD không có |
| INT-001 | IntegrationSpec | Tích hợp Napas 247 ở mức nghiệp vụ: các trường dữ liệu, nguyên tắc xử lý lỗi, SLA đối tác | Cầu nối giữa ngôn ngữ nghiệp vụ và kỹ thuật |

---

## 9. Bộ câu hỏi đánh giá (Evaluation Set) — 32 câu

File `Evaluation/evaluation_questions.json`, mỗi câu có: câu hỏi, `ground_truth`, `expected_source_docs`, và ghi chú mục đích kiểm thử.

| Nhóm | Số câu | Mục đích kiểm thử |
|---|---|---|
| `single_source` | 12 | Tra cứu trực tiếp một tài liệu — đo Context Precision cơ bản |
| `table_numeric` | 6 | Số liệu trong Excel, gồm cả ô có công thức — đo khả năng xử lý bảng |
| `multi_source` | 7 | Cần tổng hợp 2-3 tài liệu — đo Context Recall |
| `version_conflict` | 3 | Có bản cũ mâu thuẫn — đo hiệu quả **metadata filter** |
| `adversarial` | 4 | Không có đáp án trong KB — đo khả năng **từ chối trả lời** (chống hallucination) |

**Cách dùng để chứng minh giá trị từng tính năng trong báo cáo:**
- Chạy nhóm `version_conflict` **trước và sau** khi bật metadata filter → chứng minh tính năng lọc metadata
- Chạy nhóm `table_numeric` **trước và sau** khi xử lý riêng file Excel → chứng minh tính năng xử lý bảng
- Chạy nhóm `adversarial` → tính tỷ lệ từ chối đúng, đây là chỉ số chống hallucination

---

## Sơ đồ liên hệ tham chiếu chéo

```
BR-002 (Hạn mức — nguồn gốc, Approved)
   ├── BRD-001, BRD-002, BRD-003, BRD-004 tham chiếu
   ├── LIMIT-001 (Excel) trích xuất lại
   └── BR-002-v1 (Deprecated) ← bản cũ mâu thuẫn, phải bị lọc bỏ

FEE-001 (Bảng phí — nguồn gốc)
   ├── BRD-001 (phí nạp tiền), BRD-003 (phí merchant), BRD-004 (phí rút tiền)
   └── FAQ-001, FAQ-002 diễn giải lại cho người dùng cuối

INC-001 (Sự cố) → dẫn tới thay đổi ở SOP-005 v2.0 và INT-001 v1.3
                → sinh ra US-EPIC-021 (Epic khắc phục)

CR-LOG-001 (Nhật ký thay đổi) → giải thích lý do phía sau BR-002, FEE-001, BRD-004

GL-001 (Glossary) → giải nghĩa thuật ngữ dùng trong mọi tài liệu
```

Chuỗi liên kết **INC-001 → SOP-005 → INT-001 → US-EPIC-021** là phần giá trị nhất của bộ dữ liệu: nó tạo ra các câu hỏi mà chỉ hệ thống RAG tốt mới trả lời được (VD: "sau sự cố tháng 2, những tài liệu nào đã được cập nhật?"), thể hiện đúng cách tri thức doanh nghiệp liên kết với nhau trong thực tế.
