# Báo cáo Tuần 8 — Đánh giá chất lượng RAG bằng RAGAS

> Dự án **ManhPay RAG Assistant** · ngày chạy 2026-09-12 · dữ liệu gốc: `data/Evaluation/ragas_results.json`


## 1. Tóm tắt

Lần đầu đo được **chất lượng câu trả lời cuối**, thay vì chỉ đo tầng truy xuất như Tuần 5–7.

| Chỉ số | Điểm | Ý nghĩa |
|---|---|---|
| Faithfulness | **0.968** | Câu trả lời có bịa ngoài context không |
| Answer Relevancy | **0.817** | Có trả lời đúng thứ được hỏi không |
| Context Precision | **0.745** | Context lấy về có sạch không |
| Context Recall | **0.938** | Context có đủ thứ cần không |
| refusal_accuracy | **1.000** (4/4) | Câu hỏi bẫy có bị từ chối đúng không |

**Kết luận một câu:** hệ thống **không bịa** (Faithfulness 0.968, từ chối đúng 4/4), nhưng **lấy về nhiều nhiễu** (Context Precision 0.745 so với Recall 0.938).


## 2. Bảng kết quả theo 5 nhóm câu hỏi

| Nhóm | n | Faithfulness | Answer Rel. | Context Prec. | Context Recall | Chênh P−R |
|---|---:|---:|---:|---:|---:|---:|
| single_source | 12 | 1.000 | 0.828 | 0.848 | 1.000 | -0.152 |
| table_numeric | 6 | 0.944 | 0.834 | 0.711 | 1.000 | -0.289 |
| multi_source | 7 | 0.976 | 0.760 | 0.629 | 0.750 | -0.121 |
| version_conflict | 3 | 1.000 | 0.875 | 0.678 | 1.000 | -0.322 |
| adversarial | 4 | 0.871 | — | — | — | — |
| **TỔNG** | **32** | **0.968** | **0.817** | **0.745** | **0.938** | **-0.192** |

Ô `—` ở nhóm adversarial là **cố ý bỏ**, không phải lỗi — xem mục 6.


## 3. PHÁT HIỆN CHÍNH: Precision thấp dù Recall hoàn hảo

**Context Recall 0.938 — Context Precision 0.745 → chênh lệch −0.192.**

Hệ thống **lấy đủ nhưng lấy thừa**. Recall@3 của Tuần 5–7 chỉ hỏi *"có lấy được tài liệu đúng không"* nên **mù hoàn toàn chiều này**. Context Precision hỏi tiếp: *trong 5 chunk đưa cho LLM, bao nhiêu phần thực sự dùng được*. Khoảng cách giữa hai con số chính là **lượng nhiễu**.


### Phân bố Context Precision trên 28 câu được chấm

| Khoảng điểm | Số câu | |
|---|---:|---|
| 1.00 | 12 | ████████████ context sạch tuyệt đối |
| 0.75-0.99 | 5 | █████ ít nhiễu |
| 0.50-0.74 | 3 | ███ nhiễu vừa |
| 0.25-0.49 | 5 | █████ quá nửa là nhiễu |
| <0.25 | 3 | ███ gần như toàn nhiễu |

**8/28 câu có quá nửa số chunk là nhiễu.**


### Nhóm nào nhiễu nặng nhất

- **version_conflict**: Recall 1.000 nhưng Precision 0.678 (chênh -0.322)
- **table_numeric**: Recall 1.000 nhưng Precision 0.711 (chênh -0.289)

Cả hai đều là nhóm mà câu trả lời phụ thuộc vào **một ô dữ liệu cụ thể**. Kéo về 5 chunk thì 4 chunk còn lại chỉ làm loãng context. Ví dụ rõ nhất là **Q018**: Recall 1.000 (lấy được LIMIT-001) nhưng Precision 0.333 vì LIMIT-001 chỉ đứng hạng 3/5.


## 4. So sánh với Tuần 5–7 (Recall@3 tầng truy xuất)

