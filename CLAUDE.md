# CLAUDE.md — Hướng dẫn cho Claude Code trong project này

## Trạng thái hiện tại
- Phase 0: khởi tạo repo, môi trường, kiểm tra reasoner — XONG
- Phase 1: parser + hợp nhất V1/V2/V3 + đề xuất 60 hành vi MVP — XONG (đã thêm V4 = NĐ 238)
- Phase 2: ontology traffic_law.owl + docs/ontology_design.md — XONG
- Bổ sung sau Phase 2: hiệu lực tới cấp phần nội dung + có điều kiện (temporal.py), văn bản bổ trợ
  GTDB2008/LTTATGT(+L118)/TT31/TT38/LXLVPHC, 0 lệnh hợp nhất treo — XONG
- Phase 3: luật SWRL (303), rule_registry, sanctions, reasoner (HermiT), penalty — XONG (docs/rules_design.md)
- Phase 4: lớp LLM (Gemini chính + Ollama dự phòng; cache, retry 429, giới hạn RPM), normalizer, entity linker,
  synonyms.json, slot checker, llm_extractor, kiểm chứng cụm từ (grounding) — XONG
- Quyết định đã chốt: không rõ ngày vi phạm → `default_version: current` (phiên bản hiệu lực hôm nay, không cố định V3).
- Phase 5: fact_inducer (LLM suy ra sự kiện gián tiếp + kiểm tra tất định), fact_builder, pipeline đầu-cuối, CLI — XONG
- Phase 6: tracer, retriever (tra nguyên văn theo id + FAISS), verbalizer + kiểm tra chống bịa — XONG
- Phase 7: dialogue manager, FastAPI, giao diện Streamlit hai cột — ĐANG REVIEW
- Gốc project = thư mục `DoAn/` (tương ứng `traffic-law-expert/` trong đặc tả).
- Tên file dữ liệu thô: `data/raw/ND_100.docx`, `ND_123.docx`, `ND_168.docx`.

## Quy tắc nhanh (tóm tắt mục 2 bên dưới)
1. LLM KHÔNG quyết định điều khoản/mức phạt; chỉ trích xuất sự kiện và diễn đạt trace.
2. Mọi luật SWRL có mã R0xx khai trong `ontology/rule_registry.yaml`, truy về điều/khoản/điểm + trích nguyên văn.
3. Không lấy nội dung pháp luật từ trí nhớ; chỉ từ `data/raw/`. Không chắc → `TODO_VERIFY`.
4. Áp luật theo thời điểm vi phạm (V1/V2/V3, mở rộng V4 bằng cấu hình, không sửa code).
5. Thiếu trường quyết định → hỏi lại.
6. Hết mỗi phase: dừng, báo cáo, chờ duyệt. Commit theo phase.

## Lệnh thường dùng
- Kích hoạt venv: `.venv\Scripts\activate` (PowerShell) hoặc `source .venv/Scripts/activate` (Git Bash)
- Kiểm tra môi trường: `python -m scripts.check_env`; kiểm tra LLM: `python -m scripts.check_llm [--list]`
- Dựng chỉ mục RAG (bge-m3, lần đầu lâu trên CPU): `python -m src.explanation.retriever --build`;
  tra nguyên văn: `python -m src.explanation.retriever --id ND168-D7-K8-b --phien-ban V4`
- Giao diện web: `python -m scripts.run_app` (API :8000 + Streamlit :8501) hoặc `streamlit run app/streamlit_app.py`
  (tự chạy pipeline trong tiến trình nếu API chưa bật); API riêng: `uvicorn src.api.main:app --port 8000` (/docs)
- Chạy hệ thống từ CLI: `python -m scripts.chat` (hội thoại) hoặc `python -m scripts.chat -m "..." -m "..."`
  (tùy chọn `--ngay YYYY-MM-DD`, `--hom-nay`, `--khong-suy-ra`, `--khong-dien-dat`, `--json`, `--chi-tiet`)
