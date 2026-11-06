# Hướng dẫn gán nhãn bộ tình huống đánh giá

Bộ tình huống dùng để đo hệ thống (và baseline chỉ dùng LLM) theo mục 10 của đặc tả. Mỗi tình huống là một lời kể
của người dân, kèm **nhãn chuẩn**: hành vi vi phạm, phiên bản pháp lý, câu hỏi hệ thống phải hỏi lại, và các giá
trị trích xuất mong đợi.

## 1. Quy trình

1. Sửa hoặc thêm tình huống trong `data/test/scenarios_src.yaml`.
2. Chạy `python -m evaluation.sinh_nhan`. Script sinh `data/test/scenarios.jsonl` và báo lỗi nếu nhãn sai: mã hành vi
   không có ở phiên bản đó, tên trường câu hỏi không tồn tại, sự kiện không có trong ontology.
3. Chạy đánh giá: `python -m evaluation.ablation` (tất cả cấu hình) hoặc `python -m evaluation.run_eval --cau-hinh day_du`.

**Người gán nhãn KHÔNG gõ số điều/khoản/điểm hay mức phạt.** Chỉ ghi mã hành vi và phiên bản. Script tra điều khoản
và khung phạt từ `ontology/rule_registry.yaml`, bảng đã được kiểm chứng với văn bản trong `data/raw/` ở Phase 1 và 3.
Nhờ vậy nhãn chuẩn và hệ thống dùng chung một bảng pháp lý đã duyệt. Phép đo kiểm tra hệ thống có **đi tới đúng hành
vi và đúng điều khoản** từ lời kể hay không, chứ không kiểm tra lại bảng đó.

## 2. Các trường của một tình huống

```yaml
- id: S18                      # duy nhất
  nhom: da_loi                 # một trong 6 nhóm (mục 3)
  luot: ["<lời kể đầu tiên>"]  # tin nhắn đầu của người dùng
  tra_loi:                     # câu trả lời của người dùng mô phỏng, theo TÊN TRƯỜNG câu hỏi (config/slots.yaml)
    dung_tich: "Xe 110 phân khối."
  nhan:
    phien_ban: V4              # theo ngày vi phạm (mục 4)
    hanh_vi: [XM_DEN_DO, XM_KHONG_GPLX_NHO]   # mã trong config/mvp_behaviors.yaml; [] = không vi phạm
    hoi_luot_dau: []           # trường BẮT BUỘC phải hỏi ở lượt đầu (nhóm thiếu thông tin); [] = không được hỏi gì
    truong:                    # giá trị trích xuất mong đợi (chỉ ghi trường lời kể có nêu)
      loai_xe: XM_MOTO         # bí danh tập lớp chấp nhận (đầu file) hoặc danh sách lớp
      dung_tich_xi_lanh: 110
    su_kien:                   # sự kiện boolean then chốt (thuộc tính ontology), kể cả sự kiện phải SUY RA
      coGPLX: false
      khongChapHanhDenTinHieu: true
  ghi_chu: "…"                 # tùy chọn: vì sao là bẫy, điểm cần chú ý
```

Trường `truong` có thể có: `loai_xe`, `ngay` (YYYY-MM-DD), `nong_do_con_khi_tho` (mg/L), `nong_do_con_mau`
(mg/100 mL), `toc_do_thuc_te`, `toc_do_toi_da` (km/h), `dung_tich_xi_lanh` (cm3), `tuoi_nguoi_lai`.

Tên trường câu hỏi dùng trong `tra_loi` và `hoi_luot_dau`: `mo_ta_hanh_vi`, `loai_xe`, `ngay_chinh_xac`, `den_vang`,
`nong_do_con`, `don_vi_nong_do`, `toc_do_thuc_te`, `toc_do_toi_da`, `dac_diem_duong`, `dung_tich`, `tuoi_nguoi_lai`,
`loai_giay_to`, `kinh_doanh_van_tai`, `tai_nan`, `nguoi_lai_duoc_giao_xe`. Câu hỏi xác nhận (`xac_nhan`) không cần
ghi: người dùng mô phỏng tự trả lời "đúng" nếu mọi mục được hỏi khớp nhãn `su_kien`/`loai_xe`, ngược lại trả lời "không".

