# Hệ chuyên gia tư vấn vi phạm luật giao thông đường bộ

Đồ án môn Công nghệ tri thức. Người dùng kể tình huống bằng tiếng Việt; hệ thống xác định **hành vi vi phạm, điều
khoản áp dụng, khung phạt, mức phạt đề xuất, hình thức bổ sung / trừ điểm**, và **giải thích chuỗi suy luận**.

- Kết luận pháp lý do bộ suy luận OWL (HermiT) chạy trên ontology + 303 luật SWRL đưa ra. Mỗi luật có mã `R0xx` truy
  về điều/khoản/điểm và nguyên văn trong `data/raw/`.
- LLM (Gemini) chỉ hiểu ngôn ngữ (trích sự kiện, suy ra sự kiện gián tiếp) và diễn đạt câu trả lời; câu trả lời được
  kiểm tra tự động để không dẫn điều khoản, số tiền ngoài chuỗi suy luận.
- Áp đúng văn bản có hiệu lực tại ngày vi phạm: NĐ 100/2019 (V1), NĐ 100 + NĐ 123/2021 (V2), NĐ 168/2024 (V3),
  NĐ 168 + NĐ 238/2026 (V4), cùng Luật GTĐB 2008, Luật TTATGT, Luật XLVPHC, TT 31/2019, TT 38/2024.
- Phạm vi: xe mô tô/gắn máy và ô tô, 60 hành vi phổ biến. Thiếu thông tin thì hỏi lại.

Trên bộ 50 tình huống đánh giá: 90% tình huống đúng trọn vẹn, F1 điều khoản 93,6%; baseline chỉ dùng LLM đạt 16% và
dẫn văn bản hết hiệu lực ở 72% căn cứ (chi tiết: [evaluation/results/results.md](evaluation/results/results.md)).

**Kết quả chỉ mang tính tham khảo, không thay thế quyết định của người có thẩm quyền.**

Kiến trúc và luồng xử lý: [docs/architecture.md](docs/architecture.md).

---

## 1. Yêu cầu

| | |
|---|---|
| Hệ điều hành | Windows 10/11 (đã chạy thử); Linux/macOS dùng lệnh tương đương |
| Python | 3.11 trở lên (đã chạy với 3.13) |
| Java | **25 trở lên** — HermiT đi kèm owlready2 0.51 cần Java 25 |
| RAM | 8 GB (mô hình embedding bge-m3 ~2 GB, JVM ~2 GB) |
| Đĩa | ~6 GB (thư viện Python, mô hình bge-m3 tải lần đầu) |
| Mạng | cần để gọi Gemini và tải mô hình lần đầu |
| Khóa API | Google Gemini (miễn phí, lấy ở Google AI Studio — mục 4) |

## 2. Cài đặt

Chạy trong PowerShell, tại thư mục gốc project (`DoAn/`).

