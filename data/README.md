# Bộ dữ liệu mẫu — RAG Assistant cho BA/PO (ManhPay)

Dữ liệu **mô phỏng** hệ sinh thái tài liệu nghiệp vụ của một công ty ví điện tử giả định ("ManhPay"). Không sử dụng dữ liệu thật của bất kỳ doanh nghiệp nào.

## Thống kê
- **20 tài liệu** thuộc 11 loại (doc_type), 12 module nghiệp vụ
- Định dạng: 16 `.md` + 2 `.docx` + 2 `.xlsx`
- **32 câu hỏi đánh giá** chia 5 nhóm, có sẵn `ground_truth` cho RAGAS

## Cấu trúc thư mục

```
ewallet_dataset/
├── BRD/                    4 file — Business Requirement Document
├── SOP/                    3 file — Quy trình vận hành (2 file .docx)
├── BusinessRules/          2 file — Quy tắc nghiệp vụ (hạn mức, AML)
├── Deprecated/             1 file — Bản hạn mức CŨ (test metadata filter)
├── UserStories/            2 file — Epic + User Story dạng Jira
├── FAQ/                    2 file — FAQ khách hàng + FAQ merchant
├── Glossary/               1 file — Từ điển thuật ngữ nghiệp vụ
├── Fees/                   1 file .xlsx — Bảng phí (2 sheet, có công thức)
├── Limits/                 1 file .xlsx — Ma trận hạn mức & SLA (2 sheet)
├── IncidentReports/        1 file — Báo cáo sự cố vận hành
├── ChangeRequests/         1 file — Nhật ký yêu cầu thay đổi
├── Integration/            1 file — Đặc tả tích hợp Napas 247
├── Evaluation/             evaluation_questions.json (32 câu)
├── metadata_catalog.json   Index toàn bộ tài liệu kèm metadata
├── Knowledge_Base_Catalog.md   Mô tả chi tiết từng tài liệu
└── _scripts/               Script sinh file .docx/.xlsx và catalog
```

## Ba đặc điểm thiết kế quan trọng

**1. Mâu thuẫn phiên bản có chủ đích**
`BR-002` (Approved, Tier 3 = 100 triệu) và `BR-002-v1` (Deprecated, Tier 3 = 50 triệu) chứa số liệu khác nhau. Không có metadata filter theo `status`, hệ thống RAG sẽ trả lời sai. Đây là bằng chứng định lượng cho tính năng lọc metadata trong báo cáo.

**2. Single source of truth + tham chiếu chéo**
Các con số quan trọng chỉ có một nguồn gốc (BR-002 cho hạn mức, FEE-001 cho phí); BRD/SOP/FAQ chỉ tham chiếu tới. Hệ thống phải truy xuất đúng nguồn gốc thay vì tài liệu chỉ nhắc lại.

**3. Chuỗi liên kết nhân quả**
`INC-001` (sự cố) → `SOP-005 v2.0` + `INT-001 v1.3` (tài liệu được cập nhật) → `US-EPIC-021` (Epic khắc phục). Chuỗi này tạo ra các câu hỏi tổng hợp nhiều nguồn mà chỉ RAG tốt mới trả lời được.

## Lưu ý kỹ thuật khi ingest

| Định dạng | Cách xử lý | Bẫy thường gặp |
|---|---|---|
| `.md` | Parse YAML front-matter lấy metadata, chunk theo heading | Chunk theo ký tự cố định làm vỡ ngữ cảnh mục |
| `.docx` | `python-docx` hoặc `pandoc` | Bỏ sót nội dung trong bảng (table) của Word |
| `.xlsx` | `openpyxl(data_only=True)` hoặc `pandas.read_excel` | Đọc ra chuỗi công thức `=IF(...)` thay vì giá trị đã tính |

## Bước tiếp theo
1. Viết script ingest đọc theo `metadata_catalog.json`
2. Chunk + embed + lưu ChromaDB kèm metadata
3. Chạy `Evaluation/evaluation_questions.json` qua RAGAS để có số liệu trước/sau mỗi cải tiến

## Tái tạo lại file nhị phân
```bash
cd _scripts
node sop_kyc.js && node sop_doisoat.js      # sinh 2 file .docx
python3 build_fee_table.py                   # sinh bảng phí .xlsx
python3 build_limit_sla_matrix.py            # sinh ma trận hạn mức .xlsx
python3 build_catalog.py                     # sinh lại metadata_catalog.json
```
