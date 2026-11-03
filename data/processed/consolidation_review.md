# Báo cáo hợp nhất văn bản — cần duyệt tay

_Sinh tự động bởi `python -m src.ingest.build_articles` ngày 2026-11-04. Không sửa tay file này; ghi quyết định vào `config/consolidation_overrides.yaml`._

## 1. Cảnh báo khi đọc văn bản nguồn

- **ND123**: Đoạn 856: thay 1 ký tự Kirin giống Latin: 'р) Sửa đổi khoản 13 Điều 30 như sau:' -> 'p) Sửa đổi khoản 13 Điều 30 như sau:'
- **ND123**: Đoạn 860: thay 1 ký tự Kirin giống Latin: 'с) Giao phương tiện hoặc để cho người là' -> 'c) Giao phương tiện hoặc để cho người là'
- **L118**: Trùng khoản 4 Điều 5 tại đoạn 236
- **L118**: Trùng khoản 5 Điều 5 tại đoạn 238

## 2. Hợp nhất ND123 (123/2021/NĐ-CP) vào ND100 → V2

- Tổng số dòng lệnh: 149
- Đã tự áp: **133**
- Tiêu đề nhóm (không cần áp): 16
- Bỏ qua theo duyệt tay: 0
- **Cần duyệt tay: 0**

### 2.1. Lệnh CHƯA áp — cần duyệt tay

Không có.
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
| 117 | điểm s khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “tháo dỡ” bằng “phá dỡ” | ND100-D4-K1-b, ND100-D4-K2-a, ND100-D4-K3-l, ND100-D11-K12-a, ND100-D12-K10-dd, ND100-D14-K2-a, ND100-D51-K6-g, ND100-D52-K4-b, ND100-D53-K5-d, ND100-D53-K5-dd, ND100-D53-K5-e, ND100-D53-K5-g, ND100-D54-K2-dd, ND100-D54-K5-c |
| 118 | điểm t khoản 34 Điều 2 NĐ 123/2021 | Thay cụm từ “Đối với những hành vi vi phạm quy định về tải trọng, khổ giới hạn của phương … | ND100-D80-K5 |
| 119 | điểm a khoản 35 Điều 2 NĐ 123/2021 | Bỏ cụm từ “công lập” | ND100-D2-K2-c |
| 120 | điểm a khoản 35 Điều 2 NĐ 123/2021 | Bỏ cụm từ “, tổ hợp tác” | ND100-D2-K3 |
| 121 | điểm b khoản 35 Điều 2 NĐ 123/2021 | Bỏ cụm từ “hoặc tái phạm hành vi quy định tại điểm b khoản 7 Điều này,” | ND100-D5-K11-d |
| 122 | điểm c khoản 35 Điều 2 NĐ 123/2021 | Bỏ cụm từ “điểm đ,” | ND100-D6-K10-b |
| 123 | điểm d khoản 35 Điều 2 NĐ 123/2021 | Bỏ cụm từ “kinh doanh vận tải, dịch vụ hỗ trợ vận tải” | ND100-D28-K1 |
| 124 | điểm a khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D5-K5-h |
| 125 | điểm b khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D6-K2-i, ND100-D6-K2-k, ND100-D6-K4-dd |
| 126 | điểm c khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D8-K3-d, ND100-D8-K3-dd |
| 127 | điểm d khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D11-K3 |
| 128 | điểm đ khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D17-K1-b |
| 129 | điểm e khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D23-K5-g, ND100-D23-K7-a |
| 130 | điểm g khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D24-K3-a, ND100-D24-K6-c |
| 131 | điểm h khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D30-K2-b, ND100-D30-K4-c, ND100-D30-K7-dd, ND100-D30-K7-k |
| 132 | điểm i khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D80-K11 |
| 133 | điểm k khoản 36 Điều 2 NĐ 123/2021 | Bãi bỏ | ND100-D83 |

## 2. Hợp nhất ND238 (238/2026/NĐ-CP) vào ND168 → V4

- Tổng số dòng lệnh: 63
- Đã tự áp: **60**
- Tiêu đề nhóm (không cần áp): 3
- Bỏ qua theo duyệt tay: 0
- **Cần duyệt tay: 0**

