# Ví dụ: xử lý hiệu lực tới cấp phần nội dung và hiệu lực có điều kiện

*Mục dùng cho báo cáo đồ án. Các quy định trong ví dụ thuộc nhóm xe kinh doanh vận tải hành khách, nằm
ngoài phạm vi MVP (xe máy, ô tô cá nhân); ví dụ được chọn để cho thấy mô hình thời gian của hệ thống xử lý
đúng những trường hợp hiệu lực phức tạp mà văn bản thật đặt ra.*

## 1. Vấn đề

Ngày có hiệu lực của một văn bản không đủ để biết một quy định có áp dụng được hay không:

1. **Hiệu lực riêng theo điểm.** Khoản 2 Điều 53 NĐ 168/2024: điểm m khoản 3 Điều 6, điểm e khoản 4 Điều 26,
   điểm b khoản 1 Điều 27 có hiệu lực từ 01/01/2026, muộn hơn phần còn lại của Nghị định (01/01/2025).
2. **Hiệu lực của một phần nội dung trong một điểm.** Khoản 3 Điều 53 (do Điều 18 NĐ 238/2026 bổ sung):
   *"Quy định xử phạt … liên quan đến thiết bị ghi nhận hình ảnh người lái xe đối với xe ô tô kinh doanh vận tải
   hành khách dưới 08 chỗ …, xe ô tô kinh doanh vận tải hàng hóa (trừ xe ô tô đầu kéo), xe vận tải nội bộ tại
   điểm l khoản 5 Điều 20 … có hiệu lực thi hành từ ngày 01 tháng 01 năm 2028."* Điểm l khoản 5 Điều 20 lại áp
   dụng cho **mọi** xe kinh doanh vận tải hành khách — tức chỉ **một phần** nội dung của điểm bị hoãn tới 2028.
3. **Hiệu lực có điều kiện.** Khoản 4 Điều 53: quy định về thiết bị ghi hình khoang chở khách có hiệu lực
   *"từ ngày 01 tháng 01 năm 2029 **và theo quy định của pháp luật về thiết bị ghi nhận hình ảnh khoang chở
   khách**"*. Đến ngày 01/01/2029, quy định vẫn chưa chắc có hiệu lực vì còn phụ thuộc văn bản khác. Điểm b
   khoản 1 Điều 32 NĐ 168 còn không có ngày, chỉ có điều kiện (pháp luật bảo vệ môi trường).
4. **Văn bản hợp nhất.** Luật Xử lý vi phạm hành chính chỉ có bản hợp nhất 2026: khoản 4 Điều 23 (cách xác
   định mức phạt cụ thể) mang câu chữ do Luật 67/2020 sửa, có hiệu lực từ 01/01/2022. Với vi phạm năm 2021,
   quy định tương ứng có tồn tại nhưng câu chữ cũ không có trong dữ liệu.

5. **Văn bản sửa đổi lùi hiệu lực trước khi mốc cũ kịp đến.** Luật TTATGT (Điều 88 khoản 2) cho khoản 3 Điều
   10 hiệu lực từ 01/01/2026. Luật 118/2025/QH15 (điểm a khoản 20 Điều 7) sửa mốc này thành 01/07/2026, và riêng
   lệnh sửa đó có hiệu lực từ 01/01/2026 (khoản 2 Điều 11 Luật 118), trong khi phần còn lại của Luật 118 có hiệu
   lực từ 01/07/2026. Kết quả: mốc 01/01/2026 không bao giờ có hiệu lực, và Luật TTATGT có **ba phiên bản**:
   bản gốc (2025), bản chỉ áp lệnh lùi hiệu lực (01/01–30/06/2026), bản áp toàn bộ sửa đổi (từ 01/07/2026).

## 2. Mô hình

Mỗi phần tử văn bản (điều, khoản, điểm) mang một danh sách **đoạn hiệu lực** (`hieu_luc_chi_tiet`):

| Trường | Ý nghĩa |
|---|---|
| `pham_vi` | `toan_bo` · `phan_con_lai` · `mot_phan` |
| `mo_ta_pham_vi` | mô tả phần nội dung có hiệu lực riêng |
| `tu`, `den` | khoảng hiệu lực; `tu = null` khi văn bản không nêu ngày |
| `hieu_luc_dieu_kien` | điều kiện phụ thuộc văn bản khác |
| `dieu_kien_da_dap_ung` | chỉ đặt `true` khi có văn bản chứng minh; mặc định `false` |
| `can_cu` | trích nguyên văn quy định về hiệu lực (được test đối chiếu với văn bản nguồn) |

Trong ontology, phần nội dung có hiệu lực riêng là một cá thể của lớp `PhanNoiDung` (⊑ `DieuKhoan`) gắn với
điểm cha qua `thuocDieuKhoanCha`, với `moTaPhamVi`, `hieuLucTu`, `hieuLucDieuKien`, `dieuKienDaDapUng`.

Quy tắc đánh giá (`src/kb/temporal.py › trang_thai_hieu_luc`):