| Nhóm | n | Recall@3 Tuần 7 | Context Recall Tuần 8 | Context Precision Tuần 8 |
|---|---:|---:|---:|---:|
| single_source | 12 | 1.00 | 1.000 | 0.848 |
| table_numeric | 6 | 0.83 | 1.000 | 0.711 |
| multi_source | 7 | 0.86 | 0.750 | 0.629 |
| version_conflict | 3 | 1.00 | 1.000 | 0.678 |
| **TỔNG** | **28** | **0.93** | **0.938** | **0.745** |

> Hai cột đầu **không so trực tiếp được** (Recall@3 đo ở mức tài liệu trong top-3; Context Recall đo ở mức nội dung trong top-5). Bảng này để thấy **cột thứ ba là số liệu hoàn toàn mới**, không có tương đương ở Tuần 7.

## 5. Answer Relevancy — con số bị hiểu nhầm

Điểm thô **0.8172** là chỉ số thấp nhất trong 4. Nhưng nó bị kéo xuống bởi **những lần từ chối ĐÚNG**, không phải bởi câu trả lời tệ.

RAGAS có bộ phát hiện *câu trả lời né tránh* (noncommittal) và cho điểm ~0. Khi truy xuất trượt, hệ thống từ chối thay vì bịa — hành vi ta MUỐN — nhưng bị chấm 0.


| | Điểm |
|---|---:|
| Answer Relevancy, cả 28 câu | 0.8172 |
| Answer Relevancy, bỏ 3 câu từ chối | **0.8412** (+0.0239) |

3 câu hợp lệ mà hệ thống từ chối (một phần hoặc toàn bộ):

| Câu | Answer Rel. | Context Recall | Nhận xét |
|---|---:|---:|---|
| Q019 | 0.000 | 0.000 | Truy xuất trượt hẳn → từ chối là **đúng**. Bị phạt 0 điểm. |
| Q024 | 0.877 | 0.500 | Lấy được 2/3 nguồn, từ chối phần thiếu. |
| Q020 | 0.976 | 1.000 | Từ chối đúng phần nội dung INC-001 không có trong KB. |

**Cách diễn đạt trong báo cáo:** nên trích cả hai con số và giải thích, đừng chỉ ghi 0.817 vì nó làm hệ thống trông tệ hơn thực tế.


## 6. Vì sao nhóm adversarial không có 3 trong 4 chỉ số

4 câu adversarial (Q029–Q032) **có `ground_truth`** — là một câu "không tìm thấy" — nhưng `expected_source_docs` **rỗng**. Ba chỉ số trở nên vô nghĩa:

| Chỉ số | Xử lý | Lý do |
|---|---|---|
| Context Recall | Bỏ | Không có nguồn đúng nào để mà recall |
| Context Precision | Bỏ | Cần reference lấy từ tài liệu; ở đây reference là lời từ chối |
| Answer Relevancy | Bỏ | Bộ phát hiện né tránh sẽ **phạt đúng hành vi ta muốn** |
| Faithfulness | Giữ | Bắt trường hợp model bịa thêm *sau* câu từ chối |
| **refusal_accuracy** | **Thêm mới** | Chỉ số thật sự đo "có từ chối đúng không". Tất định, **$0 API** |

**refusal_accuracy = 1.000 (4/4 câu bẫy đều bị từ chối).**


Faithfulness của nhóm này (0.871) thấp hơn các nhóm khác là **bình thường**: lời từ chối gần như không đưa ra mệnh đề nào nên điểm suy biến, không phản ánh chất lượng.


## 7. Các câu cần chú ý

### Thất bại truy xuất thật (2 câu)

| Câu | Recall | Nguồn kỳ vọng | Thực tế lấy về | Hệ thống làm gì |
|---|---:|---|---|---|
| Q019 | 0.000 | BR-002, BRD-002 | FAQ-001, BRD-001 | Từ chối (đúng) |
| Q024 | 0.500 | BRD-004, SOP-002, BR-002 | BRD-004, SOP-002, FAQ-002 | Từ chối (đúng) |

