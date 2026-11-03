# Thiết kế ontology `traffic_law.owl`

Tài liệu mô tả ontology OWL 2 của hệ chuyên gia tư vấn vi phạm giao thông đường bộ: phạm vi, cấu trúc
lớp và thuộc tính, cách mô hình hóa một vụ việc, cách gắn kết với văn bản pháp luật theo phiên bản,
và các quyết định thiết kế.

## 1. Nguyên tắc

| Nguyên tắc | Cách thực hiện |
|---|---|
| Kết luận pháp lý do reasoner đưa ra | Ngưỡng định lượng là **lớp định nghĩa OWL** (ràng buộc kiểu dữ liệu); luật SWRL (Phase 3) chỉ nối các lớp đó với điều khoản. |
| Truy được về văn bản gốc | Mỗi ngưỡng có annotation `canCuPhapLy` = id phần tử + cụm từ nguyên văn; test `test_threshold_evidence_in_source` kiểm tra cụm từ có thật trong văn bản. Mỗi cá thể điều khoản giữ `noiDung` nguyên văn. |
| Không lấy luật từ trí nhớ | Mọi số liệu (ngưỡng, khung phạt) sinh từ `config/*.yaml` + `data/processed/articles_v*.jsonl`. |
| Áp luật theo thời điểm | Cá thể điều khoản gắn **theo phiên bản** (`V3_ND168-D6-K9-a`); vụ việc có `apDungPhienBan`. |
| Chạy được cả Pellet và HermiT | Không dùng SWRL built-in; ngày dùng `xsd:dateTime` (HermiT không hỗ trợ `xsd:date`). |

## 2. Sinh và chỉnh sửa

```text
config/legal_sources.yaml   ─┐
config/mvp_behaviors.yaml   ─┤
config/ontology_concepts.yaml┼─► python -m src.kb.build_ontology ─► ontology/traffic_law.owl (RDF/XML)
data/processed/articles_v*.jsonl┘
```

* File `.owl` là **sản phẩm sinh ra**. Mở bằng Protégé để xem, kiểm tra, chạy reasoner thử; muốn sửa thì
  sửa file cấu hình (hoặc phần TBox trong `src/kb/build_ontology.py`) rồi sinh lại, để không mất
  liên kết truy vết tới văn bản.
* Nạp trong code: `from src.kb.loader import load_world; world, onto = load_world()` — mỗi vụ việc dùng
  một `World` riêng.
* IRI gốc: `http://www.semanticweb.org/traffic-law-vn/ontology#`.

Số liệu hiện tại: **192 lớp** (64 lớp lõi, 27 lớp ngưỡng/hợp, 27 lớp dấu hiệu sự kiện, 14 nhóm vi phạm,
60 lớp hành vi `HV_*`), **25 thuộc tính đối tượng, 58 thuộc tính dữ liệu, 3 annotation**,
**363 cá thể điều khoản** (26 Điều, 126 Khoản, 211 Điểm, tính theo 4 phiên bản), **132 khung phạt**.

## 3. Cấu trúc lớp