- Test: `pytest`
- Sinh lại articles_v*.jsonl + consolidation_review.md: `python -m src.ingest.build_articles`
- Kiểm chứng + sinh bảng hành vi MVP: `python -m src.ingest.mvp_report` (→ docs/mvp_behaviors.md)
- Sinh ontology: `python -m src.kb.build_ontology` (→ ontology/traffic_law.owl, KHÔNG sửa tay file .owl)
- Bảng tốc độ TT 38: `python -m src.ingest.speed_limits` (→ data/processed/speed_limits.json)
- Sinh lại TOÀN BỘ đúng thứ tự: `python -m scripts.build_all`
  (build_articles → speed_limits → mvp_report → rules_builder → build_ontology → reasoning_kb)
- Suy luận một vụ việc: `from src.kb.reasoner import suy_luan; from src.kb.penalty import quyet_dinh`

## Dữ liệu pháp lý
- `config/legal_sources.yaml`: văn bản, phiên bản V1/V2/V3, ngoại lệ hiệu lực theo phần tử, văn bản chưa có (NĐ 238).
- `config/consolidation_overrides.yaml`: quyết định duyệt tay cho lệnh hợp nhất không tự áp được.
- `config/mvp_behaviors.yaml`: mã hành vi → id điều khoản từng phiên bản (+ cụm từ kiểm chứng); refs ngắn hơn số phiên bản thì phiên bản sau kế thừa id.
- `config/ontology_concepts.yaml`: ngưỡng pháp lý (lớp định nghĩa OWL, kèm evidence), lớp hợp, dấu hiệu sự kiện boolean.
- Phiên bản: V1 NĐ100, V2 NĐ100+123, V3 NĐ168, V4 NĐ168+238 (từ 15/8/2026). default_version: current.
- Văn bản bổ trợ (`supporting_documents`): GTDB2008, LTTATGT (+ L118 sửa → phiên bản LTTATGT_2025/_2026A/_2026B),
  TT31, TT38, LXLVPHC (bản hợp nhất, chú thích [n] → ngày hiệu lực câu chữ) → data/processed/support_<khóa>.jsonl.
  Chọn theo ngày vi phạm: `support_roles` + `temporal.chon_van_ban_bo_tro(vai_tro, ngay)`.
- Văn bản sửa đổi có lệnh hiệu lực khác ngày: phiên bản trung gian dùng `amendments: [{doc: X, only: [ref lệnh]}]`.
- Hiệu lực: `element_effectivity` (pham_vi toan_bo|mot_phan, hieu_luc_dieu_kien) → bản ghi có `hieu_luc_chi_tiet`;
  điều kiện chưa xác nhận ⇒ coi là CHƯA có hiệu lực. Đánh giá bằng `src/kb/temporal.trang_thai_hieu_luc`.
- Nguyên tắc hợp nhất: văn bản sửa chữ nào thì theo chữ đó (quyết định áp ở config/consolidation_overrides.yaml).
- Id phần tử: `ND168-D7-K10-a`; chữ `đ` viết `dd` trong id. V2 dùng id của NĐ 100 (văn bản gốc).
- Bản ghi JSONL có `status` (active|bai_bo), `history`, `history_inherited`, `khung_phat` (trích từ văn bản).

## Ghi chú kỹ thuật
- Reasoner chính là HermiT (Pellet 2.3.1 bỏ sót kết luận luật có lớp ngưỡng khi đủ bộ luật — test_pellet_limitation).
- HermiT không hỗ trợ SWRL built-in → ngưỡng số là lớp định nghĩa OWL (facet), luật SWRL chỉ nối lớp, KHÔNG dùng built-in.
- Truy vết luật qua lớp đánh dấu QT_<mã> (không bật infer_property_values — O(n²)); ontology suy luận gọn theo phiên bản
  ở ontology/reasoning/; reasoner chia lô 10 vụ việc.