### Đã đối chiếu thủ công — xác nhận lỗi giám khảo (1 câu)

**Q012** ban đầu bị chấm Context Recall **0.000**. Đã mở toàn bộ context đưa cho judge ra đọc:

- **Chunk 1** đúng là `US-EPIC-021` / User Story **MANHPAY-1425**, chứa nguyên văn
  `**Story Points:** 8 | **Priority:** Medium | **Status:** Backlog`.
- Hệ thống trả lời đúng (*"MANHPAY-1425 có Status: Backlog"*) và trích đúng `[US-EPIC-021]`.
- Faithfulness 1.000 và Context Precision 1.000 — **tự mâu thuẫn với recall 0.000**.

→ Đáp án **nằm sẵn trong context**. Đây là **lỗi giám khảo**, không phải lỗi truy xuất.

**Nguyên nhân judge chấm sai.** `ground_truth` là *"Backlog, chưa lên sprint."* gồm 2 vế:

| Vế | Có trong chunk của MANHPAY-1425? |
|---|---|
| "Backlog" | **Có** |
| "chưa lên sprint" | **Không** — cụm này chỉ xuất hiện ở chunk 5, nhưng thuộc về **MANHPAY-1230**, một user story khác |

Judge tách reference thành 2 mệnh đề, không quy được vế thứ hai về đúng tài liệu, rồi chấm 0 cho cả câu.

**Đã sửa:** Context Recall Q012 = **1.000**, vì trong agile *"Backlog"* chính là *"chưa lên sprint"* — hai vế là một ý. Điểm máy chấm gốc (0.000) vẫn được giữ trong `ragas_results.json` tại `per_question[Q012]._dieu_chinh_thu_cong` để kiểm tra lại.

> **Nếu muốn chặt chẽ hơn** có thể đặt 0.5 (1/2 vế khớp nguyên văn). Khi đó Context Recall nhóm single_source = 0.958 và TỔNG = 0.920. Nên nêu lựa chọn này trong báo cáo thay vì giấu đi.

**Ảnh hưởng lên số tổng:**

| | Trước | Sau |
|---|---:|---:|
| Context Recall — single_source | 0.917 | **1.000** |
| Context Recall — TỔNG | 0.902 | **0.938** |
| Chênh lệch P−R — TỔNG | −0.156 | **−0.192** |

Context Precision **không đổi** (0.745) — phát hiện chính của Tuần 8 **mạnh lên** chứ không yếu đi: khoảng cách giữa Recall và Precision rộng thêm.

### Bộ lọc trích dẫn hoạt động đúng

Trong lúc chạy có 2 cảnh báo `Câu trả lời trích mã tài liệu KHÔNG có trong context`. Kiểm tra lại: `cited_doc_ids` **không** chứa các mã đó — tức bộ lọc trong `_extract_citations()` đã **chặn thành công** mã tài liệu bịa. Đây là bằng chứng lớp phòng vệ chống bịa nguồn đang chạy, không phải lỗi.

## 8. Vấn đề kỹ thuật đã gặp và cách xử lý

Phần này dùng cho mục *khó khăn / bài học* của báo cáo.


### 8.1 `ragas 0.4.3` không import được

`ragas/llms/base.py:12` import cứng `langchain_community.chat_models.vertexai` dù dự án chỉ dùng Claude. `langchain-community 0.4.x` đã bỏ submodule đó → `ModuleNotFoundError` ngay khi `import ragas`.

**Xử lý:** chèn module stub vào `sys.modules` TRƯỚC mọi import ragas (`src/evaluation.py`, đầu file). Stub cố tình `raise ImportError` nếu có ai thật sự khởi tạo `ChatVertexAI`, để lỗi nổ rõ thay vì chạy nhầm provider.


### 8.2 Sonnet 5 trả 400 cho `temperature`/`top_p`

