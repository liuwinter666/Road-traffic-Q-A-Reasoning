## Tóm tắt

Trên 50 tình huống (6 nhóm), hệ thống đầy đủ đạt **F1 phát hiện hành vi 95,4%** (theo mã) / **93,6%** (theo điều
khoản, khớp tới điểm), **90% tình huống đúng trọn vẹn**, **100% đúng khung phạt** khi đã xác định đúng điều khoản,
**97,9% đúng phiên bản pháp lý**. Baseline chỉ dùng LLM (cùng model Gemini, trả lời từ kiến thức sẵn có) chỉ đạt
**3,7%** F1 theo điều khoản và **16%** tình huống đúng trọn vẹn — gần như toàn bộ là các tình huống không vi phạm.

| | Hệ thống đầy đủ | Baseline chỉ LLM |
|---|---|---|
| Đúng trọn vẹn | 90,0% | 16,0% |
| F1 điều khoản (khớp tới điểm) | 93,6% | 3,7% |
| Dẫn văn bản hết hiệu lực (trên số căn cứ được dẫn) | 1,9% | 71,7% |
| Dẫn sai điều khoản | 5,6% | 96,2% |
| Độ trễ trung bình / p95 mỗi lượt | 14,8 s / 34,5 s | 5,1 s / 42,3 s |

## Vì sao baseline thấp

- **Dẫn văn bản hết hiệu lực:** 42/53 căn cứ baseline đưa ra là NĐ 100/2019, kể cả cho vụ việc năm 2025–2026 (đã
  được thay bằng NĐ 168/2024 từ 01/01/2025). Câu trả lời của baseline nhắc văn bản hết hiệu lực ở 14 tình huống.
- **Khi có dẫn NĐ 168 thì giữ số điều của NĐ 100:** vd. S06 dẫn "Điều 5 NĐ 168" cho lỗi ô tô đi ngược chiều — Điều 5
  là số điều của NĐ 100; trong NĐ 168 lỗi ô tô nằm ở Điều 6.
- **Không phân biệt phiên bản trong cùng NĐ 100:** S39 (năm 2023) dẫn đúng điểm a khoản 5 Điều 5 nhưng khung
  3–5 triệu là mức của NĐ 100 *trước* khi NĐ 123/2021 sửa thành 4–6 triệu.
- Baseline đúng ở nhóm không vi phạm (6/6) vì chỉ cần không đưa ra kết luận.

Đây là đúng loại rủi ro mà thiết kế "LLM không quyết định điều khoản" nhắm tới: kết luận của hệ thống do reasoner
chạy trên luật SWRL truy về văn bản có hiệu lực tại ngày vi phạm, nên sai sót của LLM ở tầng ngôn ngữ không trở thành
sai căn cứ pháp lý.

## Ablation

- **Bỏ entity linker** (chỉ khớp đúng nhãn node của ontology, không từ điển đồng nghĩa, không embedding): F1 điều
  khoản còn 7%, đúng trọn vẹn 14% (gần như chỉ còn nhóm không vi phạm). Hệ thống không nhận ra "ô tô", "xe máy",
  "vượt đèn đỏ"... nên liên tục hỏi lại loại xe và hành vi. Đây là tầng quan trọng nhất của Bài toán 2.
- **Bỏ normalizer** (chỉ đọc chữ số và ngày dd/mm/yyyy): đúng trọn vẹn giảm 16 điểm (90% → 74%); nhóm khác thời
  điểm còn 66,7% và đa lỗi 75% — hệ thống không đọc được "0,3 mg/l" (dấu phẩy thập phân), "hôm qua", "75 km/h"
  trong câu có nhiều số.
- **Bỏ fact inducer**: F1 điều khoản giảm 6,5 điểm, nhóm gián tiếp giảm mạnh nhất (87,5% → 50%), tỉ lệ sự kiện then
  chốt đúng giảm từ 93% xuống 70% — các hành vi phải suy ra ("rồ ga chạy khi CSGT vẫy", "quẹt ngã rồi chạy luôn")
  không còn được kết luận. Đây là phần LLM đóng góp cho Bài toán 1.
- **Bỏ kiểm chứng cụm từ**: không khác biệt trên bộ này — Gemini không tự thêm thông tin ở 50 tình huống. Tác dụng của
  bước này đã thấy khi thử Ollama/qwen2.5 ở Phase 4 (chặn 3/4 lần bịa loại xe, ngày). Bộ tình huống hiện chưa có ca
  gài LLM bịa thông tin nên không đo được — nên bổ sung ở vòng sau.