- Luật sinh từ config/rule_specs.yaml (điều kiện) + config/mvp_behaviors.yaml (điều khoản); KHÔNG sửa tay .swrl/registry.
- HermiT không hỗ trợ xsd:date → mọi ngày lưu xsd:dateTime.
- YAML: không dùng khóa `on` (YAML 1.1 hiểu là True).
- owlready2 0.51 cần Java 25+ (jena-arq-fixed2.10.0.jar có class version 69). Máy dev: JDK portable tại `%USERPROFILE%/.jdks/jdk-25.0.5+8`, trỏ qua `JAVA_EXE` trong `.env`.
- owlready2 dùng `World()` riêng cho mỗi vụ việc để tránh lẫn cá thể giữa các phiên.

---

# Đặc tả gốc của đồ án


## 1. Bối cảnh

Tôi đang làm đồ án môn Công nghệ tri thức: **Hệ thống chuyên gia tư vấn hành vi vi phạm luật giao thông đường bộ dựa trên reasoning**. Hệ thống nhận mô tả hiện trường bằng tiếng Việt tự nhiên, rồi:

1. Trích xuất sự kiện từ câu hỏi và ánh xạ chính xác vào các node trên ontology (Bài toán 2).
2. Suy luận ngữ nghĩa bằng bộ suy luận OWL tiêu chuẩn kết hợp LLM để suy ra cả những hành vi vi phạm gián tiếp (Bài toán 1).
3. Tổng hợp tình tiết tăng nặng/giảm nhẹ, đưa ra hành vi vi phạm, điều khoản áp dụng, khung phạt, mức phạt đề xuất và hình thức xử phạt bổ sung.
4. Giải thích chuỗi suy luận: vì sao quy ra lỗi đó, vì sao áp điều khoản đó.

Sản phẩm cần có: giao diện chatbot tiếng Việt (hỗ trợ hội thoại nhiều lượt), cơ chế giải thích chuỗi suy luận, và báo cáo thử nghiệm hiệu năng.

## 2. Nguyên tắc thiết kế (BẮT BUỘC tuân thủ)

- **LLM không bao giờ tự quyết định điều khoản hay mức phạt.** LLM chỉ làm hai việc: (a) hiểu ngôn ngữ, trích xuất và suy ra sự kiện; (b) diễn đạt lại chuỗi suy luận đã có thành văn. Kết luận pháp lý phải do reasoner chạy trên ontology và luật SWRL đưa ra.
- **Mọi luật phải truy được về văn bản gốc.** Mỗi luật SWRL có một mã (R001, R002…). Mã này được khai báo trong `ontology/rule_registry.yaml` kèm: nghị định, điều, khoản, điểm, trích nguyên văn, ngày hiệu lực từ–đến.
- **Không lấy nội dung pháp luật từ trí nhớ của bạn (Claude).** Số điều/khoản/điểm, mức phạt và ngưỡng (nồng độ cồn, tốc độ…) phải được trích từ file trong `data/raw/`. Chỗ nào không tìm thấy hoặc không chắc thì đánh dấu `TODO_VERIFY` và liệt kê trong báo cáo cuối mỗi phase, không được đoán.
- **Luật áp dụng theo thời điểm vi phạm.** Hệ thống phải chọn đúng văn bản có hiệu lực tại thời điểm xảy ra vi phạm (xem mục 3).
- **Thiếu thông tin thì hỏi lại, không đoán.** Nếu thiếu một trường quyết định kết luận (loại xe, nồng độ đo được, loại đường…), chatbot phải đặt câu hỏi làm rõ.

## 3. Dữ liệu và mô hình thời gian

Tôi sẽ đặt trong `data/raw/` ba văn bản:

