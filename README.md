# Hệ chuyên gia tư vấn vi phạm luật giao thông đường bộ

Đồ án môn Công nghệ tri thức. Hệ thống nhận mô tả tình huống bằng tiếng Việt, trích xuất sự kiện,
suy luận trên ontology OWL + luật SWRL (Pellet) để xác định hành vi vi phạm, điều khoản, khung phạt
và giải thích chuỗi suy luận. Căn cứ: NĐ 100/2019, NĐ 123/2021, NĐ 168/2024.

> Hướng dẫn đầy đủ sẽ được hoàn thiện ở Phase 9.

## Yêu cầu
- Python 3.11+ (đã thử với 3.13)
- Java 25+ (cho Pellet/HermiT — jar Jena đi kèm owlready2 0.51 biên dịch cho Java 25). Bản portable Temurin 25: https://adoptium.net

## Cài đặt nhanh (Windows)
```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # rồi điền ANTHROPIC_API_KEY, JAVA_EXE nếu cần
python -m scripts.check_env
pytest
```

## Cấu trúc
Xem mục 6 trong [CLAUDE.md](CLAUDE.md).