```mermaid
flowchart LR
  Thing --> PhuongTien & Nguoi & LoaiDuong & VuViec & HanhVi & TinhTiet
  Thing --> VanBan & PhienBanPhapLy & DieuKhoan & KhungPhat & HinhThucXuPhat & BienPhapKhac & QuyTac

  PhuongTien --> XeCoGioi & XeThoSo
  XeCoGioi --> NhomXeOTo & NhomXeMoTo & XeMayChuyenDung
  NhomXeOTo --> OTo & XeChoNguoiBonBanhCoGanDongCo & XeChoHangBonBanhCoGanDongCo & XeTuongTuOTo
  OTo --> XeOToTai & XeOToChoNguoi
  NhomXeMoTo --> XeMoTo & XeGanMay & XeTuongTuXeMoTo & XeTuongTuXeGanMay
  XeMoTo --> XeMoToHaiBanh & XeMoToBaBanh
  XeGanMay --> XeMayDien
  XeThoSo --> XeDap & XeDapMay
  XeDapMay --> XeDapDien

  Nguoi --> NguoiDieuKhien & ChuXe & NguoiThiHanhCongVu & NguoiKhongDuDieuKienDieuKhienXe
  LoaiDuong --> DuongCaoToc & DuongMotChieu & KhuDanCu & NgoaiKhuDanCu

  HanhVi --> HanhViDieuKhienXe & HanhViGiaoXe & HanhViViPham
  HanhVi --> DauHieuSuKien & MucNongDoCon & MucVuotTocDo
  HanhViViPham --> ViPhamNongDoCon & ViPhamTocDo & ViPhamTinHieuHieuLenh & VPx["…14 nhóm"]
  ViPhamNongDoCon --> HV_OT_CON_1 & HV_XM_CON_2 & HVx["…60 lớp HV_*"]

  TinhTiet --> TinhTietTangNang & TinhTietGiamNhe
  VanBan --> NghiDinh
  DieuKhoan --> Dieu & Khoan & Diem
  HinhThucXuPhat --> PhatCanhCao & HinhThucBoSung
  HinhThucBoSung --> TuocGPLX & TichThuPhuongTien & TichThuTangVat
  BienPhapKhac --> TruDiemGPLX & TamGiuPhuongTien & BienPhapKhacPhucHauQua
```

Ràng buộc rời nhau (`AllDisjoint`):

* `NhomXeOTo`, `NhomXeMoTo`, `XeMayChuyenDung` rời nhau; `XeCoGioi` rời `XeThoSo` — nên khai báo một
  chiếc **xe đạp điện** là thuộc `NhomXeMoTo` sẽ làm ontology **mâu thuẫn** (dùng cho tình huống bẫy:
  xe đạp điện không áp lỗi của xe máy).
* `Dieu`/`Khoan`/`Diem`; `KhuDanCu`/`NgoaiKhuDanCu`; `TinhTietTangNang`/`TinhTietGiamNhe`; và các lớp
  gốc lớn (phương tiện, người, văn bản, …) đôi một rời nhau.

Phân nhóm phương tiện theo đối tượng điều chỉnh của các Điều: `NhomXeOTo` ≈ Điều 5 NĐ 100 / Điều 6 NĐ 168;
`NhomXeMoTo` ≈ Điều 6 NĐ 100 / Điều 7 NĐ 168 ("kể cả xe máy điện"). Xe máy điện là xe gắn máy, xe đạp máy
là xe thô sơ (điểm d, e khoản 1 Điều 3 NĐ 100).

## 4. Thuộc tính

### 4.1. Thuộc tính đối tượng

| Thuộc tính | Miền → Giá trị | Ghi chú |
|---|---|---|
| `coHanhVi` / `thuocVuViec` | VuViec ↔ HanhVi | nghịch đảo nhau; `thuocVuViec` hàm |
| `chuThe` | HanhVi → Nguoi | người thực hiện hành vi |
| `suDungPhuongTien` | HanhVi → PhuongTien | |
| `dieuKhien`, `laChuSoHuu` | Nguoi → PhuongTien | |
| `giaoXeCho` | HanhViGiaoXe → Nguoi | dùng cho lỗi của chủ xe |
| `trenLoaiDuong` | HanhVi → LoaiDuong | |
| `apDungPhienBan` | VuViec → PhienBanPhapLy | do `temporal.py` gán |
| `viPhamHanhVi` | Nguoi → HanhViViPham | luật SWRL gán |
| `apDungDieuKhoan` | HanhVi → DieuKhoan | luật SWRL gán |
| `duocSuyRaBoi` | * → QuyTac | **truy vết**: luật nào sinh ra kết luận |
| `coTinhTiet` | * → TinhTiet | |
| `thuocDieuKhoanCha` ⊑ `thuocDieuKhoan` | DieuKhoan → DieuKhoan | `thuocDieuKhoan` bắc cầu (điểm → khoản → điều) |
| `thuocVanBan`, `duocSuaDoiBoi`, `thuocPhienBan`, `gomVanBan` | | cấu trúc văn bản |
| `coKhungPhat` | DieuKhoan → KhungPhat | chuỗi: `thuocDieuKhoanCha ∘ coKhungPhat ⊑ coKhungPhat` |
| `chiuKhungPhat` | HanhVi → KhungPhat | chuỗi: `apDungDieuKhoan ∘ coKhungPhat ⊑ chiuKhungPhat` |
| `coHinhThucBoSung`, `coBienPhapKhac` | → HinhThucXuPhat / BienPhapKhac | Phase 3 |
| `canCuDieuKhoan`, `apDungChoPhienBan` | QuyTac → DieuKhoan / PhienBanPhapLy | Phase 3 |