| Văn bản | Vai trò | Ghi chú hiệu lực (kiểm tra lại trong văn bản) |
|---|---|---|
| Nghị định 100/2019/NĐ-CP | Xử phạt VPHC giao thông đường bộ và đường sắt | Có hiệu lực từ 01/01/2020 |
| Nghị định 123/2021/NĐ-CP | Sửa đổi, bổ sung NĐ 100 (và các NĐ hàng hải, hàng không…) | Có hiệu lực từ 01/01/2022; chỉ lấy phần sửa NĐ 100 về đường bộ |
| Nghị định 168/2024/NĐ-CP | Xử phạt VPHC về trật tự, ATGT đường bộ; trừ điểm, phục hồi điểm GPLX | Có hiệu lực từ 01/01/2025; thay thế phần đường bộ của NĐ 100/123 |

Từ đó hệ thống có các "phiên bản pháp lý":

- **V1** (01/01/2020 – 31/12/2021): NĐ 100 nguyên bản
- **V2** (01/01/2022 – 31/12/2024): NĐ 100 đã hợp nhất với các sửa đổi của NĐ 123
- **V3** (từ 01/01/2025): NĐ 168

Yêu cầu:
- Viết parser tách văn bản thành cấu trúc phân cấp **Điều → Khoản → Điểm** (PDF/DOCX → JSONL). Mỗi phần tử có `id` dạng `ND168-D7-K10-a`, nội dung, văn bản nguồn, hiệu lực.
- NĐ 123 viết theo kiểu "Sửa đổi, bổ sung điểm a khoản 2 Điều 5 như sau: …". Hãy viết module hợp nhất bán tự động để sinh V2. Những chỗ không tự hợp nhất được thì xuất ra `data/processed/consolidation_review.md` cho tôi duyệt tay.
- Nếu thời điểm vi phạm không rõ, mặc định dùng V3 và ghi rõ điều đó trong câu trả lời.
- Lưu ý: NĐ 168 đã được sửa đổi bởi NĐ 238/2026/NĐ-CP (hiệu lực 15/8/2026). Tôi chưa đưa văn bản này vào. Hãy thiết kế để sau này chỉ cần thêm file và một phiên bản V4 là chạy được, không phải sửa code.
- Tình tiết tăng nặng/giảm nhẹ và cách chọn mức phạt trong khung nằm ở Luật Xử lý vi phạm hành chính, không nằm trong ba nghị định trên. Hãy mô hình hóa phần này trong `penalty_decision.swrl` và file cấu hình riêng, để căn cứ pháp lý dạng `TODO_VERIFY` cho tới khi tôi bổ sung văn bản luật.

## 4. Phạm vi (MVP)

Không số hóa toàn bộ nghị định. Trước hết chỉ làm **xe mô tô/xe gắn máy và ô tô**, khoảng **40–60 hành vi phổ biến**:
nồng độ cồn, chạy quá tốc độ, vượt đèn đỏ, đi ngược chiều, đi sai làn, không đội mũ bảo hiểm, dùng điện thoại khi lái xe, không chấp hành hiệu lệnh của người điều khiển giao thông, chống đối hoặc cản trở người thi hành công vụ, bỏ chạy, không có hoặc không mang GPLX/đăng ký/bảo hiểm, chưa đủ tuổi điều khiển xe, gây tai nạn rồi bỏ trốn.

Trước khi code, đề xuất danh sách hành vi cụ thể kèm điều khoản tương ứng ở cả V1/V2/V3 để tôi duyệt.

## 5. Công nghệ

- Python 3.11+, quản lý phụ thuộc bằng `uv` hoặc `pip` + `requirements.txt`
- Ontology: OWL 2, sửa được bằng Protégé; nạp bằng `owlready2`
- Reasoner: Pellet (qua owlready2, cần Java), HermiT để dự phòng
- Luật: SWRL
- LLM: lớp adapter dùng chung (`src/llm/client.py`), chọn provider qua `.env` (mặc định Anthropic Claude API). Dùng structured output/JSON schema với Pydantic
- Embedding cho entity linking: model đa ngữ hỗ trợ tiếng Việt (ví dụ `BAAI/bge-m3`), cấu hình được
- RAG: FAISS hoặc Chroma trên `articles.jsonl`
- Backend: FastAPI. Frontend: Streamlit
- Test: pytest