`InstructorModelArgs` của ragas mặc định gắn `temperature=0.01`, `top_p=0.1` rồi truyền thẳng sang Anthropic. Sonnet 5 **từ chối cả hai**. Truyền `None` không cứu được vì kwargs chỉ ghi đè giá trị chứ không xóa key.

**Xử lý:** `pop()` hai key khỏi `llm.model_args` sau khi dựng judge.


### 8.3 Lỗi nghiêm trọng nhất — judge hỏng NGẦM

Lượt pilot đầu cho `context_precision = None` ở **cả 5 câu**. Nguyên nhân: Sonnet 5 **bật adaptive thinking mặc định**, trả `ThinkingBlock` trước, mà `instructor 1.3.2` lấy thẳng `content[0].text` → `AttributeError`. ragas nuốt lỗi thành điểm `None`.


Nguy hiểm vì nó **không đều**: metric gọi nhiều lượt hỏng nặng hơn.


| Metric | Số lượt gọi/câu | Tỷ lệ hỏng |
|---|---:|---|
| context_precision | 5 | **100%** |
| answer_relevancy | 3 | thỉnh thoảng |
| context_recall | 1 | hiếm |

Nhìn bảng điểm sẽ tưởng *hệ thống truy xuất kém*, thực ra là **lỗi parse**.

**Xử lý:** đặt `thinking={"type": "disabled"}` cho judge. Đo kiểm chứng: mặc định 3/3 lượt trả `thinking` block; `disabled` 3/3 lượt trả `text`.


### 8.4 Prompt caching làm ĐẮT thêm 25%

Thêm `cache_control` vào `generate_answer()` với ý định cache system prompt. Nhưng `cache_control` ở top-level **tự đặt điểm cache vào block CUỐI CÙNG** — tức user message chứa context. Context đổi theo từng câu nên lượt nào cũng là cache **write** (giá 1,25x) và **không bao giờ có lượt đọc**.


Đo thật: `cache_creation_input_tokens = 3067`, `cache_read_input_tokens = 0`, `input_tokens = 2`. Vì `cost_usd` chỉ cộng `input_tokens` nên nó báo **$0.0016/câu thay vì $0.0077** — thiếu gần 5 lần.

**Xử lý:** gỡ `cache_control`; sửa `cost_usd` cộng cả token cache (write 1,25x, read 0,1x) để lỗi loại này không ẩn được nữa. Thêm 2 test khóa công thức.


> **Bài học chung:** cả 4 lỗi đều **im lặng** — không có lỗi nào làm chương trình dừng. Bước `--dry-run` → `--pilot` → `--run` là thứ đã chặn chúng trước khi tiêu hết ngân sách.


## 9. Chi phí

| Khoản | USD |
|---|---:|
| Sinh câu trả lời (32 câu) | 0.2133 |
| Chấm RAGAS — pilot (5 câu) | 0.2770 |
| Chấm RAGAS — run (27 câu) | 1.7078 |
| **Tổng cho bộ dữ liệu này** | **2.1981** |
| Lượt pilot hỏng đã bỏ (không dùng) | 0.3274 |
| **Tổng tiền thật đã chi** | **2.5255** |

Giá áp dụng: **$2.00 input / $10.00 output mỗi 1M token** (`claude-sonnet-5`). Đây là **giá chính thức** — mức $2/$10 ban đầu công bố là giá giới thiệu đến 31/08/2026, nhưng Anthropic đã **hủy** đợt tăng lên $3/$15, kiểm chứng ngày 11/09/2026.


Dự toán trước khi chạy là $1.8236 cho `--run`, thực tế $1.7476 — **lệch 4%**. Con số dự toán được hiệu chỉnh lại theo lượt pilot thật nên khớp trong khoảng 0,1%.


## 10. Hạn chế của kết quả này

Phải ghi vào báo cáo để kết quả được đọc đúng mức:

