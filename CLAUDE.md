# ManhPay RAG Assistant

Trợ lý ảo RAG giúp BA/PO tra cứu tài liệu nghiệp vụ cho sản phẩm ví điện tử ManhPay (dữ liệu mô phỏng).

## Kiến trúc pipeline
Data ingestion → Chunking (structure-aware) → Embedding → ChromaDB (kèm metadata)
→ Hybrid Search (vector + BM25) → Metadata Filter → Reranking → LLM Generation (kèm trích dẫn) → UI (Streamlit)

## Cấu trúc thư mục
- `data/` — Knowledge Base, 20 tài liệu, KHÔNG tự sửa nội dung tài liệu trong này trừ khi được yêu cầu rõ
  - `data/metadata_catalog.json` — index toàn bộ tài liệu (doc_id, file_path, doc_type, module, version, status)
  - `data/Knowledge_Base_Catalog.md` — mô tả chi tiết từng tài liệu, đọc file này để hiểu ngữ nghĩa dữ liệu
  - `data/_scripts/` — script gốc để tái tạo file `.docx`/`.xlsx`, không phải code pipeline chính
- `src/` — code pipeline chính (ingestion, chunking, embedding, retrieval, generation)
- `tests/` — test cho từng module trong `src/`
- `notebooks/` — thử nghiệm nhanh, không cần chuẩn code sạch như `src/`

## Quy ước code
- Python 3.11, dùng virtualenv ở `venv/` (không commit thư mục này)
- Docstring tiếng Anh, comment giải thích nghiệp vụ bằng tiếng Việt
- Mỗi module trong `src/` nên có hàm `if __name__ == "__main__":` để test nhanh độc lập

## Lưu ý kỹ thuật BẮT BUỘC khi đọc dữ liệu (hay bị sai)
- File `.xlsx` (`Fees/`, `Limits/`): PHẢI đọc bằng `openpyxl.load_workbook(path, data_only=True)` hoặc `pandas.read_excel`. KHÔNG đọc chuỗi công thức thô (`=IF(...)`), vì 2 file này chứa công thức tính phí/tổng hạn mức.
- File `.docx` (`SOP_KYC_v2.1.docx`, `SOP_DoiSoat_v2.0.docx`): dùng `python-docx`, chú ý đọc cả bảng (`doc.tables`), không chỉ `doc.paragraphs` — `SOP_DoiSoat_v2.0.docx` có 1 bảng quan trọng về phân loại chênh lệch đối soát.
- Tài liệu trong `data/Deprecated/` có `status: Deprecated` trong metadata — khi build retrieval PHẢI lọc bỏ (`status == "Approved"`) trừ khi câu hỏi hỏi về lịch sử/thay đổi trong quá khứ.
- Luôn đọc metadata từ YAML front-matter ở đầu file `.md` (giữa hai dòng `---`), không parse bằng regex tùy tiện — dùng thư viện `python-frontmatter` hoặc `yaml.safe_load`.

## Lệnh hay dùng
- Kích hoạt venv: `source venv/bin/activate` (Mac/Linux) hoặc `venv\Scripts\activate` (Windows)
- Chạy toàn bộ test: `pytest tests/ -v` (KHÔNG gọi API, không tốn tiền)
- Chạy 1 test cụ thể: `pytest tests/test_ingestion.py -v`
- Đo lại retrieval (bảng Recall@3 4 cấu hình + thứ hạng Q015/Q018, ~4 phút, nạp 2 model, KHÔNG gọi API): `pytest tests/test_reranking.py -m slow -v -s` — kết quả mới nhất lưu ở `data/Evaluation/results_tuan7.json`
- Chạy test gọi Claude API thật (TỐN TIỀN, in bảng chi phí ở cuối): `pytest tests/test_generation.py -m llm -v`

## Compact instructions
Khi compact hội thoại, luôn giữ lại: danh sách file đã sửa trong `src/`, lệnh test đã chạy và kết quả, và các quyết định về schema dữ liệu (tên field, cấu trúc chunk).