## Phân tích lỗi của hệ thống đầy đủ (13 tình huống chưa hoàn hảo)

| Tầng | Tình huống | Nguyên nhân | Hướng sửa |
|---|---|---|---|
| Hội thoại — hỏi xác nhận | S14, S21, S24, S29, S45 (lượt đầu) | Hành vi được ánh xạ bằng embedding (đúng) nên hệ thống hỏi xác nhận trước khi dùng — thận trọng theo thiết kế, nhưng cho thấy từ điển đồng nghĩa còn thiếu cách nói ("chạy vào làn xe buýt", "đèn đã đỏ vẫn cố chạy qua") | Bổ sung `synonyms.json`; nếu tính không kể câu xác nhận, tỉ lệ hỏi đúng lúc là 88% thay vì 76% |
| Hội thoại — hỏi không dứt | S45, S46 | Lời kể không vi phạm (dừng đúng đèn đỏ; uống rượu nhưng đi taxi) → không có sự kiện nào ánh xạ được nên hệ thống hỏi lại mãi | Khi người dùng trả lời mà hồ sơ không thay đổi, dừng hỏi và kết luận "không phát hiện vi phạm" kèm ghi chú |
| Hội thoại — hỏi sai hướng | S26 | Embedding gán "chạy luôn không dừng lại" thành gợi ý *tốc độ* → hỏi tốc độ và đặc điểm đường thay vì kết luận gây tai nạn bỏ trốn | Không dùng embedding cho gợi ý (gợi ý chỉ để chọn câu hỏi, sai thì gây hỏi thừa) |
| Hội thoại — bỏ sót câu hỏi | S37 | Gợi ý "CSGT" bị coi là đã mô tả hành vi → không hỏi "bạn vi phạm gì" | Gợi ý không phải hành vi: không tính khi xét "đã mô tả hành vi" |
| Thời điểm | S36 | "Từ 28/12/2024 đến 3/1/2025" chỉ được đọc ngày đầu → áp V2 (NĐ 100) thay vì hỏi ngày chính xác | Normalizer đọc khoảng "từ … đến …" để slot checker phát hiện khoảng vắt qua hai phiên bản |
| Suy luận | S10 | "Chở bạn không đội mũ, còn tôi có đội" → từ điển khớp cụm "không đội mũ bảo hiểm" cho cả người lái | Thêm cụm "ngồi sau không đội mũ…" vào từ điển (khớp dài nhất thắng) |
| Ánh xạ | S35 | "Không có giấy tờ xe" được hiểu thẳng là không có đăng ký xe, thay vì hỏi giấy tờ nào và có hay chỉ quên mang | Bỏ cụm mơ hồ khỏi mục "không có đăng ký", để gợi ý "giấy tờ" kích hoạt câu hỏi |
| Hội thoại | S25 | Hỏi lại "có kinh doanh vận tải không" dù lời kể có "chở hàng thuê cho ứng dụng giao hàng" (vẫn kết luận đúng) | Bổ sung ví dụ cho fact inducer / từ điển |

Khung phạt đúng 100% khi điều khoản đúng — mọi sai sót nằm ở tầng hiểu ngôn ngữ và hội thoại, không nằm ở cơ sở
tri thức (luật SWRL, sổ đăng ký điều khoản).

## Lưu ý khi đọc số liệu

- **Độ trễ** gồm cả thời gian chờ do giới hạn 10 lượt gọi/phút của gói Gemini miễn phí (mỗi lượt gọi LLM tối đa 3
  lần: trích xuất, suy ra sự kiện, diễn đạt) và khoảng 3 giây chạy HermiT. Độ trễ của các ablation **không so sánh
  được** với hệ thống đầy đủ vì phần lớn lượt gọi đã có trong cache và ablation không chạy bước diễn đạt.
- 50 tình huống do nhóm phát triển soạn; nhãn điều khoản tra từ cùng bảng hành vi ↔ điều khoản mà hệ thống dùng (bảng
  đã kiểm chứng với văn bản gốc). Phép đo vì vậy kiểm tra hệ thống có **đi tới đúng hành vi** từ lời kể hay không,
  không kiểm tra lại bảng đó.
- Chạy một lần với temperature 0; phản hồi LLM được cache nên chạy lại cho cùng kết quả.
