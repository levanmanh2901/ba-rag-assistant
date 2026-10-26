# ManhPay RAG Assistant - Trợ lý tra cứu tài liệu nghiệp vụ cho Business Analyst

> Hệ thống hỏi đáp trên kho tài liệu nghiệp vụ của một sản phẩm ví điện tử, ứng dụng kỹ thuật Retrieval-Augmented Generation (RAG). Câu trả lời luôn kèm trích dẫn nguồn, và hệ thống chủ động từ chối khi không đủ căn cứ.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Tests](https://img.shields.io/badge/tests-156%20passed-brightgreen)
![Recall@3](https://img.shields.io/badge/Recall%403-93%25-success)
![Faithfulness](https://img.shields.io/badge/Faithfulness-0.968-success)

<p align="center">
  <img src="assets/kien-truc-he-thong.png" width="640" alt="Kiến trúc hệ thống">
</p>

---

## 1. Bài toán nghiệp vụ (Problem Statement)

Trong đội phát triển sản phẩm ví điện tử, tài liệu nghiệp vụ gồm BRD, SOP, Business Rules, biểu phí và ma trận hạn mức tăng nhanh theo từng tính năng. Business Analyst gặp ba vấn đề khi tra cứu:

| # | Vấn đề | Tác động nghiệp vụ |
|---|--------|--------------------|
| 1 | Cách diễn đạt của người hỏi khác văn phong tài liệu | Tìm theo từ khóa bỏ sót thông tin, mất thời gian dò thủ công |
| 2 | Một con số xuất hiện ở nhiều tài liệu, chỉ một nơi là nguồn gốc | Trích dẫn nhầm tài liệu tham chiếu thay vì tài liệu gốc |
| 3 | Tài liệu hết hiệu lực tồn tại song song bản mới | Rủi ro dùng nhầm quy định cũ khi viết spec hoặc trả lời stakeholder |

**Giá trị kỳ vọng:** rút ngắn thời gian tra cứu, giảm rủi ro dùng sai số liệu trong tài liệu bàn giao cho đội phát triển.

## 2. Đối tượng sử dụng (Stakeholders)

| Vai trò | Nhu cầu chính | Mức độ liên quan |
|---------|---------------|------------------|
| Business Analyst | Tra cứu nhanh quy định, hạn mức, biểu phí kèm nguồn | Người dùng chính |
| Content Admin | Cập nhật tài liệu, gắn metadata, kiểm soát phiên bản | Người quản trị dữ liệu |
| Product Owner | Đối chiếu quy định hiện hành khi ra quyết định sản phẩm | Người dùng phụ |

## 3. Phạm vi (Scope)

**Trong phạm vi**
- Tra cứu bằng ngôn ngữ tự nhiên trên 20 tài liệu nghiệp vụ, 11 loại, 3 định dạng (.md, .docx, .xlsx)
- Trích dẫn nguồn ở cấp mã tài liệu cho từng câu trả lời
- Lọc theo module, loại tài liệu và trạng thái hiệu lực
- Từ chối trả lời khi kho tri thức không có căn cứ
- Đánh giá định lượng chất lượng hệ thống

**Ngoài phạm vi**
- Xác thực và phân quyền người dùng ở mức sản phẩm thương mại
- Tự động đồng bộ với hệ quản trị tài liệu của doanh nghiệp
- Huấn luyện hoặc tinh chỉnh mô hình ngôn ngữ
- Triển khai hạ tầng production

## 4. Yêu cầu (Requirements)

### 4.1 Yêu cầu chức năng

| Mã | Yêu cầu | Ưu tiên |
|----|---------|---------|
| FR-01 | Người dùng đặt câu hỏi bằng tiếng Việt tự nhiên | Must |
| FR-02 | Hệ thống trả lời kèm mã tài liệu nguồn cho từng thông tin | Must |
| FR-03 | Hệ thống từ chối và nêu lý do khi không đủ căn cứ | Must |
| FR-04 | Loại trừ tài liệu hết hiệu lực khỏi kết quả theo mặc định | Must |
| FR-05 | Cho phép tra cứu tài liệu hết hiệu lực khi hỏi thông tin lịch sử | Should |
| FR-06 | Lọc kết quả theo module và loại tài liệu | Should |
| FR-07 | Hiển thị điểm số truy xuất của từng đoạn ngữ cảnh | Could |

### 4.2 Yêu cầu phi chức năng

| Mã | Yêu cầu | Kết quả đo được |
|----|---------|-----------------|
| NFR-01 | Chạy được trên máy cá nhân không có GPU | Đạt |
| NFR-02 | Thời gian phản hồi trung bình dưới 5 giây | 2,9 giây |
| NFR-03 | Không bịa thông tin ngoài kho tri thức | Faithfulness 0,968 |
| NFR-04 | Mỗi thay đổi phải có kiểm thử tự động bảo vệ | 156 test, không gọi API |

## 5. Quy tắc nghiệp vụ (Business Rules)

| Mã | Quy tắc |
|----|---------|
| BR-01 | Số liệu trong câu trả lời phải sao chép nguyên văn từ tài liệu, hệ thống không tự tính toán |
| BR-02 | Mỗi loại số liệu chỉ có một tài liệu gốc, các tài liệu khác chỉ được tham chiếu |
| BR-03 | Tài liệu trạng thái Deprecated bị loại trừ mặc định, chỉ dùng khi người dùng bật tùy chọn lịch sử |
| BR-04 | Tài liệu được nhắc tới nhưng không có nội dung trong kho không được dùng làm căn cứ trả lời |
| BR-05 | Mã tài liệu trong câu trả lời phải nằm trong danh sách đã đưa vào ngữ cảnh |

## 6. Kiến trúc và luồng xử lý

```
Câu hỏi → Lọc metadata → Truy xuất lai (Vector + BM25 + bù điểm bảng)
        → Ngưỡng chặn → Mô hình ngôn ngữ (6 quy tắc) → Câu trả lời + trích dẫn
```

| Thành phần | Công nghệ | Vai trò nghiệp vụ |
|------------|-----------|-------------------|
| Ingestion | python-docx, openpyxl | Chuẩn hóa tài liệu đa định dạng về một dạng thống nhất |
| Chunking | Structure-aware | Giữ nguyên bảng biểu phí và hạn mức trong cùng một đoạn |
| Embedding | paraphrase-multilingual-MiniLM-L12-v2 | Hiểu câu hỏi diễn đạt khác văn phong tài liệu |
| Vector store | ChromaDB | Lưu vector kèm metadata phục vụ lọc theo trạng thái |
| Hybrid search | Vector + BM25 | Bắt chính xác số liệu và mã tài liệu |
| Generation | Claude Sonnet 5 | Sinh câu trả lời có trích dẫn, từ chối khi thiếu căn cứ |
| Giao diện | Streamlit | Cho phép BA tự kiểm chứng nguồn của câu trả lời |

## 7. Kết quả đo được (Metrics)

### 7.1 Tầng truy xuất — thí nghiệm đối chứng, 28 câu hỏi

| Cấu hình | Recall@3 | Đóng góp riêng |
|----------|----------|----------------|
| Vector-only | 54% | Đường cơ sở |
| + Lọc metadata | 57% | +1 câu |
| + BM25 | 89% | +9 câu (82% mức cải thiện) |
| + Bù điểm cho bảng | **93%** | +1 câu |

### 7.2 Tầng câu trả lời — khung RAGAS, 32 câu hỏi

| Chỉ số | Kết quả | Ý nghĩa nghiệp vụ |
|--------|---------|-------------------|
| Faithfulness | 0,968 | Câu trả lời bám sát tài liệu, không bịa thông tin |
| Context Recall | 0,938 | Hiếm khi bỏ sót tài liệu cần thiết |
| Context Precision | 0,745 | Ngữ cảnh còn lẫn nội dung không liên quan |
| Refusal accuracy | 4/4 | Từ chối đúng toàn bộ câu hỏi không có đáp án |

> Chi tiết phương pháp đo và phân tích: xem `docs/05-traceability-matrix.md`

## 8. Kịch bản kiểm thử chấp nhận (UAT)

| # | Kịch bản | Kết quả kỳ vọng | Trạng thái |
|---|----------|-----------------|------------|
| 1 | Hỏi hạn mức chuyển tiền P2P của Tier 2 | Trả lời đúng số, trích dẫn tài liệu gốc | Đạt |
| 2 | Hỏi về Tier 4 (không tồn tại) | Từ chối, nêu rõ chỉ có 3 cấp Tier | Đạt |
| 3 | Nhập chuỗi ký tự vô nghĩa | Chặn trước khi gọi mô hình | Đạt |
| 4 | Lọc module KYC rồi hỏi về hạn mức | Từ chối, xác nhận bộ lọc có hiệu lực | Đạt |
| 5 | Bật tài liệu hết hiệu lực, hỏi quy định cũ | Trả về bản cũ kèm nhãn cảnh báo | Đạt |
| 6 | Để trống ô câu hỏi | Cảnh báo, không gọi mô hình | Đạt |

## 9. Quyết định kỹ thuật và căn cứ (Decision Log)

| Quyết định | Căn cứ định lượng |
|------------|-------------------|
| Chọn RAG thay vì tinh chỉnh mô hình | Cập nhật tri thức bằng cập nhật tài liệu, có trích dẫn nguồn, không cần GPU |
| Bù điểm 0,11 cho đoạn chứa bảng | Đoạn từ Excel có điểm vector trung bình 0,163 so với 0,272 của văn xuôi |
| Tắt bước xếp hạng lại theo mặc định | Nâng Context Precision 0,099 nhưng làm một câu hợp lệ bị từ chối và tăng thời gian phản hồi từ 2,9 lên 5,7 giây |
| Ngưỡng chặn 0,45 không dùng để chống câu hỏi bẫy | Không tồn tại ngưỡng chặn được câu bẫy mà không chặn oan câu hợp lệ |

## 10. Rủi ro đã ghi nhận (Risk Log)

| Rủi ro | Mức độ | Biện pháp |
|--------|--------|-----------|
| Dữ liệu mô phỏng chưa đối chiếu với nghiệp vụ thật | Cao | Đang bổ sung bảng đối chiếu với nguồn công khai và thẩm định bởi người có chuyên môn |
| Mô hình chấm điểm cùng loại với mô hình sinh câu trả lời | Trung bình | Ghi nhận trong báo cáo, đề xuất dùng mô hình giám khảo độc lập |
| Kho tri thức nhỏ, tham số có thể không tổng quát | Trung bình | Các tham số đều truy ngược được về phép đo, cần đo lại khi mở rộng dữ liệu |

## 11. Cách chạy

```bash
git clone https://github.com/<tài-khoản>/ba-rag-assistant.git
cd ba-rag-assistant
pip install -r requirements.txt
cp .env.example .env          # điền API key
python -m src.ingestion       # nạp dữ liệu và xây chỉ mục
streamlit run app.py
```

Chạy kiểm thử (không gọi API, không phát sinh chi phí):

```bash
pytest tests/ -v
```

## 12. Cấu trúc thư mục

```
ba-rag-assistant/
├── app.py              # Giao diện Streamlit
├── src/                # Pipeline RAG theo thứ tự xử lý
├── data/               # Kho tri thức mô phỏng và bộ câu hỏi đánh giá
├── notebooks/          # Notebook thí nghiệm và đánh giá
├── tests/              # Kiểm thử tự động, gồm kiểm thử nhất quán nghiệp vụ
└── requirements.txt    # Danh sách thư viện
```

## 13. Lưu ý về dữ liệu

Toàn bộ tài liệu trong `data/` là **dữ liệu mô phỏng** cho một sản phẩm ví điện tử giả định, được xây dựng phục vụ mục đích học thuật. Không sử dụng dữ liệu thật của bất kỳ doanh nghiệp nào.

## 14. Hướng phát triển

- Trộn điểm giữa truy xuất lai và xếp hạng lại theo trọng số
- Giảm nhiễu trong ngữ cảnh để nâng Context Precision
- Đối chiếu bộ dữ liệu với quy định và biểu phí công khai trên thị trường
- Tích hợp với hệ quản trị tài liệu để kho tri thức tự cập nhật

---