**Bước 1 — môi trường Python**
```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Bước 2 — Java 25.** Tải bản portable Temurin 25 (JDK) tại https://adoptium.net và giải nén vào
`%USERPROFILE%\.jdks\` (vd. `C:\Users\<tên>\.jdks\jdk-25.0.5+8`) — hệ thống tự tìm thấy. Nếu để chỗ khác, ghi đường
dẫn `java.exe` vào `JAVA_EXE` trong `.env`.

**Bước 3 — cấu hình**
```powershell
copy .env.example .env
```
Mở `.env`, điền `GEMINI_API_KEY` (cách lấy ở mục 4). Không commit file `.env`.

**Bước 4 — kiểm tra**
```powershell
python -m scripts.check_env        # Python, thư viện, Java, Pellet/HermiT trên ontology mẫu
python -m scripts.check_llm --list # các model Gemini khóa của bạn dùng được
python -m scripts.check_llm        # gọi thử một request
```

**Bước 5 — (tùy chọn) sinh lại cơ sở tri thức và chạy test**
```powershell
python -m scripts.build_all        # văn bản → articles → luật → ontology (~10 giây); repo đã có sẵn kết quả
python -m src.explanation.retriever --build   # chỉ mục RAG cho gợi ý tra cứu (một lần, ~25 phút trên CPU)
pytest                             # 236 test, ~10–15 phút (chạy HermiT thật)
```
Chỉ mục RAG chỉ cần cho phần "quy định có thể liên quan" khi không phát hiện vi phạm; thiếu chỉ mục thì phần đó bị
bỏ qua, các chức năng khác vẫn chạy. Lần đầu dùng đến embedding, hệ thống tải mô hình `BAAI/bge-m3` (~2 GB).

## 3. Chạy

### Giao diện web
```powershell
python -m scripts.run_app
```
Bật API (http://localhost:8000/docs) và giao diện (http://localhost:8501), tự mở trình duyệt khi sẵn sàng. Để cửa
sổ terminal mở trong lúc dùng; Ctrl+C để tắt. Lần gửi tin nhắn đầu mất khoảng 1 phút (nạp mô hình, khởi động Java).

- **Cột trái:** khung chat nhiều lượt. Hệ thống hỏi lại khi thiếu thông tin (loại xe, nồng độ, tốc độ, ngày...).
- **Cột phải:** *Sự kiện* (giá trị hệ thống đã hiểu — sửa rồi bấm *Chạy lại suy luận*), *Cây suy luận* (đồ thị sự
  kiện → quy tắc → hành vi → điều khoản), *Điều khoản* (nguyên văn theo phiên bản áp dụng), *Chi tiết* (mức phạt,
  mã quy tắc, kết quả kiểm tra chống bịa).
- **Thanh bên:** ô chọn ngày vi phạm, nút *Vụ việc mới*.

Chỉ chạy giao diện (không API): `streamlit run app/streamlit_app.py` — giao diện tự chạy hệ thống trong cùng tiến trình.

### Dòng lệnh
```powershell
python -m scripts.chat             # hội thoại; lệnh: /moi (vụ mới), /hoso (xem hồ sơ), /thoat
python -m scripts.chat -m "Tối qua thấy CSGT vẫy thì em rồ ga chạy luôn, không đội mũ" -m "xe máy 110 phân khối"
python -m scripts.chat --ngay 2023-06-01 -m "Tôi lái ô tô, đo nồng độ cồn 0,3 mg/lít khí thở"
```
| Tùy chọn | Ý nghĩa |
|---|---|
| `--ngay YYYY-MM-DD` | ngày vi phạm (như ô chọn ngày trên giao diện) |
| `--hom-nay YYYY-MM-DD` | cố định "hôm nay" để chạy lại cho cùng kết quả |
| `--chi-tiet` | in thêm bản trình bày tự động, mã quy tắc, kết quả kiểm tra chống bịa |
| `--khong-dien-dat` | không dùng LLM viết câu trả lời (bản tự động) |
| `--khong-suy-ra` | tắt suy ra sự kiện gián tiếp |
| `--json` | in toàn bộ kết quả dạng JSON |

### API
`uvicorn src.api.main:app --port 8000` — tài liệu tương tác ở http://localhost:8000/docs. Các endpoint chính:
`POST /phien` (tạo phiên), `POST /phien/{id}/tin-nhan`, `PATCH /phien/{id}/ho-so` (sửa sự kiện rồi chạy lại),
`PUT /phien/{id}/ngay`, `GET /dieu-khoan/{id}` (nguyên văn điều khoản).

### Ví dụ để thử
- "Tối qua tôi đi xe máy, CSGT đo nồng độ cồn được 0,45 mg/l khí thở."
- "Ngày 10/3/2025 tôi lái ô tô chạy 80 cây trong khu dân cư, đường đôi." (tốc độ tối đa tra theo TT 38)
- "Thấy CSGT vẫy thì em rồ ga chạy luôn." (hành vi gián tiếp — hệ thống suy ra, rồi hỏi loại xe)
- "Hôm qua tôi đi xe máy vượt đèn vàng." (hệ thống hỏi xe đã qua vạch dừng chưa)
- Cùng một lời kể với `--ngay 2023-06-15` và `--ngay 2025-06-15` để thấy khác biệt giữa NĐ 100 và NĐ 168.

## 4. Cấu hình LLM

LLM chỉ dùng để hiểu ngôn ngữ và diễn đạt — **không** quyết định điều khoản hay mức phạt. Chọn bằng `LLM_PROVIDER`.

### Google Gemini (mặc định, gói miễn phí)
1. Mở **Google AI Studio**: https://aistudio.google.com/apikey, đăng nhập tài khoản Google.
2. Bấm **Create API key** (chọn hoặc tạo một Google Cloud project nếu được hỏi), sao chép khóa.
3. Trong `.env`:
   ```
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=<khóa vừa tạo>
   GEMINI_MODEL=gemini-3.5-flash-lite
   ```
4. Kiểm tra bằng `python -m scripts.check_llm --list` rồi `python -m scripts.check_llm`.

Lưu ý gói miễn phí:
- Có hạn mức request mỗi phút/ngày theo model. Đặt `LLM_MAX_RPM` thấp hơn hạn mức; gặp lỗi 429 thì client tự chờ
  (theo `retryDelay` của máy chủ hoặc backoff lũy thừa) và thử lại tối đa `LLM_MAX_RETRIES` lần.
- Phản hồi được cache ở `.cache/llm/` (khóa = provider + model + prompt): hỏi lại cùng câu không tốn request.
- Theo điều khoản của Google, dữ liệu gửi qua gói miễn phí có thể được dùng để cải thiện sản phẩm — không gửi thông
  tin cá nhân thật khi thử nghiệm.

### Ollama (dự phòng, chạy trên máy)
1. Cài Ollama tại https://ollama.com, rồi `ollama pull qwen2.5:7b`.
2. Trong `.env`: `LLM_PROVIDER=ollama`, `OLLAMA_MODEL=qwen2.5:7b`.
3. Máy chỉ có CPU chạy model 7B rất chậm (1–3 phút mỗi lần gọi); bước suy ra sự kiện và diễn đạt có thể quá thời gian
   chờ — khi đó hệ thống tự dùng phương án dự phòng (kết luận từ sự kiện trực tiếp, câu trả lời tự động). Tăng
   `OLLAMA_TIMEOUT_S` hoặc dùng model nhỏ hơn (`qwen2.5:3b`).

Cả hai provider trả JSON theo schema (Gemini: JSON schema mode; Ollama: `format: "json"`); mọi phản hồi được kiểm tra
bằng Pydantic, sai schema thì gọi lại một lần kèm thông báo lỗi.

### Các biến khác trong `.env`
| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `LLM_MAX_RPM` | 10 | giới hạn request/phút |
| `LLM_MAX_RETRIES`, `LLM_BACKOFF_BASE_S` | 5, 2 | thử lại khi 429 / lỗi tạm thời |
| `LLM_CACHE` | true | cache phản hồi LLM |
| `EMBEDDING_MODEL`, `EMBEDDING_DEVICE` | BAAI/bge-m3, cpu | mô hình embedding cho ánh xạ node và RAG |
| `ENTITY_LINK_THRESHOLD` | 0.80 | ngưỡng cosine của ánh xạ bằng embedding (đo bằng `python -m evaluation.calib_entity_link`) |
| `ENTITY_LINK_EMBEDDING` | true | bật ánh xạ bằng embedding khi từ điển đồng nghĩa không khớp |
| `JAVA_EXE`, `JAVA_MEMORY_MB` | (tự tìm), 2000 | Java cho reasoner |
| `REASONER` | hermit | hermit \| pellet |

## 5. Đánh giá

```powershell
python -m evaluation.sinh_nhan    # sinh nhãn chuẩn data/test/scenarios.jsonl từ data/test/scenarios_src.yaml
python -m evaluation.ablation     # hệ thống đầy đủ + 4 ablation + baseline chỉ-LLM (~1 giờ với gói Gemini miễn phí)
python -m evaluation.bao_cao      # bảng, biểu đồ, evaluation/results/results.md
```
Bộ tình huống và cách gán nhãn: [data/test/annotation_guide.md](data/test/annotation_guide.md). Lần chạy bị ngắt
(vd. hết hạn mức Gemini) thì chạy lại để tiếp tục các tình huống còn thiếu.

## 6. Cấu trúc thư mục

```
DoAn/
├── app/streamlit_app.py          giao diện
├── config/                       cấu hình tri thức: văn bản & phiên bản, hành vi ↔ điều khoản, điều kiện luật,
│                                 ngưỡng, câu hỏi làm rõ, ngưỡng suy ra sự kiện...
├── data/raw/                     văn bản pháp luật gốc (.docx)
├── data/processed/               articles_v1..v4.jsonl, support_*.jsonl, synonyms.json, speed_limits.json
├── data/test/                    bộ tình huống đánh giá + hướng dẫn gán nhãn
├── docs/                         architecture.md, ontology_design.md, rules_design.md, mvp_behaviors.md
├── evaluation/                   chạy đánh giá, baseline, ablation, metric; results/ (kết quả, biểu đồ, results.md)
├── ontology/                     traffic_law.owl, rules/*.swrl, rule_registry.yaml, reasoning/ (theo phiên bản)
├── scripts/                      build_all, check_env, check_llm, chat (CLI), run_app
├── src/                          ingest, kb, llm, extraction, inference, explanation, dialogue, api
└── tests/                        236 test (pytest)
```
Mô tả từng module: [docs/architecture.md](docs/architecture.md#8-bản-đồ-mã-nguồn). Thiết kế ontology và luật:
[docs/ontology_design.md](docs/ontology_design.md), [docs/rules_design.md](docs/rules_design.md). Bảng 60 hành vi và
điều khoản theo phiên bản: [docs/mvp_behaviors.md](docs/mvp_behaviors.md).

## 7. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| `Không tìm thấy Java` / lỗi `UnsupportedClassVersionError` | Cài Java **25+** (bước 2); kiểm tra bằng `python -m scripts.check_env` |
| Gemini báo 404 "model … no longer available" | Chạy `python -m scripts.check_llm --list`, đổi `GEMINI_MODEL` sang model có trong danh sách |
| Báo 429 / hết hạn mức | Chờ hoặc giảm `LLM_MAX_RPM`; đánh giá hàng loạt chạy lại sẽ tiếp tục phần còn thiếu |
| `LLM_PROVIDER='anthropic' không hỗ trợ` dù `.env` đã đúng | Terminal còn giữ biến cũ (biến môi trường ghi đè `.env`): `Remove-Item Env:LLM_PROVIDER` hoặc mở terminal mới; trong VS Code đặt `"python.terminal.useEnvFile": false` |
| http://localhost:8501 không mở được | Lần chạy trước còn treo giữ cổng: đóng terminal cũ (Ctrl+C) rồi chạy lại `python -m scripts.run_app` |
| Cảnh báo "symlinks" của huggingface trên Windows | Vô hại (tốn thêm chỗ đĩa); ẩn bằng biến `HF_HUB_DISABLE_SYMLINKS_WARNING=1` |
| Ollama báo quá thời gian chờ | Tăng `OLLAMA_TIMEOUT_S` hoặc dùng model nhỏ hơn; hoặc quay lại Gemini |
| PowerShell in log màu đỏ kèm `NativeCommandError` | Chỉ là log ghi ra stderr, không phải lỗi |

## 8. Giới hạn

- Chỉ xe mô tô/gắn máy và ô tô, 60 hành vi; hành vi khác nhận "không phát hiện vi phạm" kèm gợi ý tra cứu.
- Mức tăng/giảm tiền phạt khi có tình tiết là mức tham khảo của hệ thống: văn bản hướng dẫn chi tiết khoản 4 Điều 23
  Luật XLVPHC chưa có trong dữ liệu.
- Một số lỗi hội thoại đã biết (hỏi lặp khi lời kể không vi phạm, khoảng ngày "từ … đến …") — xem
  [evaluation/results/results.md](evaluation/results/results.md) và
  [docs/architecture.md](docs/architecture.md#10-giới-hạn-đã-biết).