Hai **chuỗi thuộc tính (property chain)** cho phép reasoner tự suy ra: điểm a khoản 9 thuộc khoản 9 có
khung phạt 18–20 triệu ⇒ điểm a có khung phạt đó ⇒ hành vi áp dụng điểm a chịu khung phạt đó.

### 4.2. Thuộc tính dữ liệu (sự kiện của vụ việc)

* Số: `nongDoConKhiTho` (mg/L), `nongDoConMau` (mg/100 mL), `tocDoThucTe`, `tocDoToiDaChoPhep`,
  `tocDoVuot` (km/h), `tuoi`, `dungTichXiLanh` (cm3), `congSuatDongCoDien` (kW), `thoiDiemViPham`.
* Boolean trên `HanhViDieuKhienXe` (29 thuộc tính), vd. `khongChapHanhDenTinHieu`, `coHieuLenhNguoiDieuKhienGT`,
  `chapHanhHieuLenh`, `coHieuLenhDungXe`, `boChay`, `doiMuBaoHiem`, `coGPLX`, `mangTheoGPLX`, `kinhDoanhVanTai`…
* Văn bản/điều khoản: `maDieuKhoan`, `trichDan`, `noiDung`, `trangThai`, `hieuLucTu`, `hieuLucDen`,
  `hieuLucChuaXacDinh`; khung phạt: `mucToiThieu`, `mucToiDa`, `doiTuongApDung`.

## 5. Khái niệm định nghĩa (OWL reasoner tự phân loại)

### 5.1. Ngưỡng pháp lý — `config/ontology_concepts.yaml › thresholds`

Mỗi lớp = `<lớp miền> ⊓ ∃<thuộc tính>.<kiểu dữ liệu>[facet]`, kèm căn cứ:

| Lớp | Định nghĩa | Căn cứ (ví dụ) |
|---|---|---|
| `NongDoConKhiThoMuc1/2/3` | (0; 0,25] · (0,25; 0,4] · > 0,4 mg/L | V3 `ND168-D6-K6-c`, `-K9-a`, `-K11-a` |
| `NongDoConMauMuc1/2/3` | (0; 50] · (50; 80] · > 80 mg/100 mL | như trên |
| `NongDoConMuc1/2/3` | hợp "máu **hoặc** hơi thở" | |
| `VuotTocDo05Den10` | [5; 10) km/h | "từ 05 km/h đến dưới 10 km/h" |
| `VuotTocDo10Den20` | [10; 20] | "từ 10 km/h đến 20 km/h" |
| `VuotTocDoTren20Den35`, `VuotTocDoTren35` | (20; 35] · > 35 (ô tô) | |
| `VuotTocDoTren20` | > 20 (xe máy) — reasoner tự suy ra `VuotTocDoTren20Den35 ⊑ VuotTocDoTren20` | |
| `NguoiTu14Den16Tuoi`, `NguoiTu16Den18Tuoi` | [14; 16) · [16; 18) | `ND168-D18-K1`, `-K6` |
| `DungTichDuoi175cm3`, `DungTichTu175cm3` | phân hạng NĐ 100 | `ND100-D21-K5`, `-K7` |
| `DungTichDen125cm3`, `CongSuatDen11kW`, `XeMoToHangNhoND168` … | phân hạng NĐ 168 | `ND168-D18-K5`, `-K7` |
| `DungTichTu50cm3`, `CongSuatTu4kW`, `XeMoToTu50cm3Hoac4kW` | | `ND100-D21-K4-a`, `ND168-D18-K4-a` |

