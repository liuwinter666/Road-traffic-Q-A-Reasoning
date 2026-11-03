"""Đo ngưỡng embedding của entity linker trên tập cụm từ có nhãn (cụm KHÔNG khớp từ điển đồng nghĩa).

    python -m evaluation.calib_entity_link

In top-1 node + độ tương đồng cho từng cụm và số liên kết đúng / sai / bỏ sót theo từng ngưỡng. Tập nhỏ dưới đây
là tập khởi đầu (Phase 5); Phase 8 mở rộng từ data/test/scenarios.jsonl.
"""
import sys
from loguru import logger; logger.remove()
from src.extraction.entity_linker import EntityLinker
lk = EntityLinker(threshold=0.0)
# (cụm từ không khớp từ điển, node đúng hoặc None nếu không nên liên kết)
cases = [
    ("đi tiếp luôn", None), ("hoảng quá nên chạy mất", None), ("tôi về nhà ngủ", None), ("đi chơi với bạn", None),
    ("chở vợ đi chợ", None), ("trời mưa to", None), ("đường rất đông", None), ("bị phạt", None),
    ("mua xe mới", None), ("đi làm muộn", None), ("bấm còi inh ỏi", None), ("dừng xe bên đường", None),
    ("va quẹt nhẹ với một bà đi xe đạp", "_TAI_NAN"), ("tông vào đuôi xe tải", "_TAI_NAN"),
    ("làm mấy chai bia với bạn", "_CO_CON"), ("tối qua nhậu hơi xỉn", "_CO_CON"),
    ("phóng như bay", "_TOC_DO"), ("chạy ẩu tốc độ cao trên phố", "_TOC_DO"),
    ("không có bằng lái", "KhongCoGPLX"), ("để quên bằng lái ở nhà", "KhongMangTheoGPLX"),
    ("cầm điện thoại nhắn tin lúc chạy xe", "DungTaySuDungDienThoai"), ("chạy vào đường cấm ngược chiều", "DiNguocChieu"),
    ("không cài dây an toàn", "KhongThatDayAnToan"), ("vượt khi đèn đã chuyển đỏ", "KhongChapHanhDenTinHieu"),
    ("chửi mắng anh cảnh sát", "langMaNguoiThiHanhCongVu"), ("đánh võng trên cầu", "LangLachDanhVong"),
]
kinds = ["dau_hieu", "tinh_tiet", "goi_y"]
rows = []
for m, gold in cases:
    r = lk._embed_link(m, kinds)
    top = r[0] if r else None
    rows.append((m, gold, top.node if top else None, round(top.diem, 3) if top else None))
for x in sorted(rows, key=lambda r: -(r[3] or 0)):
    ok = "OK " if x[1] == x[2] else ("NEG" if x[1] is None else "SAI")
    print(ok, x[3], "|", x[0], "→", x[2], "(đúng:", x[1], ")")
for t in (0.65, 0.7, 0.72, 0.75, 0.78, 0.8, 0.85):
    tp = sum(1 for m, g, p, s in rows if g and p == g and s >= t)
    fp = sum(1 for m, g, p, s in rows if s >= t and p != g)
    fn = sum(1 for m, g, p, s in rows if g and not (p == g and s >= t))
    print(f"ngưỡng {t}: đúng {tp}, sai/bịa {fp}, bỏ sót {fn}")