* chưa tới `tu` → **chưa có hiệu lực**;
* đã tới `tu` nhưng còn `hieu_luc_dieu_kien` chưa được xác nhận → **coi là chưa có hiệu lực** và nói rõ lý do;
* không có `tu`, chỉ có điều kiện → **chưa xác định**, coi là chưa có hiệu lực;
* phần nội dung chính có hiệu lực nhưng có phần bị hoãn → **có hiệu lực một phần**, nêu rõ phần nào chưa;
* văn bản hợp nhất, trước ngày của câu chữ hiện hành → **không có dữ liệu câu chữ tại thời điểm đó** (khác với
  "không có quy định").

Ngoại lệ hiệu lực do văn bản sửa đổi đặt ra chỉ áp cho phiên bản có văn bản đó trong nguồn hợp nhất: mốc 2028
của NĐ 238 gắn với V4, không gắn nhầm vào V3. Khi các lệnh của một văn bản sửa đổi có ngày hiệu lực khác nhau,
phiên bản trung gian chỉ áp đúng các lệnh đã có hiệu lực (`amendments: [{doc: L118, only: [...]}]`).

## 3. Kết quả chạy thực tế

| Phần tử | Ngày hỏi | Trạng thái | Giải thích do hệ thống sinh |
|---|---|---|---|
| `ND168-D20-K5-l` (V4) | 03/11/2026 | `mot_phan` | Chỉ có hiệu lực một phần. Phần CHƯA có hiệu lực — Phần quy định về thiết bị ghi nhận hình ảnh người lái xe đối với xe ô tô kinh doanh vận tải hành khách dưới 08 chỗ …, xe ô tô kinh doanh vận tải hàng hóa (trừ xe ô tô đầu kéo), xe vận tải nội bộ: Có hiệu lực từ 01/01/2028. |
| `ND168-D20-K5-l` (V4) | 01/01/2028 | `co_hieu_luc` | Toàn bộ nội dung có hiệu lực. |
| `ND168-D20-K5-n` (V4) | 03/11/2026 | `chua_hieu_luc` | Có hiệu lực từ 01/01/2029, đồng thời theo quy định của pháp luật về thiết bị ghi nhận hình ảnh khoang chở khách …; ngày 03/11/2026 chưa có hiệu lực. |
| `ND168-D20-K5-n` (V4) | 01/06/2029 | `chua_hieu_luc_dieu_kien` | Mốc 01/01/2029 đã đến nhưng hiệu lực còn theo quy định của pháp luật về thiết bị ghi nhận hình ảnh khoang chở khách …; điều kiện này chưa được xác nhận trong dữ liệu nên hệ thống coi là chưa có hiệu lực. |
| `ND168-D32-K1-b` (V3) | 03/11/2026 | `chua_xac_dinh` | Văn bản không nêu ngày hiệu lực; hiệu lực theo quy định của pháp luật bảo vệ môi trường về kiểm định khí thải xe mô tô, xe gắn máy. Hệ thống coi là chưa có hiệu lực. |
| `ND168-D6-K3-m` (V3) | 01/06/2025 | `chua_hieu_luc` | Có hiệu lực từ 01/01/2026; ngày 01/06/2025 chưa có hiệu lực. |
| `LTTATGT-D10-K3` (bản 2026A) | 01/03/2026 | `chua_hieu_luc` | Có hiệu lực từ 01/07/2026; ngày 01/03/2026 chưa có hiệu lực. (Mốc cũ 01/01/2026 đã bị Luật 118 lùi.) |
| `LTTATGT-D10-K3` (bản 2026B) | 01/08/2026 | `co_hieu_luc` | Có hiệu lực từ 01/07/2026 — câu chữ do khoản 3 Điều 7 Luật 118 sửa. |
| `LXLVPHC-D23-K4` | 01/06/2021 | `khong_co_du_lieu_thoi_diem` | Câu chữ hiện hành có hiệu lực từ 01/01/2022 … Không có trong dữ liệu — văn bản hợp nhất chỉ chứa câu chữ hiện hành; câu chữ áp dụng trước 2022-01-01 có thể khác. |

Kiểm thử: `tests/test_temporal.py` (gồm `test_luat_118_lui_hieu_luc_khoan_3_dieu_10`), `tests/test_ontology.py::test_conditional_and_partial_effectivity`.

## 4. Ý nghĩa

* Hệ thống **không trích dẫn một quy định chưa có hiệu lực** làm căn cứ kết luận, kể cả khi chỉ một phần nội
  dung của điểm bị hoãn.
* Khi người dùng hỏi tới các quy định này, câu trả lời **nói rõ vì sao** chưa áp dụng (chưa tới ngày, còn phụ
  thuộc văn bản khác, hay thiếu dữ liệu câu chữ cũ) thay vì im lặng bỏ qua.
* Khi có văn bản xác nhận điều kiện (ví dụ quy định về thiết bị ghi hình khoang chở khách), chỉ cần đặt
  `dieu_kien_da_dap_ung: true` kèm căn cứ trong `config/legal_sources.yaml`, không sửa code.
