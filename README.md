# Hệ chuyên gia tư vấn vi phạm luật giao thông đường bộ

Đồ án môn Công nghệ tri thức. Hệ thống nhận mô tả tình huống bằng tiếng Việt, trích xuất sự kiện,
suy luận trên ontology OWL + luật SWRL (HermiT) để xác định hành vi vi phạm, điều khoản, khung phạt
và giải thích chuỗi suy luận. Căn cứ: NĐ 100/2019, NĐ 123/2021, NĐ 168/2024, NĐ 238/2026 và các luật,
thông tư bổ trợ trong `data/raw/`.

> Hướng dẫn đầy đủ sẽ được hoàn thiện ở Phase 9.

## Yêu cầu
- Python 3.11+ (đã thử với 3.13)
- Java 25+ (cho HermiT/Pellet — jar Jena đi kèm owlready2 0.51 biên dịch cho Java 25).
  Bản portable Temurin 25: https://adoptium.net. Nếu giải nén vào `%USERPROFILE%\.jdks\`, hệ thống tự tìm thấy;
  hoặc đặt `JAVA_EXE` trong `.env`.

## Cài đặt nhanh (Windows)
```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # rồi điền GEMINI_API_KEY (xem mục dưới)
python -m scripts.check_env
python -m scripts.build_all  # sinh dữ liệu tri thức, ontology, luật (~6 giây)
pytest
```

## Cấu hình LLM

LLM chỉ dùng để hiểu ngôn ngữ (trích cụm từ, diễn đạt lại câu trả lời) — **không** quyết định điều khoản hay
mức phạt. Chọn provider bằng `LLM_PROVIDER` trong `.env`.

### Google Gemini (mặc định, gói miễn phí)
1. Mở **Google AI Studio**: https://aistudio.google.com/apikey và đăng nhập tài khoản Google.
2. Bấm **Create API key** (chọn hoặc tạo một Google Cloud project nếu được hỏi), sao chép key.
3. Trong `.env`:
   ```
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=<key vừa tạo>
   GEMINI_MODEL=gemini-3.5-flash-lite
   ```
4. Kiểm tra: `python -m scripts.check_llm --list` (liệt kê model Flash/Flash-Lite key dùng được),
   rồi `python -m scripts.check_llm` (gọi thử một request).

Lưu ý gói miễn phí:
- Có hạn mức số request mỗi phút/ngày theo từng model. Đặt `LLM_MAX_RPM` thấp hơn hạn mức; khi gặp lỗi 429,
  client tự chờ (theo `retryDelay` của máy chủ hoặc backoff lũy thừa) và thử lại tối đa `LLM_MAX_RETRIES` lần.
- Phản hồi được cache ở `.cache/llm/` (khóa = hash provider + model + prompt), chạy lại cùng câu hỏi không tốn request.
- Theo điều khoản của Google, dữ liệu gửi qua gói miễn phí có thể được dùng để cải thiện sản phẩm — không gửi
  thông tin cá nhân thật khi thử nghiệm; kiểm tra điều khoản hiện hành của Google.

### Ollama (dự phòng, chạy local)
1. Cài Ollama: https://ollama.com, rồi tải model: `ollama pull qwen2.5:7b`
2. Trong `.env`: `LLM_PROVIDER=ollama`, `OLLAMA_MODEL=qwen2.5:7b` (đổi model tùy máy).
3. Máy chỉ có CPU (không GPU rời) chạy model 7B rất chậm: một lần trích xuất có thể mất 1–3 phút. Tăng
   `OLLAMA_TIMEOUT_S` nếu bị báo quá thời gian chờ, hoặc dùng model nhỏ hơn (`ollama pull qwen2.5:3b`).
   `OLLAMA_KEEP_ALIVE` giữ model trong RAM giữa các lượt; JSON schema nằm trong system prompt (phần đầu cố định)
   để Ollama dùng lại phần prompt đã xử lý ở lần gọi trước.

### Lỗi thường gặp: sửa `.env` mà không có tác dụng
Biến môi trường của shell **ghi đè** `.env`. Nếu báo `LLM_PROVIDER='anthropic' không hỗ trợ` (hoặc giá trị cũ khác)
dù `.env` đã đúng: terminal còn giữ biến cũ — thường do VS Code bật `python.terminal.useEnvFile` (chép `.env` vào
terminal lúc mở). Xóa biến (`Remove-Item Env:LLM_PROVIDER` / `unset LLM_PROVIDER`) hoặc mở terminal mới;
nên để `"python.terminal.useEnvFile": false` vì ứng dụng tự đọc `.env`.

Structured output: Gemini dùng JSON schema mode; Ollama dùng `format: "json"`. Mọi phản hồi được validate bằng
Pydantic, sai schema thì gọi lại một lần kèm thông báo lỗi.

## Cấu trúc
Xem mục 6 trong [CLAUDE.md](CLAUDE.md). Thiết kế: [docs/ontology_design.md](docs/ontology_design.md),
[docs/rules_design.md](docs/rules_design.md).