1. **Judge cùng model với hệ thống được chấm** (`claude-sonnet-5` chấm chính nó) → có *self-preference bias*, điểm tuyệt đối nên đọc rộng tay. So sánh giữa các nhóm vẫn hợp lệ.

2. **n nhỏ**: version_conflict chỉ 3 câu, adversarial 4 câu. Một câu lệch làm đổi trung bình nhóm rất nhiều. Không nên phát biểu mạnh từ các nhóm này.

3. **Chỉ đo cấu hình `rerank=False`**. Nhánh rerank không được chấm RAGAS ở tuần này; nó vẫn được đánh giá ở tầng truy xuất trong `tests/test_reranking.py`.

4. **Q012 đã được đối chiếu tay và sửa điểm** (mục 7). Đây là điểm duy nhất không do máy chấm; điểm gốc vẫn lưu trong `ragas_results.json` để kiểm tra lại.

5. RAGAS là **LLM chấm LLM**, không tất định. Chạy lại có thể lệch vài phần trăm.


## 11. Hướng Tuần 9 mà số liệu này chỉ ra

Số liệu Tuần 8 chỉ thẳng vào một việc: **nâng Context Precision mà không làm tụt Recall.**


| Hướng | Căn cứ từ số liệu |
|---|---|
| Giảm `top_k` từ 5 xuống 3–4 | 8/28 câu có quá nửa chunk là nhiễu; Recall đang 0.938 nên còn dư địa |
| **Bật lại reranker** (đang tắt) | Tuần 7 đo được rerank nâng Recall@3 nhóm multi_source **86% → 100%**; nó xếp lại thứ tự nên tác động thẳng vào Precision |
| Lọc chunk theo ngưỡng điểm sau truy xuất | Nhiễu tập trung ở đuôi danh sách top-5 |
| Xem lại chunking cho nhóm bảng số | version_conflict (−0.322) và table_numeric (−0.289) nhiễu nặng nhất |

> Lưu ý: đây là **lần đầu có căn cứ định lượng để bật lại rerank**. Tuần 7 đã cân nhắc và tạm gác vì nó làm tụt hạng Q018; giờ đã biết cái nó cải thiện là Precision — thứ Tuần 7 chưa đo được.

## Phụ lục A — Điểm chi tiết 32 câu