## 6. Cấu trúc project

```
traffic-law-expert/
├── README.md
├── CLAUDE.md
├── requirements.txt
├── .env.example
├── data/
│   ├── raw/                       # ND100, ND123, ND168 (tôi cung cấp)
│   ├── processed/
│   │   ├── articles_v1.jsonl
│   │   ├── articles_v2.jsonl
│   │   ├── articles_v3.jsonl
│   │   ├── consolidation_review.md
│   │   └── synonyms.json
│   └── test/
│       ├── scenarios.jsonl
│       └── annotation_guide.md
├── ontology/
│   ├── traffic_law.owl
│   ├── rules/
│   │   ├── alcohol.swrl
│   │   ├── speed.swrl
│   │   ├── signal.swrl
│   │   ├── resistance.swrl
│   │   ├── documents.swrl
│   │   └── penalty_decision.swrl
│   └── rule_registry.yaml
├── src/
│   ├── ingest/        # parser.py, consolidate.py, build_articles.py
│   ├── kb/            # loader.py, reasoner.py, temporal.py
│   ├── llm/           # client.py, prompts/
│   ├── extraction/    # schema.py, llm_extractor.py, normalizer.py, entity_linker.py, slot_checker.py
│   ├── inference/     # fact_inducer.py, fact_builder.py, pipeline.py
│   ├── explanation/   # tracer.py, retriever.py, verbalizer.py
│   ├── dialogue/      # manager.py
│   └── api/           # main.py
├── app/streamlit_app.py
├── evaluation/        # run_eval.py, baseline_llm_only.py, ablation.py, metrics.py, results/
├── tests/
├── notebooks/
└── docs/              # architecture.md, ontology_design.md, report/
```

## 7. Thiết kế ontology

Các lớp chính (tên tiếng Việt không dấu, CamelCase):
- `PhuongTien` → `XeMoTo`, `XeGanMay`, `OTo`, `XeTai`, … (theo cách phân loại trong nghị định)
- `NguoiDieuKhien`, `VuViec`, `HanhViViPham` (phân cấp theo nhóm), `TinhTiet` → `TinhTietTangNang`, `TinhTietGiamNhe`
- `VanBan` → `NghiDinh`; `DieuKhoan` → `Dieu`, `Khoan`, `Diem`; `PhienBanPhapLy` (V1/V2/V3)
- `KhungPhat` (mucToiThieu, mucToiDa), `HinhThucBoSung` → `TuocGPLX`, `TruDiemGPLX`, `TamGiuPhuongTien`, …
- `LoaiDuong` → `KhuDanCu`, `NgoaiKhuDanCu`, `CaoToc`, …
- `QuyTac` (mỗi luật SWRL là một cá thể của lớp này)

Thuộc tính tiêu biểu: `nongDoConKhiTho` (mg/L), `nongDoConMau` (mg/100mL), `tocDoThucTe`, `tocDoToiDaChoPhep`, `thoiDiemViPham`, `dieuKhien`, `viPhamHanhVi`, `apDungDieuKhoan`, `coKhungPhat`, `coTinhTiet`, **`duocSuyRaBoi`** (trỏ tới cá thể `QuyTac`).

**Mẹo giải thích (bắt buộc):** mỗi luật SWRL, ngoài kết luận chính, phải gán thêm `duocSuyRaBoi(?vipham, R0xx)`. Sau khi reasoner chạy, `tracer.py` đi ngược các quan hệ này để dựng chuỗi: sự kiện đầu vào → quy tắc → hành vi → điều khoản → khung phạt → mức đề xuất.

## 8. Pipeline xử lý một câu hỏi