Biên được kiểm tra trong test: 0,25 mg/L → mức 1; 4 km/h → không thuộc mức nào; 10 và 20 km/h → `VuotTocDo10Den20`;
18 tuổi → không thuộc nhóm 16–18.

### 5.2. Dấu hiệu sự kiện — `observations`

Lớp ghép từ giá trị boolean (và ràng buộc lớp), vd.

* `KhongChapHanhHieuLenhNguoiDieuKhienGT ≡ HanhViDieuKhienXe ⊓ coHieuLenhNguoiDieuKhienGT = true ⊓ chapHanhHieuLenh = false`
* `DiNguocChieuTrenCaoToc ≡ HanhViDieuKhienXe ⊓ diNguocChieu = true ⊓ ∃trenLoaiDuong.DuongCaoToc`
* `KhongMangTheoGPLX ≡ HanhViDieuKhienXe ⊓ coGPLX = true ⊓ mangTheoGPLX = false`

## 6. Mô hình hóa một vụ việc (ABox)

Ví dụ: *"Tối 10/3/2025 tôi uống bia rồi chạy xe máy, thấy CSGT vẫy thì rồ ga chạy; đo được 0,3 mg/L."*

```mermaid
flowchart LR
  vv[vv1: VuViec<br/>thoiDiemViPham=2025-03-10T21:00<br/>apDungPhienBan=V3]
  h[h1: HanhViDieuKhienXe<br/>nongDoConKhiTho=0.3<br/>coHieuLenhNguoiDieuKhienGT=true<br/>chapHanhHieuLenh=false<br/>boChay=true]
  n[n1: NguoiDieuKhien]
  x[x1: XeMoToHaiBanh]
  vv -- coHanhVi --> h
  h -- chuThe --> n
  h -- suDungPhuongTien --> x
  h -. OWL suy ra .-> c1[NongDoConMuc2]
  h -. OWL suy ra .-> c2[KhongChapHanhHieuLenhNguoiDieuKhienGT]
  h -. SWRL Phase 3 .-> hv[HV_XM_CON_2<br/>apDungDieuKhoan V3_ND168-D7-K8-b<br/>duocSuyRaBoi R0xx]
  hv -. property chain .-> kp[chiuKhungPhat KP_V3_ND168-D7-K8]
```

* `fact_builder` tạo cá thể; các sự kiện *gián tiếp* (`coHieuLenhNguoiDieuKhienGT`, `boChay`) do `fact_inducer`
  suy ra kèm độ tin cậy.
* `tocDoVuot` do `fact_builder` tính (`tocDoThucTe − tocDoToiDaChoPhep`) vì OWL không có phép trừ — đây là phép
  tính số học, không phải kết luận pháp lý.
* Lỗi của **chủ xe** là một cá thể `HanhViGiaoXe` riêng (`chuThe` = chủ xe, `giaoXeCho` = người lái). Phase 3
  sẽ suy ra `NguoiKhongDuDieuKienDieuKhienXe` từ chính vi phạm của người lái (chưa đủ tuổi, không có GPLX) rồi
  mới kết luận lỗi giao xe — một chuỗi suy luận gián tiếp hai bước.

## 7. Điều khoản theo phiên bản

* Cá thể `V{n}_{id}` thuộc `Dieu`/`Khoan`/`Diem`, có `thuocPhienBan`, `thuocVanBan` (văn bản gốc của id),
  `duocSuaDoiBoi` (NĐ 123 ở V2, NĐ 238 ở V4 nếu phần tử bị sửa), `noiDung`, `trichDan`, `hieuLucTu/Den`.
* Cùng một id ở hai phiên bản là **hai cá thể khác nhau** (vd. `V1_ND100-D5-K4` 1–2 triệu, `V2_ND100-D5-K4` 2–3 triệu).
* Chỉ nạp các phần tử được hành vi MVP hoặc ngưỡng dẫn tới, cùng khoản/điều cha (để reasoner nhanh); nguyên
  văn đầy đủ vẫn ở `articles_v*.jsonl` cho RAG.
