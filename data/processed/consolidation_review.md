# Báo cáo hợp nhất văn bản — cần duyệt tay

_Sinh tự động bởi `python -m src.ingest.build_articles` ngày 2026-11-03. Không sửa tay file này; ghi quyết định vào `config/consolidation_overrides.yaml`._

## 1. Cảnh báo khi đọc văn bản nguồn

- **ND123**: Đoạn 856: thay 1 ký tự Kirin giống Latin: 'р) Sửa đổi khoản 13 Điều 30 như sau:' -> 'p) Sửa đổi khoản 13 Điều 30 như sau:'
- **ND123**: Đoạn 860: thay 1 ký tự Kirin giống Latin: 'с) Giao phương tiện hoặc để cho người là' -> 'c) Giao phương tiện hoặc để cho người là'

## 2. Hợp nhất ND123 (123/2021/NĐ-CP) vào ND100 → V2

- Tổng số dòng lệnh: 149
- Đã tự áp: **132**
- Tiêu đề nhóm (không cần áp): 16
- Bỏ qua theo duyệt tay: 0
- **Cần duyệt tay: 1**

### 2.1. Lệnh CHƯA áp — cần duyệt tay

**1. Lệnh:** `điểm s khoản 34 Điều 2 NĐ 123/2021` (đoạn 1130 trong file nguồn)

> Thay cụm từ “tháo dỡ” bằng cụm từ “phá dỡ” tại điểm b khoản 1, điểm a khoản 2, điểm l khoản 3 Điều 4; điểm a khoản 12 Điều 11; điểm đ khoản 10 Điều 12; điểm a khoản 2 Điều 14; điểm g khoản 6 Điều 51; điểm b khoản 4 Điều 52; điểm d, điểm đ, điểm e, điểm g khoản 5 Điều 53; điểm đ khoản 2, điểm c khoản 5 Điều 54;

- **Lý do:** Cụm từ “tháo dỡ” xuất hiện 3 lần tại điểm l khoản 3 Điều 4 (cần đúng 1 lần)
- **Cách xử lý:** thêm vào `config/consolidation_overrides.yaml`:

```yaml
- ref: "điểm s khoản 34 Điều 2 NĐ 123/2021"
  action: replace_all   # hoặc skip / set_text (kèm id, text)
  reviewer: ""
  note: ""
```

### 2.2. Đã áp nhưng nên kiểm tra lại

Các lệnh *bổ sung cụm từ* được ghép tự động (có xử lý dấu câu); nên đối chiếu với nguyên văn.

- `điểm a khoản 33 Điều 2 NĐ 123/2021`: Bổ sung cụm từ “khoản 4a,” vào trước “khoản 5” → ND100-D74-K2-d, ND100-D74-K3-e
- `điểm b khoản 33 Điều 2 NĐ 123/2021`: Bổ sung cụm từ “điểm d khoản 7;” vào sau “khoản 6” → ND100-D74-K5-a
- `điểm c khoản 33 Điều 2 NĐ 123/2021`: Bổ sung cụm từ “điểm a” vào trước “khoản 3” → ND100-D74-K6, ND100-D79-K1-dd, ND100-D80-K5-b

### 2.3. Nhật ký áp đầy đủ