1. `dialogue/manager.py` nhận tin nhắn và cập nhật "hồ sơ vụ việc" (Pydantic) qua nhiều lượt.
2. `llm_extractor.py` trích các trường theo schema. `normalizer.py` chuẩn hóa số và đơn vị ("80 cây", "0.3 miligam", "nửa đêm"…). `entity_linker.py` ánh xạ vào node ontology (từ điển đồng nghĩa trước, embedding sau, có ngưỡng tin cậy).
3. `slot_checker.py`: nếu thiếu trường quyết định thì sinh câu hỏi làm rõ và dừng tại đây.
4. `fact_inducer.py`: LLM suy ra sự kiện gián tiếp kèm độ tin cậy và câu trích làm bằng chứng. Ví dụ "thấy CSGT vẫy thì rồ ga chạy" → `coHieuLenhDung`, `khongChapHanh`, `boChay`. Sự kiện có độ tin cậy thấp thì hỏi lại người dùng để xác nhận.
5. `fact_builder.py` tạo cá thể trong ontology. `temporal.py` chọn phiên bản pháp lý. `reasoner.py` chạy Pellet.
6. `penalty_decision`: gộp các lỗi, áp tình tiết, đề xuất mức phạt trong khung.
7. `tracer.py` + `retriever.py` lấy chuỗi suy luận và nguyên văn điều khoản. `verbalizer.py` để LLM viết câu trả lời **chỉ từ trace**. Sau đó kiểm tra lại: mọi mã điều khoản xuất hiện trong câu trả lời đều phải có trong trace.

Định dạng câu trả lời: hành vi vi phạm → căn cứ (văn bản, điều, khoản, điểm, trích dẫn) → khung phạt → mức đề xuất và lý do → hình thức bổ sung/trừ điểm → chuỗi suy luận → lưu ý (giả định đã dùng, thông tin còn thiếu, kết quả chỉ mang tính tham khảo).

## 9. Giao diện

Streamlit có hai cột. Cột trái là khung chat. Cột phải gồm: bảng sự kiện đã trích (người dùng sửa được rồi chạy lại), cây suy luận (graphviz hoặc streamlit-agraph), và nguyên văn điều khoản. Có một ô chọn ngày vi phạm.

## 10. Đánh giá

- `data/test/scenarios.jsonl`: 200–300 tình huống, mỗi tình huống có nhãn chuẩn (hành vi, id điều khoản, khung phạt, hình thức bổ sung, phiên bản pháp lý). Chia nhóm: đơn lỗi, đa lỗi, gián tiếp, thiếu thông tin, khác thời điểm (cùng hành vi nhưng V2 và V3 cho kết quả khác nhau), gài bẫy/không vi phạm. Bạn sinh trước khoảng 50 tình huống mẫu kèm `annotation_guide.md`, tôi sẽ duyệt và bổ sung.
- Metric: F1 từng trường trích xuất; accuracy ánh xạ node; precision/recall/F1 phát hiện hành vi; accuracy điều khoản (khớp tới điểm); accuracy khung phạt; tỉ lệ hỏi lại đúng lúc; tỉ lệ dẫn sai luật hoặc dẫn luật hết hiệu lực; latency trung bình và p95.
- Baseline: LLM trả lời trực tiếp, không có ontology. Ablation: bỏ normalizer, bỏ entity linker, bỏ fact_inducer.
- Xuất bảng và biểu đồ vào `evaluation/results/`, kèm `results.md` tóm tắt và phân tích lỗi theo tầng.

## 11. Cách làm việc

Làm theo từng phase. **Hết mỗi phase thì dừng lại**, báo cáo ngắn: đã làm gì, cách chạy thử, danh sách `TODO_VERIFY`, rồi chờ tôi duyệt.