* Khung phạt `KP_V3_ND168-D6-K9` gắn vào khoản; nếu khoản có mức riêng cho tổ chức thì có thêm `KP_TC_…`.

## 8. Định hướng cho luật SWRL (Phase 3)

Luật **không dùng built-in**, chỉ nối lớp đã phân loại với phiên bản và điều khoản:

```text
HanhViDieuKhienXe(?h) ∧ suDungPhuongTien(?h, ?x) ∧ NhomXeMoTo(?x) ∧ NongDoConMuc2(?h)
  ∧ thuocVuViec(?h, ?v) ∧ apDungPhienBan(?v, V3)
  → HV_XM_CON_2(?h) ∧ apDungDieuKhoan(?h, V3_ND168-D7-K8-b) ∧ duocSuyRaBoi(?h, R0xx)
```

Cá thể `R0xx` (lớp `QuyTac`) mang `ketLuanMaHanhVi`, `canCuDieuKhoan`, `apDungChoPhienBan`, nên `tracer.py`
dựng lại được chuỗi: sự kiện → lớp định nghĩa → quy tắc → hành vi → điều khoản → khung phạt.

## 9. Quyết định thiết kế và đánh đổi

1. **Giả định thế giới mở (OWA).** OWL không suy ra "không mang GPLX" từ việc thiếu thông tin. Vì vậy sự kiện
   phủ định được ghi tường minh bằng boolean (`mangTheoGPLX = false`), và `slot_checker` phải hỏi lại khi
   trường quyết định chưa có giá trị. Đây cũng là cơ chế "thiếu thông tin thì hỏi lại".
2. **Hành vi vi phạm là lớp, hành vi thực tế là cá thể.** Một lượt điều khiển xe có thể thuộc nhiều lớp
   `HV_*` (vừa có cồn vừa quá tốc độ); quan hệ hành vi ↔ điều khoản đi qua cá thể quy tắc nên không bị nhập nhằng.
3. **Tên lớp hành vi `HV_<mã>`** dùng đúng mã trong `config/mvp_behaviors.yaml` (ổn định xuyên suốt registry,
   test, đánh giá) thay vì CamelCase tự đặt; nhãn tiếng Việt nằm ở `rdfs:label`.
4. **Ngày dạng `xsd:dateTime`** để HermiT (dự phòng) chạy được.
5. **Ngưỡng dùng chung cho mọi phiên bản** vì 4 phiên bản dùng cùng ranh giới (đã đối chiếu V1 và V3 trong
   evidence). Phân hạng xe khác nhau giữa NĐ 100 (175 cm3) và NĐ 168 (125 cm3/11 kW) được tách thành lớp riêng;
   luật của từng phiên bản chọn lớp phù hợp.
6. Phiên bản V4 (NĐ 238) **bỏ ngưỡng 50 cm3** ở điểm a khoản 4 Điều 18 (người 16–18 tuổi đi mô tô): luật V4 sẽ
   không dùng `XeMoToTu50cm3Hoac4kW` cho hành vi này.

## 10. TODO_VERIFY

* `NguoiKhongDuDieuKienDieuKhienXe`: điều kiện đầy đủ nằm ở Luật Giao thông đường bộ / Luật Trật tự, an toàn
  giao thông đường bộ (được dẫn trong khoản 5 Điều 30 NĐ 100, khoản 10 Điều 32 NĐ 168) — chưa có trong `data/raw/`.
  Phase 3 chỉ suy ra lớp này từ các vi phạm về tuổi và GPLX có trong nghị định.
* Tốc độ tối đa cho phép theo loại đường không có trong 4 nghị định; hệ thống yêu cầu người dùng cung cấp
  (biển báo) hoặc hỏi lại.
* `TinhTietTangNang` / `TinhTietGiamNhe` mới có lớp, chưa có cá thể — căn cứ ở Luật Xử lý vi phạm hành chính
  (chưa có trong `data/raw/`).