## 3. Sáu nhóm tình huống

| Nhóm | Ý nghĩa | Ghi chú gán nhãn |
|---|---|---|
| `don_loi` | một hành vi, lời kể nói thẳng | `hoi_luot_dau: []` |
| `da_loi` | nhiều hành vi trong một lời kể | liệt kê đủ mã; với cặp loại trừ (gây tai nạn bỏ trốn / liên quan tai nạn không dừng), chỉ ghi mã được áp |
| `gian_tiep` | hành vi phải SUY RA (vd. "rồ ga chạy khi CSGT vẫy") | ghi `su_kien` cần suy ra |
| `thieu_thong_tin` | thiếu trường quyết định → hệ thống phải hỏi | ghi `hoi_luot_dau` và `tra_loi` cho từng câu |
| `khac_thoi_diem` | cùng hành vi ở các phiên bản khác nhau | nên có cặp/bộ cùng lời kể, chỉ khác ngày |
| `khong_vi_pham` | bẫy hoặc không vi phạm | `hanh_vi: []`; ghi `ghi_chu` lý do |

## 4. Phiên bản pháp lý theo ngày vi phạm

| Phiên bản | Áp dụng cho vi phạm | Văn bản |
|---|---|---|
| V1 | 01/01/2020 – 31/12/2021 | NĐ 100/2019 |
| V2 | 01/01/2022 – 31/12/2024 | NĐ 100/2019 + NĐ 123/2021 |
| V3 | 01/01/2025 – 14/08/2026 | NĐ 168/2024 |
| V4 | từ 15/08/2026 | NĐ 168/2024 + NĐ 238/2026 |

Khi đánh giá, "hôm nay" cố định là **06/11/2026**: "hôm qua" là 05/11/2026 (V4). Lời kể không nêu ngày thì áp phiên bản
đang có hiệu lực hôm nay (V4), theo quyết định đã chốt ở Phase 4.

## 5. Quy ước gán nhãn hành vi

- Chỉ gán hành vi thuộc phạm vi MVP (60 mã trong `config/mvp_behaviors.yaml`, xem `docs/mvp_behaviors.md`).
  Hành vi ngoài phạm vi thì coi là không vi phạm *trong phạm vi hệ thống*, kèm `ghi_chu`.
- "Xe máy" chung chung là nhóm xe mô tô, xe gắn máy. Hành vi phụ thuộc dung tích (GPLX, độ tuổi) chỉ gán khi lời kể
  hoặc `tra_loi` có dung tích.
- Từ 2025 (V3, V4), lỗi *không mang theo* GPLX hoặc đăng ký chỉ áp với xe kinh doanh vận tải (điều kiện của luật).
- Tốc độ: mức vượt = tốc độ thực tế − tốc độ tối đa. Tránh giá trị đúng biên ngưỡng (10, 20, 35 km/h) trừ khi muốn
  thử biên.
- Không gán tình tiết tăng nặng/giảm nhẹ ở bộ này. Mức điều chỉnh vẫn là quy ước của hệ thống (TODO_VERIFY).

## 6. Metric được tính từ nhãn

- **Phát hiện hành vi**: precision / recall / F1 (micro), so theo mã hành vi và theo id điều khoản.
- **Điều khoản**: tỉ lệ hành vi chuẩn có điều khoản dự đoán khớp tới điểm. **Khung phạt**: khớp min–max.
- **Phiên bản pháp lý**: đúng phiên bản theo ngày.
- **Hỏi lại đúng lúc**: lượt đầu hỏi đủ `hoi_luot_dau` (nhóm thiếu thông tin), hoặc không hỏi gì khi `hoi_luot_dau`
  rỗng. Báo cả tỉ lệ hỏi thừa.
- **Dẫn sai luật / luật hết hiệu lực**: căn cứ trong câu trả lời không thuộc nhãn, hoặc thuộc văn bản không áp dụng
  cho phiên bản của vụ việc.
- **Trích xuất**: F1 từng trường trong `truong`. **Sự kiện**: độ khớp `su_kien`. **Ánh xạ node**: tỉ lệ node dấu
  hiệu kỳ vọng (script tự suy từ điều kiện luật) có trong kết quả.
- **Độ trễ**: trung bình và p95 mỗi lượt.