- **Phase 0** — Khởi tạo repo, cấu trúc thư mục, `requirements.txt`, `.env.example`, `CLAUDE.md`, kiểm tra Java + owlready2 + Pellet chạy được với một ontology đồ chơi.
- **Phase 1** — Parser + hợp nhất V1/V2/V3 → `articles_v*.jsonl`, `consolidation_review.md`. Đề xuất danh sách 40–60 hành vi MVP kèm điều khoản ở từng phiên bản.
- **Phase 2** — Ontology `traffic_law.owl` + `docs/ontology_design.md`.
- **Phase 3** — Luật SWRL + `rule_registry.yaml` + reasoner + temporal. Unit test cho từng luật (nhập sự kiện bằng tay → kỳ vọng đúng điều khoản).
- **Phase 4** — Extraction: schema, extractor, normalizer, entity linker, slot checker + test.
- **Phase 5** — Fact inducer + pipeline đầu-cuối chạy được từ CLI.
- **Phase 6** — Explanation: tracer, RAG, verbalizer, kiểm tra chống bịa điều khoản.
- **Phase 7** — FastAPI + Streamlit + dialogue manager nhiều lượt.
- **Phase 8** — Bộ test, đánh giá, baseline, ablation, `results.md`.
- **Phase 9** — `README.md` hướng dẫn cài và chạy, `docs/architecture.md` có sơ đồ (Mermaid).

Quy ước code: type hints, docstring tiếng Việt, log rõ ràng, không hard-code API key, prompt LLM để trong `src/llm/prompts/` dạng file riêng có version. Commit theo từng phase.

Bắt đầu với **Phase 0**.

## LLM (Phase 4)
- KHÔNG dùng Anthropic. Provider: `gemini` (GEMINI_API_KEY, GEMINI_MODEL) | `ollama` (OLLAMA_BASE_URL, OLLAMA_MODEL).
- Interface: `get_llm_client().generate(...)` / `.generate_structured(prompt, PydanticModel, system=...)`.
- Prompt có version: `src/llm/prompts/<id>_v<n>.md` (front-matter + `## system` / `## user`), nạp bằng `load_prompt`.
- LLM chỉ chép cụm từ bề mặt (TrichXuatLLM); chuẩn hóa/ánh xạ là tất định (normalizer, entity_linker, synonyms.json);
  sự kiện kéo theo của node lấy từ ontology_concepts.yaml; phân loại xe máy theo dung tích ở config/phan_loai_xe.yaml
  (khác nhau giữa Luật GTĐB 2008 "dưới 50 cm3" và Luật TTATGT "không lớn hơn 50 cm3").
- Kiểm chứng cụm từ (`src/extraction/grounding.py`): sau LLM, bỏ mọi cụm không có trong lời người dùng (so khớp
  bỏ dấu, số viết bằng chữ quy ra chữ số); chỗ bị bỏ ghi vào `HoSoVuViec.cum_tu_loai_bo`. Chỉ đối chiếu tin nhắn
  người dùng, không đối chiếu câu hỏi hệ thống. Tắt cho ablation: `LLMExtractor(kiem_chung_cum_tu=False)`.
- Ollama trên máy dev chạy CPU (~50 s/lần trích xuất với qwen2.5:7b): timeout riêng `OLLAMA_TIMEOUT_S`, không retry
  khi hết giờ; schema đặt trong system prompt để tái dùng KV-cache. Không dùng Ollama cho đánh giá hàng loạt.

## Pipeline (Phase 5)
- `src/inference/pipeline.py`: `Pipeline.xu_ly(PhienLamViec, tin_nhan, ngay_vi_pham=None)` → `KetQuaLuot`
  (can_hoi | ket_luan | khong_phat_hien). Trạng thái nhiều lượt trong `PhienLamViec` (hồ sơ Pydantic + lời kể + câu hỏi vừa hỏi).
- fact_inducer: danh mục thuộc tính = thuộc tính boolean của ontology (HanhViDieuKhienXe/HanhVi), lấy tự động;
  ngưỡng/ngoại lệ ở `config/fact_inducer.yaml`; bằng chứng phải có trong lời người dùng; sự kiện trực tiếp luôn thắng.
  Định nghĩa pháp lý đính kèm prompt lấy NGUYÊN VĂN theo ngày (support_roles `dinh_nghia_nguoi_dieu_khien_gt`).