| # | Lệnh | Thao tác | Đơn vị bị ảnh hưởng |
|---|---|---|---|
| 1 | khoản 1 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D2-K2-h |
| 2 | khoản 2 Điều 2 NĐ 123/2021 | Bổ sung Điều ['4a'] | ND100-D4a |
| 3 | điểm a khoản 3 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D5-K3-k |
| 4 | điểm b khoản 3 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D5-K4-c |
| 5 | điểm c khoản 3 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D5-K6-b |
| 6 | điểm d khoản 3 Điều 2 NĐ 123/2021 | Bổ sung điểm ['d'] | ND100-D5-K7-d |
| 7 | điểm a khoản 4 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D6-K3-a |
| 8 | điểm b khoản 4 Điều 2 NĐ 123/2021 | Bổ sung điểm ['n', 'o'] | ND100-D6-K3-n, ND100-D6-K3-o |
| 9 | điểm c khoản 4 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D6-K5 |
| 10 | điểm d khoản 4 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D6-K10-c |
| 11 | khoản 5 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D7-K4-g |
| 12 | khoản 6 Điều 2 NĐ 123/2021 | Bổ sung điểm ['đ', 'e'] | ND100-D8-K4-dd, ND100-D8-K4-e |
| 13 | khoản 7 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D11-K6 |
| 14 | khoản 8 Điều 2 NĐ 123/2021 | Bổ sung khoản ['4a'] | ND100-D15-K4a |
| 15 | khoản 9 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D16 |
| 16 | khoản 10 Điều 2 NĐ 123/2021 | Bổ sung điểm ['d'] | ND100-D17-K2-d |
| 17 | khoản 11 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D21 |
| 18 | điểm a khoản 12 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D23-K5-p |
| 19 | điểm b khoản 12 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D23-K6-dd |
| 20 | điểm c khoản 12 Điều 2 NĐ 123/2021 | Bổ sung khoản ['7a'] | ND100-D23-K7a |
| 21 | điểm d khoản 12 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D23-K8-b |
| 22 | điểm a khoản 13 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D24-K3-c |
| 23 | điểm b khoản 13 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D24-K5-c |
| 24 | điểm c khoản 13 Điều 2 NĐ 123/2021 | Bổ sung khoản ['8a'] | ND100-D24-K8a |
| 25 | điểm d khoản 13 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D24-K9-b |
| 26 | khoản 14 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D25 |
| 27 | điểm a khoản 15 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D28-K2-e |
| 28 | điểm b khoản 15 Điều 2 NĐ 123/2021 | Bổ sung điểm ['i'] | ND100-D28-K2-i |
| 29 | điểm c khoản 15 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D28-K3 |
| 30 | điểm d khoản 15 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D28-K4-d |
| 31 | điểm đ khoản 15 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D28-K6-o |
| 32 | điểm e khoản 15 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D28-K6-p |
| 33 | điểm g khoản 15 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D28-K8 |
| 34 | điểm h khoản 15 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D28-K9 |
| 35 | khoản 16 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D29 |
| 36 | điểm a khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K3 |
| 37 | điểm b khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K4-b |
| 38 | điểm c khoản 17 Điều 2 NĐ 123/2021 | Bổ sung khoản ['4a'] | ND100-D30-K4a |
| 39 | điểm d khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K5-g |
| 40 | điểm đ khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K6 |
| 41 | điểm e khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K7-d |
| 42 | điểm g khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K7-m |
| 43 | điểm h khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K8-g |
| 44 | điểm i khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K9-a |
| 45 | điểm k khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K9-dd |
| 46 | điểm l khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K9-e, ND100-D30-K9-g |
| 47 | điểm m khoản 17 Điều 2 NĐ 123/2021 | Bổ sung điểm ['i'] | ND100-D30-K9-i |
| 48 | điểm n khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K10 |
| 49 | điểm o khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K12 |
| 50 | điểm p khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K13 |
| 51 | điểm q khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K14 |
| 52 | điểm r khoản 17 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D30-K15 |
| 53 | điểm s khoản 17 Điều 2 NĐ 123/2021 | Bổ sung khoản ['16'] | ND100-D30-K16 |
| 54 | khoản 18 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D33 |
| 55 | điểm a khoản 19 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D34-K2 |
| 56 | điểm b khoản 19 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D34-K3 |
| 57 | khoản 20 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D35 |
| 58 | khoản 21 Điều 2 NĐ 123/2021 | Bổ sung điểm ['d'] | ND100-D37-K2-d |
| 59 | khoản 22 Điều 2 NĐ 123/2021 | Bổ sung điểm ['c'] | ND100-D38-K1-c |
| 60 | điểm a khoản 23 Điều 2 NĐ 123/2021 | Thay đoạn mở đầu khoản 3 Điều 44 | ND100-D44-K3 |
| 61 | điểm b khoản 23 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D44-K3-a |
| 62 | điểm a khoản 24 Điều 2 NĐ 123/2021 | Thay tên Điều 66 | ND100-D66 |
| 63 | điểm b khoản 24 Điều 2 NĐ 123/2021 | Thay đoạn mở đầu khoản 3 Điều 66 | ND100-D66-K3 |
| 64 | điểm c khoản 24 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D66-K3-c |
| 65 | điểm d khoản 24 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D66-K4 |
| 66 | điểm đ khoản 24 Điều 2 NĐ 123/2021 | Thay đoạn mở đầu khoản 5 Điều 66 | ND100-D66-K5 |
| 67 | điểm e khoản 24 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D66-K5-a |
| 68 | khoản 25 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D67-K1-a |
| 69 | điểm a khoản 26 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D74-K2-e, ND100-D74-K2-g |
| 70 | điểm b khoản 26 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D74-K3-a, ND100-D74-K3-b |
| 71 | điểm c khoản 26 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D74-K3-h |
| 72 | điểm d khoản 26 Điều 2 NĐ 123/2021 | Bổ sung khoản ['3a'] | ND100-D74-K3a |
| 73 | điểm đ khoản 26 Điều 2 NĐ 123/2021 | Thay đoạn mở đầu khoản 4 Điều 74 | ND100-D74-K4 |
| 74 | điểm e khoản 26 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D74-K4-b |
| 75 | điểm g khoản 26 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D74-K4-e |
| 76 | điểm h khoản 26 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D74-K5-g |
| 77 | điểm i khoản 26 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D74-K5-i |
| 78 | điểm k khoản 26 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D74-K5-l |
| 79 | điểm l khoản 26 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D74-K5-n |
| 80 | điểm m khoản 26 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D74-K5-p |
| 81 | khoản 27 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D75 |
| 82 | khoản 28 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D76 |
| 83 | khoản 29 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D77 |
| 84 | điểm a khoản 30 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D80-K1 |
| 85 | điểm b khoản 30 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D80-K2 |
| 86 | điểm c khoản 30 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D80-K3-a |
| 87 | điểm d khoản 30 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D80-K3-b |
| 88 | điểm đ khoản 30 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D80-K3-d, ND100-D80-K3-dd, ND100-D80-K3-e |
| 89 | điểm e khoản 30 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D80-K3-k |
| 90 | điểm g khoản 30 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D80-K4 |
| 91 | điểm h khoản 30 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D80-K5-c |
| 92 | điểm i khoản 30 Điều 2 NĐ 123/2021 | Bổ sung điểm ['e'] | ND100-D80-K5-e |
| 93 | điểm k khoản 30 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D80-K7 |
| 94 | khoản 31 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D81-K2 |
| 95 | điểm a khoản 32 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D82-K1 |
| 96 | điểm b khoản 32 Điều 2 NĐ 123/2021 | Thay đơn vị | ND100-D82-K2 |
| 97 | điểm a khoản 33 Điều 2 NĐ 123/2021 | Bổ sung cụm từ “khoản 4a,” vào trước “khoản 5” | ND100-D74-K2-d, ND100-D74-K3-e |
| 98 | điểm b khoản 33 Điều 2 NĐ 123/2021 | Bổ sung cụm từ “điểm d khoản 7;” vào sau “khoản 6” | ND100-D74-K5-a |
| 99 | điểm c khoản 33 Điều 2 NĐ 123/2021 | Bổ sung cụm từ “điểm a” vào trước “khoản 3” | ND100-D74-K6, ND100-D79-K1-dd, ND100-D80-K5-b |
| 100 | điểm a khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “điểm a, điểm b khoản 6; điểm a, điểm c khoản 7” bằng “điểm a khoản 6; điểm a,… | ND100-D5-K1-a |
| 101 | điểm b khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “điểm b khoản 6” bằng “điểm d khoản 7” | ND100-D5-K2-h, ND100-D5-K3-e, ND100-D5-K4-d |
| 102 | điểm c khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “điểm h, điểm i khoản 5” bằng “điểm i khoản 5” | ND100-D5-K11-b |
| 103 | điểm d khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “1.000.000 đồng đến 2.000.000 đồng” bằng “2.000.000 đồng đến 3.000.000 đồng” | ND100-D5-K4, ND100-D7-K5, ND100-D47-K7 |
| 104 | điểm đ khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “3.000.000 đồng đến 5.000.000 đồng” bằng “4.000.000 đồng đến 6.000.000 đồng” | ND100-D5-K5, ND100-D47-K8 |
| 105 | điểm e khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “điểm d, điểm g, điểm i, điểm m khoản 3” bằng “điểm a, điểm d, điểm g, điểm i,… | ND100-D6-K1-a |
| 106 | điểm g khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “600.000 đồng đến 1.000.000 đồng” bằng “800.000 đồng đến 1.000.000 đồng” | ND100-D6-K4, ND100-D47-K5 |
| 107 | điểm h khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “điểm b khoản 6 Điều 33” bằng “điểm b khoản 5 Điều 33” | ND100-D11-K9 |
| 108 | điểm i khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “200.000 đồng đến 400.000 đồng” bằng “300.000 đồng đến 400.000 đồng” | ND100-D5-K1, ND100-D7-K2, ND100-D42-K1, ND100-D43-K1, ND100-D46-K1 |
| 109 | điểm k khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “200.000 đồng đến 300.000 đồng” bằng “300.000 đồng đến 400.000 đồng” | ND100-D6-K2, ND100-D8-K3, ND100-D18-K2, ND100-D47-K4 |
| 110 | điểm l khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “từ 200.000 đồng đến 300.000 đồng đối với cá nhân, từ 400.000 đồng đến 600.000… | ND100-D15-K2 |
| 111 | điểm m khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “300.000 đồng đến 400.000 đồng” bằng “800.000 đồng đến 1.000.000 đồng” | ND100-D17-K2, ND100-D19-K1 |
| 112 | điểm n khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “800.000 đồng đến 1.000.000 đồng” bằng “2.000.000 đồng đến 3.000.000 đồng” | ND100-D17-K3 |
| 113 | điểm o khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “tổng mức phạt tiền tối đa không vượt quá 40.000.000 đồng” bằng “tổng mức phạt… | ND100-D23-K2, ND100-D23-K4 |
| 114 | điểm p khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “điểm a khoản 7” bằng “khoản 7a” | ND100-D23-K5-dd, ND100-D23-K5-e, ND100-D23-K5-k |
| 115 | điểm q khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “có thiết kế từ từ 09 chỗ” bằng “có thiết kế từ 09 chỗ” | ND100-D28-K4-c |
| 116 | điểm r khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “từ 7.000.000 đồng đến 10.000.000 đồng đối với cá nhân, từ 14.000.000 đồng đến… | ND100-D28-K7 |
| 117 | điểm t khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “Đối với những hành vi vi phạm quy định về tải trọng, khổ giới hạn của phương … | ND100-D80-K5 |
| 118 | điểm a khoản 35 Điều 2 NĐ 123/2021 | Bỏ cụm từ “công lập” | ND100-D2-K2-c |
| 119 | điểm a khoản 35 Điều 2 NĐ 123/2021 | Bỏ cụm từ “, tổ hợp tác” | ND100-D2-K3 |
| 120 | điểm b khoản 35 Điều 2 NĐ 123/2021 | Bỏ cụm từ “hoặc tái phạm hành vi quy định tại điểm b khoản 7 Điều này,” | ND100-D5-K11-d |
| 121 | điểm c khoản 35 Điều 2 NĐ 123/2021 | Bỏ cụm từ “điểm đ,” | ND100-D6-K10-b |
| 122 | điểm d khoản 35 Điều 2 NĐ 123/2021 | Bỏ cụm từ “kinh doanh vận tải, dịch vụ hỗ trợ vận tải” | ND100-D28-K1 |
| 123 | điểm a khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D5-K5-h |
| 124 | điểm b khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D6-K2-i, ND100-D6-K2-k, ND100-D6-K4-dd |
| 125 | điểm c khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D8-K3-d, ND100-D8-K3-dd |
| 126 | điểm d khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D11-K3 |
| 127 | điểm đ khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D17-K1-b |
| 128 | điểm e khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D23-K5-g, ND100-D23-K7-a |
| 129 | điểm g khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D24-K3-a, ND100-D24-K6-c |
| 130 | điểm h khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D30-K2-b, ND100-D30-K4-c, ND100-D30-K7-dd, ND100-D30-K7-k |
| 131 | điểm i khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D80-K11 |
| 132 | điểm k khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D83 |

## 3. Hiệu lực theo từng phần tử và văn bản chưa có

- ND168 ND168-D6-K3-m, ND168-D26-K4-e, ND168-D27-K1-b: hiệu lực từ `2026-01-01` — _Điều 53 khoản 2: Quy định tại điểm m khoản 3 Điều 6, điểm e khoản 4 Điều 26, điểm b khoản 1 Điều 27 của Nghị định này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2026_
- ND168 ND168-D32-K1-b: hiệu lực từ `None` **TODO_VERIFY** — _Điều 53 khoản 2: quy định tại điểm b khoản 1 Điều 32 của Nghị định này có hiệu lực thi hành theo quy định của pháp luật bảo vệ môi trường về kiểm định khí thải xe mô tô, xe gắn máy._
- Văn bản **238/2026/NĐ-CP** (sửa ND168, hiệu lực 2026-08-15) chưa có trong data/raw/. Nguồn: Người dùng cung cấp trong đặc tả; chưa có văn bản để đối chiếu. **TODO_VERIFY**