### 2.1. Lệnh CHƯA áp — cần duyệt tay

Không có.
### 2.2. Đã áp nhưng nên kiểm tra lại

Các lệnh *bổ sung cụm từ* được ghép tự động (có xử lý dấu câu); nên đối chiếu với nguyên văn.

- `khoản 1 Điều 19 NĐ 238/2026`: Bổ sung cụm từ “, trừ hành vi vi phạm quy định tại điểm b khoản 3a Điều 29 của Nghị định này” vào sau “xe được kéo khi kéo nhau” → ND168-D6-K3-h
- `khoản 2 Điều 19 NĐ 238/2026`: Bổ sung cụm từ “hoặc chuyển làn đường không bảo đảm khoảng cách an toàn với xe phía trước, xe phía sau, xe hai bên” vào sau “chỉ được phép chuyển sang một làn đường liền kề” → ND168-D6-K2-a, ND168-D6-K5-g, ND168-D7-K1-e, ND168-D8-K6-h
- `khoản 3 Điều 19 NĐ 238/2026`: Bổ sung cụm từ “hoặc có quy định cấm của cấp có thẩm quyền đối với loại phương tiện đang điều khiển” vào sau “đối với loại phương tiện đang điều khiển” → ND168-D6-K5-i, ND168-D7-K6-b, ND168-D8-K6-d
- `khoản 4 Điều 19 NĐ 238/2026`: Bổ sung cụm từ “hoặc dải dừng xe khẩn cấp” vào sau “làn dừng xe khẩn cấp” → ND168-D6-K7-c, ND168-D8-K6-b
- `khoản 5 Điều 19 NĐ 238/2026`: Bổ sung cụm từ “khoản 1; điểm d,” vào trước “điểm đ” → ND168-D14-K6-a
- `khoản 6 Điều 19 NĐ 238/2026`: Bổ sung cụm từ “, xe vận tải nội bộ” vào sau “xe ô tô kinh doanh vận tải” → ND168-D20-K6-d, ND168-D21-K5-b
- `khoản 7 Điều 19 NĐ 238/2026`: Bổ sung cụm từ “, điểm l” vào sau “điểm h” → ND168-D26-K11
- `khoản 8 Điều 19 NĐ 238/2026`: Bổ sung cụm từ “Điều 20 (điểm l khoản 5, điểm đ khoản 6), Điều 21 (điểm b khoản 3, điểm c khoản 5),” vào trước “Điều 29” → ND168-D47-K3-h
- `khoản 8 Điều 19 NĐ 238/2026`: Bổ sung cụm từ “; khoản 9a” vào sau “điểm n khoản 7” → ND168-D47-K3-h
- `khoản 9 Điều 19 NĐ 238/2026`: Bổ sung cụm từ “, khoản 3, khoản 4” vào sau “khoản 2” → ND168-D53-K1

### 2.3. Nhật ký áp đầy đủ