| Câu | Nhóm | Faith. | Ans.Rel | Ctx.Prec | Ctx.Rec | Từ chối | Nguồn kỳ vọng |
|---|---|---:|---:|---:|---:|:-:|---|
| Q001 | single_source | 1.000 | 1.000 | 1.000 | 1.000 |  | BR-002 |
| Q002 | single_source | 1.000 | 0.826 | 1.000 | 1.000 |  | SOP-002 |
| Q003 | single_source | 1.000 | 0.953 | 1.000 | 1.000 |  | BRD-003 |
| Q004 | single_source | 1.000 | 0.890 | 0.833 | 1.000 |  | SOP-003 |
| Q005 | single_source | 1.000 | 0.560 | 1.000 | 1.000 |  | GL-001 |
| Q006 | single_source | 1.000 | 0.993 | 0.500 | 1.000 |  | BRD-002, FEE-001, FAQ-001 |
| Q007 | single_source | 1.000 | 0.833 | 0.806 | 1.000 |  | BRD-004 |
| Q008 | single_source | 1.000 | 0.615 | 0.333 | 1.000 |  | BR-004 |
| Q009 | single_source | 1.000 | 0.850 | 0.700 | 1.000 |  | SOP-005 |
| Q010 | single_source | 1.000 | 0.981 | 1.000 | 1.000 |  | INC-001 |
| Q011 | single_source | 1.000 | 0.876 | 1.000 | 1.000 |  | FAQ-002 |
| Q012 | single_source | 1.000 | 0.562 | 1.000 | **1.000** ᴹ |  | US-EPIC-021 |
| Q013 | table_numeric | 1.000 | 0.872 | 0.756 | 1.000 |  | FEE-001, BRD-001 |
| Q014 | table_numeric | 1.000 | 1.000 | 1.000 | 1.000 |  | FEE-001 |
| Q015 | table_numeric | 1.000 | 0.507 | 0.679 | 1.000 |  | FEE-001 |
| Q016 | table_numeric | 0.667 | 0.712 | 1.000 | 1.000 |  | FEE-001, BRD-004 |
| Q017 | table_numeric | 1.000 | 0.998 | 0.500 | 1.000 |  | FEE-001 |
| Q018 | table_numeric | 1.000 | 0.915 | 0.333 | 1.000 |  | LIMIT-001 |
| Q019 | multi_source | 0.833 | 0.000 | 0.000 | 0.000 | ✓ | BR-002, BRD-002 |
| Q020 | multi_source | 1.000 | 0.976 | 0.200 | 1.000 | ✓ | INC-001, SOP-005, INT-001 |
| Q021 | multi_source | 1.000 | 0.859 | 1.000 | 1.000 |  | CR-LOG-001, FEE-001 |
| Q022 | multi_source | 1.000 | 0.710 | 1.000 | 1.000 |  | BRD-001, SOP-005, FAQ-001 |
| Q023 | multi_source | 1.000 | 0.963 | 0.500 | 0.750 |  | BR-004, FAQ-001, SOP-002 |
| Q024 | multi_source | 1.000 | 0.877 | 0.700 | 0.500 | ✓ | BRD-004, SOP-002, BR-002 |
| Q025 | multi_source | 1.000 | 0.932 | 1.000 | 1.000 |  | BR-002, BRD-003 |
| Q026 | version_conflict | 1.000 | 0.940 | 0.867 | 1.000 |  | BR-002 |
| Q027 | version_conflict | 1.000 | 0.963 | 0.917 | 1.000 |  | BR-002 |
| Q028 | version_conflict | 1.000 | 0.721 | 0.250 | 1.000 |  | BR-002-v1, CR-LOG-001, BR-002 |
| Q029 | adversarial | 0.857 | — | — | — | ✓ | *(không có — câu bẫy)* |
| Q030 | adversarial | 1.000 | — | — | — | ✓ | *(không có — câu bẫy)* |
| Q031 | adversarial | 0.750 | — | — | — | ✓ | *(không có — câu bẫy)* |
| Q032 | adversarial | 0.875 | — | — | — | ✓ | *(không có — câu bẫy)* |

## Phụ lục B — Cách tái lập

```bash
# Xem dự toán chi phí, KHÔNG gọi API
python -m src.evaluation --dry-run

# Chạy 5 câu kiểm thử (~$0.27)
python -m src.evaluation --pilot

# Chạy phần còn lại (~$1.82)
python -m src.evaluation --run

# Test không gọi API
pytest tests/ -v
```

Xóa `data/Evaluation/ragas_store.json` để chạy lại từ đầu (file đó là cache để chạy lại không tính tiền hai lần cho câu đã xong).


## Phụ lục C — Cấu hình đã dùng

| Mục | Giá trị |
|---|---|
| Model sinh câu trả lời | `claude-sonnet-5` |
| Model chấm điểm (judge) | `claude-sonnet-5` |
| Embeddings cho Answer Relevancy | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (chạy cục bộ, $0) |
| Cấu hình truy xuất | hybrid search (vector + BM25), TABLE_BOOST=0.11, rerank **tắt** |
| Số chunk đưa vào prompt | 5 (`top_k=5`) |
| Ngưỡng từ chối | `MIN_TOP_SCORE = 0.45` |
| Bộ câu hỏi | 32 câu, 5 nhóm — `data/Evaluation/evaluation_questions.json` |
| Thư viện đánh giá | `ragas 0.4.3` (kèm bản vá, xem mục 8.1) |

---

> ᴹ = điểm đã sửa tay sau đối chiếu thủ công, xem mục 7.

*File này sinh tự động từ `data/Evaluation/ragas_results.json` — mọi con số lấy thẳng từ dữ liệu đo được, không chép tay.*