- Xác nhận: mọi mục chờ xác nhận gộp thành MỘT câu hỏi (`xac_nhan`), hỏi riêng một lượt; "có/không" áp cho đúng các mục đó.
- Tốc độ tối đa khi không có biển: `src/kb/toc_do.py` (dùng chung cho slot_checker và fact_builder).
- Ngưỡng embedding entity linker 0.80 (đo bằng `python -m evaluation.calib_entity_link`; 0.65 cho nhiều liên kết sai).
- `src/inference/report.py`: trình bày tất định (Phase 6 thay bằng verbalizer có kiểm tra chống bịa).

## Giải thích (Phase 6)
- `src/explanation/tracer.py`: `dung_trace(KetQuaLuot)` → `Trace` — đi ngược thân luật SWRL (registry) qua lớp ngưỡng /
  hợp / dấu hiệu (ontology_concepts.yaml) tới sự kiện đầu vào + nguồn; bằng chứng ngưỡng ưu tiên chính điều khoản kết
  luận. Nhãn lớp được `sach()` bỏ ghi chú kỹ thuật trong ngoặc (tránh dẫn nhầm "NĐ 100" cho vụ V4).
  `Trace.can_cu_hop_le()/so_tien_hop_le()/ma_quy_tac()` = danh sách được phép xuất hiện trong câu trả lời; `do_thi()` cho UI.
- `src/explanation/retriever.py`: `lay(id, phien_ban, ngay)` tất định (đường chính để dẫn chứng); `Retriever.tim()` FAISS
  chỉ để GỢI Ý "quy định có thể liên quan" khi không phát hiện vi phạm (hành vi ngoài MVP) — không phải kết luận.
  Vector cache theo hash nội dung ở `data/index/` (gitignored); chỉ nhúng nội dung khoản/điểm.
- `src/explanation/verbalizer.py`: LLM viết từ `trace_cho_llm(trace)` (prompt `verbalize_v1`); `kiem_tra()` đối chiếu
  tham chiếu điều khoản, văn bản (chặn văn bản không thuộc phiên bản), số tiền, số điểm, số tháng, mã R…, độ đầy đủ;
  sai → thử lại 1 lần kèm lỗi → vẫn sai/LLM lỗi → bản tất định (`report.trinh_bay`).
- Hành vi kể ra nhưng không ánh xạ được (ngoài MVP) không bị hỏi lại "mô tả hành vi" — trả "không phát hiện" + gợi ý.

## Hội thoại, API, giao diện (Phase 7)
- `src/dialogue/manager.py`: `DialogueManager` — phiên trong bộ nhớ (TTL 180 phút), `gui()` (lệnh `/moi`), `sua_ho_so()`
  (sửa bảng sự kiện → `Pipeline.chay_lai`, KHÔNG gọi LLM trích xuất; nguồn `nguoi_dung_sua` thắng sự kiện LLM suy ra),
  `dat_ngay()`. Một khóa chung bao lượt xử lý (owlready2/Java không an toàn song song).
- `src/dialogue/serialize.py`: `ket_qua_json(KetQuaLuot)` dùng chung cho API, giao diện, CLI `--json`.
- `src/api/main.py`: /suc-khoe, /danh-muc, /phien (POST/GET/DELETE), /phien/{id}/tin-nhan, PATCH /phien/{id}/ho-so,
  PUT /phien/{id}/ngay, POST /phien/{id}/moi, /dieu-khoan/{id}. Lỗi: 404 phiên, 422 dữ liệu, 503 LLM.
- `app/streamlit_app.py`: APP_BACKEND=auto|api|truc_tiep; tab Sự kiện (form + data_editor), Cây suy luận (Graphviz
  từ `Trace.do_thi()`), Điều khoản (nguyên văn theo phiên bản), Chi tiết. Test bằng `streamlit.testing.v1.AppTest`.