| # | Lệnh | Thao tác | Đơn vị bị ảnh hưởng |
|---|---|---|---|
| 1 | khoản 1 Điều 1 NĐ 238/2026 | Thay đơn vị | ND168-D3-K3-i |
| 2 | khoản 2 Điều 1 NĐ 238/2026 | Thay đơn vị | ND168-D3-K3-l |
| 3 | khoản 1 Điều 2 NĐ 238/2026 | Bổ sung khoản ['1a'] | ND168-D6-K1a |
| 4 | khoản 2 Điều 2 NĐ 238/2026 | Thay đơn vị | ND168-D6-K3-m |
| 5 | Điều 3 NĐ 238/2026 | Thay đơn vị | ND168-D13-K8-b |
| 6 | Điều 4 NĐ 238/2026 | Thay đơn vị | ND168-D14-K3-b |
| 7 | Điều 5 NĐ 238/2026 | Thay đơn vị | ND168-D17-K2-a |
| 8 | Điều 6 NĐ 238/2026 | Thay đơn vị | ND168-D18-K4-a |
| 9 | điểm a khoản 1 Điều 7 NĐ 238/2026 | Thay đơn vị | ND168-D20-K5-dd |
| 10 | điểm b khoản 1 Điều 7 NĐ 238/2026 | Thay đơn vị | ND168-D20-K5-g |
| 11 | điểm c khoản 1 Điều 7 NĐ 238/2026 | Thay đơn vị | ND168-D20-K5-l, ND168-D20-K5-m |
| 12 | điểm d khoản 1 Điều 7 NĐ 238/2026 | Bổ sung điểm ['n'] | ND168-D20-K5-n |
| 13 | khoản 2 Điều 7 NĐ 238/2026 | Thay đơn vị | ND168-D20-K6-dd |
| 14 | khoản 3 Điều 7 NĐ 238/2026 | Bổ sung khoản ['8a'] | ND168-D20-K8a |
| 15 | khoản 4 Điều 7 NĐ 238/2026 | Thay đơn vị | ND168-D20-K10-c |
| 16 | khoản 1 Điều 8 NĐ 238/2026 | Thay đơn vị | ND168-D21-K2-b |
| 17 | khoản 2 Điều 8 NĐ 238/2026 | Thay đơn vị | ND168-D21-K3-b |
| 18 | khoản 3 Điều 8 NĐ 238/2026 | Thay đơn vị | ND168-D21-K5-c |
| 19 | điểm a khoản 4 Điều 8 NĐ 238/2026 | Thay đơn vị | ND168-D21-K8-d, ND168-D21-K8-dd |
| 20 | điểm b khoản 4 Điều 8 NĐ 238/2026 | Bổ sung điểm ['e'] | ND168-D21-K8-e |
| 21 | điểm a khoản 1 Điều 9 NĐ 238/2026 | Thay đơn vị | ND168-D26-K7-e |
| 22 | điểm b khoản 1 Điều 9 NĐ 238/2026 | Bổ sung điểm ['k', 'l'] | ND168-D26-K7-k, ND168-D26-K7-l |
| 23 | khoản 2 Điều 9 NĐ 238/2026 | Bổ sung điểm ['d'] | ND168-D26-K8-d |
| 24 | khoản 3 Điều 9 NĐ 238/2026 | Thay đơn vị | ND168-D26-K13-c, ND168-D26-K13-d |
| 25 | khoản 1 Điều 10 NĐ 238/2026 | Bổ sung khoản ['3a'] | ND168-D29-K3a |
| 26 | khoản 2 Điều 10 NĐ 238/2026 | Thay đơn vị | ND168-D29-K4 |
| 27 | khoản 1 Điều 11 NĐ 238/2026 | Bổ sung khoản ['9a'] | ND168-D32-K9a |
| 28 | khoản 2 Điều 11 NĐ 238/2026 | Bổ sung điểm ['e'] | ND168-D32-K11-e |
| 29 | khoản 3 Điều 11 NĐ 238/2026 | Bổ sung điểm ['e'] | ND168-D32-K13-e |
| 30 | khoản 4 Điều 11 NĐ 238/2026 | Thay đơn vị | ND168-D32-K19-l |
| 31 | khoản 5 Điều 11 NĐ 238/2026 | Thay đơn vị | ND168-D32-K21-c |
| 32 | khoản 1 Điều 12 NĐ 238/2026 | Thay đơn vị | ND168-D41-K2-d |
| 33 | khoản 2 Điều 12 NĐ 238/2026 | Bổ sung điểm ['k1'] | ND168-D41-K4-k1 |
| 34 | khoản 3 Điều 12 NĐ 238/2026 | Thay đơn vị | ND168-D41-K5 |
| 35 | Điều 13 NĐ 238/2026 | Thay đơn vị | ND168-D42 |
| 36 | Điều 14 NĐ 238/2026 | Thay đơn vị | ND168-D43 |
| 37 | Điều 15 NĐ 238/2026 | Thay đơn vị | ND168-D44 |
| 38 | Điều 16 NĐ 238/2026 | Thay đơn vị | ND168-D46-K2 |
| 39 | khoản 1 Điều 17 NĐ 238/2026 | Thay đơn vị | ND168-D50-K1-dd |
| 40 | khoản 2 Điều 17 NĐ 238/2026 | Thay đoạn thứ 2 của điểm a khoản 3 Điều 50 | ND168-D50-K3-a |
| 41 | Điều 18 NĐ 238/2026 | Bổ sung khoản ['3', '4'] | ND168-D53-K3, ND168-D53-K4 |
| 42 | khoản 1 Điều 19 NĐ 238/2026 | Bổ sung cụm từ “, trừ hành vi vi phạm quy định tại điểm b khoản 3a Điều 29 của Nghị định n… | ND168-D6-K3-h |
| 43 | khoản 2 Điều 19 NĐ 238/2026 | Bổ sung cụm từ “hoặc chuyển làn đường không bảo đảm khoảng cách an toàn với xe phía trước,… | ND168-D6-K2-a, ND168-D6-K5-g, ND168-D7-K1-e, ND168-D8-K6-h |
| 44 | khoản 3 Điều 19 NĐ 238/2026 | Bổ sung cụm từ “hoặc có quy định cấm của cấp có thẩm quyền đối với loại phương tiện đang đ… | ND168-D6-K5-i, ND168-D7-K6-b, ND168-D8-K6-d |
| 45 | khoản 4 Điều 19 NĐ 238/2026 | Bổ sung cụm từ “hoặc dải dừng xe khẩn cấp” vào sau “làn dừng xe khẩn cấp” | ND168-D6-K7-c, ND168-D8-K6-b |
| 46 | khoản 5 Điều 19 NĐ 238/2026 | Bổ sung cụm từ “khoản 1; điểm d,” vào trước “điểm đ” | ND168-D14-K6-a |
| 47 | khoản 6 Điều 19 NĐ 238/2026 | Bổ sung cụm từ “, xe vận tải nội bộ” vào sau “xe ô tô kinh doanh vận tải” | ND168-D20-K6-d, ND168-D21-K5-b |
| 48 | khoản 7 Điều 19 NĐ 238/2026 | Bổ sung cụm từ “, điểm l” vào sau “điểm h” | ND168-D26-K11 |
| 49 | khoản 8 Điều 19 NĐ 238/2026 | Bổ sung cụm từ “Điều 20 (điểm l khoản 5, điểm đ khoản 6), Điều 21 (điểm b khoản 3, điểm c … | ND168-D47-K3-h |
| 50 | khoản 8 Điều 19 NĐ 238/2026 | Bổ sung cụm từ “; khoản 9a” vào sau “điểm n khoản 7” | ND168-D47-K3-h |
| 51 | khoản 9 Điều 19 NĐ 238/2026 | Bổ sung cụm từ “, khoản 3, khoản 4” vào sau “khoản 2” | ND168-D53-K1 |
| 52 | khoản 10 Điều 19 NĐ 238/2026 | Thay cụm từ “chở người trên nóc xe; để người đu bám ở cửa xe, bên ngoài thành xe khi xe đa… | ND168-D6-K5-p |
| 53 | khoản 11 Điều 19 NĐ 238/2026 | Thay cụm từ “giấy chứng nhận kiểm định” bằng “chứng nhận kiểm định” | ND168-D3-K3-q, ND168-D3-K3-r, ND168-D13-K3-d, ND168-D13-K4-b, ND168-D18-K3-c, ND168-D21-K2-a, ND168-D21-K2-d, ND168-D21-K5-a, ND168-D21-K5-d, ND168-D21-K6-a, ND168-D21-K6-b, ND168-D21-K7-a, ND168-D21-K7-b, ND168-D21-K8-a, ND168-D21-K8-b, ND168-D26-K1-a, ND168-D26-K3, ND168-D26-K5, ND168-D32-K1-b, ND168-D32-K11-d, ND168-D32-K14-h, ND168-D32-K18-c, ND168-D32-K18-d, ND168-D32-K19-dd, ND168-D32-K19-g, ND168-D32-K20, ND168-D40-K4-a, ND168-D48-K3 |
| 54 | khoản 12 Điều 19 NĐ 238/2026 | Bỏ cụm từ “giấy chứng nhận kiểm định an toàn kỹ thuật và bảo vệ môi trường” | ND168-D32-K7-b, ND168-D32-K7-d |
| 55 | khoản 12 Điều 19 NĐ 238/2026 | Bỏ cụm từ “điểm e, điểm g khoản 7;” | ND168-D32-K18-dd |
| 56 | khoản 13 Điều 19 NĐ 238/2026 | Bỏ cụm từ “tại nơi phát hiện vi phạm” | ND168-D47-K5-c |
| 57 | khoản 14 Điều 19 NĐ 238/2026 | Bỏ cụm từ “Điểm g khoản 5;” | ND168-D48-K1-a |
| 58 | khoản 15 Điều 19 NĐ 238/2026 | Bỏ cụm từ “điểm m khoản 3 Điều 6,” | ND168-D53-K2 |
| 59 | khoản 16 Điều 19 NĐ 238/2026 | Bỏ cụm từ “trực thuộc trung ương” | ND168-D55 |
| 60 | khoản 17 Điều 19 NĐ 238/2026 | Bãi bỏ | ND168-D32-K17-d, ND168-D32-K17-dd, ND168-D32-K17-e, ND168-D32-K17-g |

## 2. Hợp nhất L118 (118/2025/QH15) vào LTTATGT → LTTATGT_2026B

- Tổng số dòng lệnh: 39
- Đã tự áp: **31**
- Tiêu đề nhóm (không cần áp): 8
- Bỏ qua theo duyệt tay: 0
- **Cần duyệt tay: 0**

### 2.1. Lệnh CHƯA áp — cần duyệt tay

Không có.
### 2.2. Đã áp nhưng nên kiểm tra lại

Các lệnh *bổ sung cụm từ* được ghép tự động (có xử lý dấu câu); nên đối chiếu với nguyên văn.

- Không có.

### 2.3. Nhật ký áp đầy đủ

| # | Lệnh | Thao tác | Đơn vị bị ảnh hưởng |
|---|---|---|---|
| 1 | điểm a khoản 1 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D7-K1-c, LTTATGT-D7-K1-d |
| 2 | điểm b khoản 1 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D7-K1-h |
| 3 | khoản 2 Điều 7 Luật 118/2025/QH15 | Thay ['18'] và bổ sung ['18a'] | LTTATGT-D9-K18, LTTATGT-D9-K18a |
| 4 | khoản 3 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D10-K3 |
| 5 | khoản 4 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D27-K3-a, LTTATGT-D27-K3-b |
| 6 | điểm a khoản 5 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D34-K4 |
| 7 | điểm b khoản 5 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D34-K6 |
| 8 | khoản 6 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D35-K2, LTTATGT-D35-K3 |
| 9 | khoản 7 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D41-K7 |
| 10 | điểm a khoản 8 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D42-K4 |
| 11 | điểm b khoản 8 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D42-K5-e |
| 12 | khoản 9 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D43-K1 |
| 13 | khoản 10 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D52-K9 |
| 14 | khoản 11 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D57-K9 |
| 15 | điểm a khoản 12 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D60-K3-e |
| 16 | điểm b khoản 12 Điều 7 Luật 118/2025/QH15 | Thay ['7', '8'] và bổ sung ['9'] | LTTATGT-D60-K7, LTTATGT-D60-K8, LTTATGT-D60-K9 |
| 17 | điểm a khoản 13 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D61-K4 |
| 18 | điểm b khoản 13 Điều 7 Luật 118/2025/QH15 | Thay ['6', '7'] và bổ sung ['8'] | LTTATGT-D61-K6, LTTATGT-D61-K7, LTTATGT-D61-K8 |
| 19 | điểm a khoản 14 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D62-K5-b |
| 20 | điểm b khoản 14 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D62-K6 |
| 21 | khoản 15 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D64-K1 |
| 22 | khoản 16 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D67-K3 |
| 23 | khoản 17 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D71 |
| 24 | khoản 18 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D75-K4-c |
| 25 | khoản 19 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D87-K2, LTTATGT-D87-K3 |
| 26 | điểm a khoản 20 Điều 7 Luật 118/2025/QH15 | Thay đơn vị | LTTATGT-D88-K2 |
| 27 | điểm b khoản 20 Điều 7 Luật 118/2025/QH15 | Bổ sung khoản ['2a'] | LTTATGT-D88-K2a |
| 28 | khoản 21 Điều 7 Luật 118/2025/QH15 | Thay cụm từ “Bộ Giao thông vận tải” bằng “Bộ Xây dựng” | LTTATGT-D11-K13, LTTATGT-D12-K4, LTTATGT-D42-K5, LTTATGT-D49-K1-d, LTTATGT-D53-K7, LTTATGT-D63-K4 |
| 29 | điểm a khoản 22 Điều 7 Luật 118/2025/QH15 | Bỏ cụm từ “, Bộ Lao động, Thương binh và Xã hội,” | LTTATGT-D6-K3 |
| 30 | điểm b khoản 22 Điều 7 Luật 118/2025/QH15 | Bỏ cụm từ “trực thuộc trung ương” | LTTATGT-D75-K3 |
| 31 | khoản 23 Điều 7 Luật 118/2025/QH15 | Bãi bỏ | LTTATGT-D62-K7 |

## 3. Hiệu lực riêng theo phần tử / phần nội dung

- ND168 ND168-D6-K3-m, ND168-D26-K4-e, ND168-D27-K1-b (toàn bộ): từ `2026-01-01`
- ND168 ND168-D32-K1-b (toàn bộ): từ `chưa xác định`; **có điều kiện**: theo quy định của pháp luật bảo vệ môi trường về kiểm định khí thải xe mô tô, xe gắn máy
- ND238 ND168-D20-K5-l, ND168-D21-K3-b, ND168-D32-K9a-b (một phần nội dung): từ `2028-01-01`
- ND238 ND168-D20-K5-n, ND168-D26-K7-k, ND168-D26-K7-l (toàn bộ): từ `2029-01-01`; **có điều kiện**: theo quy định của pháp luật về thiết bị ghi nhận hình ảnh khoang chở khách trên phương tiện giao thông đường bộ
- LTTATGT LTTATGT-D10-K3 (toàn bộ): từ `2026-01-01`
- L118 LTTATGT-D10-K3 (toàn bộ): từ `2026-07-01`

## 4. Văn bản bổ trợ và văn bản được thay thế nhưng chưa có

- **LTTATGT** (36/2024/QH15): hiệu lực từ 2025-01-01. Điều kiện người điều khiển (Điều 56), hạng GPLX (Điều 57), độ tuổi (Điều 59) — áp cho vi phạm từ 01/01/2025
  - Thay thế: Luật Giao thông đường bộ số 23/2008/QH12 (GTDB2008)
- **L118** (118/2025/QH15): hiệu lực từ 2026-07-01. 
- **GTDB2008** (23/2008/QH12): hiệu lực từ 2009-07-01. Điều kiện người lái xe (Điều 58), độ tuổi (Điều 60) — áp cho vi phạm đến 31/12/2024 (V1, V2)
  - Sửa đổi chưa có: Luật số 35/2018/QH14 và Luật số 44/2019/QH14 (được khoản 3 Điều 88 Luật TTATGT nêu) — file data/raw/GTDB_2008.docx là bản gốc 2008, chưa gồm các sửa đổi này **TODO_VERIFY**
- **TT31** (31/2019/TT-BGTVT): hiệu lực từ 2019-10-15. Tốc độ tối đa khi không có biển báo (Điều 6–9) — áp cho vi phạm đến 31/12/2024 (V1, V2)
  - Sửa đổi chưa có: Điều 15 Thông tư số 06/2023/TT-BGTVT (TT 38 'thay thế Điều 15 Thông tư số 06/2023/TT-BGTVT ... sửa đổi, bổ sung một số điều của các Thông tư ...') — có thể đã sửa TT 31 từ năm 2023; chưa có trong data/raw/ **TODO_VERIFY**
- **TT38** (38/2024/TT-BGTVT): hiệu lực từ 2025-01-01. Tốc độ khai thác tối đa khi không có biển báo (Điều 6–9) — dùng để suy ra tocDoToiDaChoPhep
  - Thay thế: Thông tư số 31/2019/TT-BGTVT (TT31)
- **LXLVPHC** (15/2012/QH13): hiệu lực từ 2013-07-01. Tình tiết giảm nhẹ/tăng nặng (Điều 9, 10), mức phạt cụ thể (khoản 4 Điều 23), đối tượng bị xử phạt (Điều 5), người chưa thành niên (Điều 134)
