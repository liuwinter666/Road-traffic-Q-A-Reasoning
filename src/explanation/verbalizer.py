"""Verbalizer: LLM viết câu trả lời CHỈ từ trace, sau đó kiểm tra chống bịa (tất định).

Kiểm tra (``kiem_tra``) trên văn bản LLM viết:
  * Mọi tham chiếu "điểm … khoản … Điều …" (kèm tên văn bản nếu có) phải khớp một căn cứ trong trace
    (điều khoản kết luận, chế tài, căn cứ ngưỡng/định nghĩa/tra bảng, căn cứ chung của Luật XLVPHC...).
  * Văn bản được nhắc (Nghị định/NĐ số…, Thông tư số…, Luật …) phải thuộc trace hoặc phiên bản pháp lý đã áp dụng
    — chặn dẫn văn bản hết hiệu lực (vd. nhắc NĐ 100 khi vụ việc áp V4).
  * Số tiền, số điểm bị trừ, số tháng tước GPLX, mã quy tắc R… phải có trong trace.
  * Đầy đủ: mỗi hành vi trong trace phải được nêu kèm đúng điều khoản và mức đề xuất; có câu "tham khảo".
Sai → gọi lại LLM MỘT lần kèm danh sách lỗi; vẫn sai (hoặc LLM lỗi) → dùng bản trình bày tất định.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from loguru import logger

from src.explanation.tracer import Trace
from src.llm.client import LLMClient, LLMError, get_llm_client
from src.llm.prompts import load_prompt

RE_THAM_CHIEU = re.compile(
    r"(?:điểm\s+([a-zđ]{1,2})\s*,?\s+)?(?:khoản\s+(\d+)\s*,?\s+)?Điều\s+(\d+)", re.IGNORECASE)
RE_ID_TRACE = re.compile(r"^([A-Z]+\d*)-D(\d+)(?:-K(\d+))?(?:-([a-z]+))?$")
VAN_BAN_THEO_TEN = [
    (re.compile(r"^\s*,?\s*(?:của\s+)?(?:Nghị định|NĐ)\s*(?:số\s*)?(\d+)", re.I), lambda m: f"ND{m.group(1)}"),
    (re.compile(r"^\s*,?\s*(?:của\s+)?(?:Thông tư|TT)\s*(?:số\s*)?(\d+)", re.I), lambda m: f"TT{m.group(1)}"),
    (re.compile(r"^\s*,?\s*(?:của\s+)?Luật\s+(?:số\s+)?(?:Xử lý vi phạm hành chính|15/2012)", re.I), lambda m: "LXLVPHC"),
    (re.compile(r"^\s*,?\s*(?:của\s+)?Luật\s+(?:số\s+)?(?:Trật tự,? an toàn giao thông|36/2024)", re.I), lambda m: "LTTATGT"),
    (re.compile(r"^\s*,?\s*(?:của\s+)?Luật\s+(?:số\s+)?(?:Giao thông đường bộ|23/2008)", re.I), lambda m: "GTDB2008"),
]
RE_VAN_BAN_TU_DO = [
    (re.compile(r"(?:Nghị định|NĐ)\s*(?:số\s*)?(\d{2,3})\b", re.I), "ND{}"),
    (re.compile(r"(?:Thông tư|TT)\s*(?:số\s*)?(\d{2})\b", re.I), "TT{}"),
]
# Số tiền: từ 1.000.000 trở lên (dạng nhóm 3 chữ số) luôn coi là tiền; số nhỏ hơn (500.000) khi có "đồng" theo sau
RE_TIEN_LON = re.compile(r"\b\d{1,3}(?:\.\d{3}){2,}\b|\b\d{1,3}(?:\.\d{3})+(?=\s*(?:đồng|VNĐ|vnđ|đ\b))")
RE_TIEN_CHU = re.compile(r"(\d+(?:[.,]\d+)?)\s*(triệu|nghìn|ngàn)\b", re.I)
RE_DIEM = re.compile(r"\b(\d+)\s*điểm\b")
RE_THANG = re.compile(r"(?<!ngày )\b(\d+)\s*tháng\b(?!\s*\d)")
RE_QUY_TAC = re.compile(r"\bR\d{3}\b")
RE_MA_PHAN_TU = re.compile(r"\b(?:ND\d+|LXLVPHC|LTTATGT|GTDB2008|TT\d+)-D\d+(?:-K\d+)?(?:-[a-z]{1,2})?\b")


def _dd(x: str | None) -> str | None:
    return None if x is None else x.lower().replace("đ", "dd")


def _so_tien(text: str) -> set[int]:
    out = {int(m.group(0).replace(".", "")) for m in RE_TIEN_LON.finditer(text)}
    for m in RE_TIEN_CHU.finditer(text):
        he_so = 1_000_000 if m.group(2).lower() == "triệu" else 1_000
        out.add(round(float(m.group(1).replace(",", ".")) * he_so))
    return out


def tham_chieu(text: str) -> list[dict]:
    """Các tham chiếu điều khoản trong ``text``: {diem, khoan, dieu, van_ban, chuoi}."""
    out = []
    for m in RE_THAM_CHIEU.finditer(text):
        vb = None
        sau = text[m.end(): m.end() + 80]
        for rx, f in VAN_BAN_THEO_TEN:
            if mm := rx.match(sau):
                vb = f(mm)
                break
        out.append({"diem": _dd(m.group(1)), "khoan": m.group(2), "dieu": m.group(3), "van_ban": vb,
                    "chuoi": m.group(0) + (f" ({vb})" if vb else "")})
    return out


@dataclass
class KetQuaKiemTra:
    hop_le: bool
    loi: list[str] = field(default_factory=list)


def kiem_tra(text: str, trace: Trace) -> KetQuaKiemTra:
    """Đối chiếu câu trả lời với trace (xem docstring module)."""
    loi: list[str] = []
    cho_phep = []
    for i in trace.can_cu_hop_le():
        if m := RE_ID_TRACE.match(i):
            cho_phep.append({"van_ban": m.group(1), "dieu": m.group(2), "khoan": m.group(3), "diem": m.group(4)})
    van_ban_ok = {c["van_ban"] for c in cho_phep} | set(trace.phien_ban.get("van_ban") or [])
    trace_txt = json.dumps(trace.to_dict(), ensure_ascii=False)
    # tham chiếu nằm sẵn trong nguyên văn của trace (vd. "khoản 10 Điều 7" trong câu chế tài) cũng được chép lại
    cho_phep += [t for t in tham_chieu(trace_txt)]

    def khop(t: dict, c: dict) -> bool:
        return c["dieu"] == t["dieu"] and (t["khoan"] is None or c["khoan"] == t["khoan"]) and \
            (t["diem"] is None or c["diem"] == t["diem"]) and (t["van_ban"] is None or c["van_ban"] == t["van_ban"])

    tcs = tham_chieu(text)
    for t in tcs:
        if not any(khop(t, c) for c in cho_phep):
            loi.append(f"Tham chiếu không có trong trace: “{t['chuoi']}”")
    for rx, fmt in RE_VAN_BAN_TU_DO:
        for m in rx.finditer(text):
            vb = fmt.format(m.group(1))
            if vb not in van_ban_ok:
                loi.append(f"Văn bản không thuộc trace/phiên bản áp dụng: “{m.group(0)}”")
    for ten, vb in (("Luật Giao thông đường bộ", "GTDB2008"), ("Luật Xử lý vi phạm hành chính", "LXLVPHC"),
                    ("Luật Trật tự, an toàn giao thông", "LTTATGT")):
        if ten.lower() in text.lower() and vb not in van_ban_ok:
            loi.append(f"Văn bản không thuộc trace: “{ten}”")

    tien_ok = trace.so_tien_hop_le() | _so_tien(trace_txt)
    for x in sorted(_so_tien(text) - tien_ok):
        loi.append(f"Số tiền không có trong trace: {x:,}".replace(",", "."))
    diem_ok = {int(x) for x in RE_DIEM.findall(trace_txt)} | {k.tru_diem for k in trace.ket_luan if k.tru_diem} \
        | ({trace.tru_diem_ap_dung} if trace.tru_diem_ap_dung else set())
    diem_ok |= {c["gia_tri"].get("so_diem") for k in trace.ket_luan for c in k.che_tai if c["loai"] == "tru_diem"}
    for x in sorted({int(x) for x in RE_DIEM.findall(text)} - diem_ok):
        loi.append(f"Số điểm trừ không có trong trace: {x}")
    thang_ok = {int(x) for x in RE_THANG.findall(trace_txt)}
    for k in trace.ket_luan:
        for c in k.che_tai:
            thang_ok |= {v for kk, v in c["gia_tri"].items() if kk.endswith("thang")}
    for x in sorted({int(x) for x in RE_THANG.findall(text)} - thang_ok):
        loi.append(f"Thời hạn (tháng) không có trong trace: {x}")
    # Mã quy tắc R… và mã phần tử (ND168-D7-K7-d) là định danh nội bộ: chỉ hiện ở tab Cây suy luận / Chi tiết,
    # câu trả lời viết căn cứ bằng chữ
    for x in sorted(set(RE_QUY_TAC.findall(text))):
        loi.append(f"Không đưa mã quy tắc nội bộ vào câu trả lời: {x}")
    for x in sorted(set(RE_MA_PHAN_TU.findall(text))):
        loi.append(f"Không đưa mã điều khoản nội bộ vào câu trả lời (viết bằng chữ): {x}")

    # Đầy đủ
    for k in trace.ket_luan:
        m = RE_ID_TRACE.match(k.dieu_khoan.id)
        c = {"van_ban": m.group(1), "dieu": m.group(2), "khoan": m.group(3), "diem": m.group(4)}
        if not any(t["dieu"] == c["dieu"] and t["khoan"] == c["khoan"] and t["diem"] == c["diem"] for t in tcs):
            loi.append(f"Thiếu căn cứ của hành vi “{k.ten}”: {k.dieu_khoan.trich_dan}")
        if k.muc_de_xuat and k.muc_de_xuat not in _so_tien(text):
            loi.append(f"Thiếu mức đề xuất {k.muc_de_xuat:,} đồng của hành vi “{k.ten}”".replace(",", "."))
    if "tham khảo" not in text.lower():
        loi.append("Thiếu câu lưu ý kết quả chỉ mang tính tham khảo")
    return KetQuaKiemTra(not loi, list(dict.fromkeys(loi)))


# ---------------------------------------------------------------------------
# Trace rút gọn cho LLM
# ---------------------------------------------------------------------------

def _tien(x) -> str | None:
    return None if x is None else f"{x:,}".replace(",", ".") + " đồng"


def _che_tai_chu(c: dict) -> str:
    g = c["gia_tri"]
    ten = {"tuoc_gplx": "Tước quyền sử dụng giấy phép lái xe", "tru_diem": "Trừ điểm giấy phép lái xe",
           "tich_thu_phuong_tien": "Tịch thu phương tiện", "tich_thu": "Tịch thu", "thu_hoi": "Thu hồi"}[c["loai"]]
    v = (f"từ {g['tu_thang']} tháng đến {g['den_thang']} tháng" if c["loai"] == "tuoc_gplx" else
         f"{g['so_diem']} điểm" if c["loai"] == "tru_diem" else g.get("doi_tuong", ""))
    tt = {"ap_dung": "áp dụng", "ap_dung_do_thoa_dieu_kien": "áp dụng (đã thỏa điều kiện)",
          "neu_thoa_dieu_kien": "nếu thỏa điều kiện", "khong_ap_dung": "không áp dụng"}[c["trang_thai"]]
    dk = f"; điều kiện: {c['dieu_kien']}" if c["dieu_kien"] else ""
    return f"{ten} {v} — {tt}{dk} — căn cứ {c['trich_dan']}"


def _tinh_tiet_chu(t: dict, nguon: dict) -> str:
    """"Tự nguyện khai báo, thành thật hối lỗi (khoản 2 Điều 9 Luật số 15/2012/QH13) — suy ra từ lời kể: “…”"."""
    s = t["nhan"] + (f" ({t['can_cu']['trich_dan']})" if t.get("can_cu") else "")
    for sk in t.get("su_kien") or []:
        if sk.get("nguon"):
            s += f" — {nguon.get(sk['nguon'], sk['nguon'])}" + (f": “{sk['bang_chung']}”" if sk.get("bang_chung") else "")
            break
    return s


def trace_cho_llm(tr: Trace) -> dict:
    """Bản rút gọn, đã định dạng sẵn (tiền, chế tài) để LLM chép đúng."""
    from src.explanation.tracer import _mo_ta_cay

    nguon = {"truc_tiep": "người dùng nêu", "suy_ra": "suy ra từ lời kể", "xac_nhan": "người dùng đã xác nhận",
             "tra_bang": "tra bảng tốc độ của thông tư", "tinh_toan": "tính toán",
             "xep_loai": "xếp loại xe theo dung tích/công suất quy định trong luật"}
    return {
        "phien_ban_phap_ly": tr.phien_ban["ghi_chu"],
        "su_kien_dau_vao": [{"su_kien": n.mo_ta, "nguon": nguon.get(n.nguon, n.nguon),
                             **({"trich_loi_nguoi_dung": n.bang_chung} if n.bang_chung else {}),
                             **({"can_cu": [c.trich_dan for c in n.can_cu]} if n.can_cu else {})}
                            for n in tr.su_kien],
        "hanh_vi_vi_pham": [{
            "hanh_vi": k.ten,
            "can_cu": k.dieu_khoan.trich_dan,
            "nguyen_van": k.dieu_khoan.nguyen_van.split("\n")[-1],
            "hinh_thuc_chinh": {"phat_tien": "phạt tiền", "canh_cao": "cảnh cáo",
                                "khong_xu_phat": "không xử phạt"}.get(k.hinh_thuc_chinh, k.hinh_thuc_chinh),
            "khung_phat": f"từ {_tien(k.khung_phat[0])} đến {_tien(k.khung_phat[1])}" if k.khung_phat else None,
            "muc_de_xuat": _tien(k.muc_de_xuat),
            "ly_do_muc_de_xuat": k.ly_do,
            "hinh_thuc_bo_sung": [_che_tai_chu(c) for c in k.che_tai if c["trang_thai"] != "khong_ap_dung"],
            "tinh_tiet_tang_nang": [_tinh_tiet_chu(t, nguon) for t in k.tinh_tiet_tang],
            "tinh_tiet_giam_nhe": [_tinh_tiet_chu(t, nguon) for t in k.tinh_tiet_giam],
            "chuoi_suy_luan": ["; ".join(_mo_ta_cay(n, nguon=True) for n in q.dieu_kien)
                               for q in k.quy_tac],
            "can_cu_khac": [c.trich_dan for c in k.can_cu_khac],
        } for k in tr.ket_luan],
        "khong_ap_dung_do_loai_tru": [{"hanh_vi": x["ten"], "ly_do": x["ly_do"]} for x in tr.loai_tru],
        "nguoi_khong_du_dieu_kien": [x["mo_ta"] for x in tr.nguoi_khong_du_dieu_kien],
        "tong_tien_de_xuat": _tien(tr.tong_tien_de_xuat) if len(tr.ket_luan) > 1 else None,
        "tru_diem_giay_phep_lai_xe": f"{tr.tru_diem_ap_dung} điểm" if tr.tru_diem_ap_dung else None,
        "can_cu_chung": [f"{c.trich_dan}: {c.nguyen_van}" for c in tr.can_cu_chung],
        "ghi_chu": tr.ghi_chu,
    }


@dataclass
class KetQuaDienDat:
    van_ban: str
    nguon: str                      # llm | tat_dinh
    kiem_tra: KetQuaKiemTra | None = None
    so_lan_goi: int = 0
    ly_do_du_phong: str | None = None


class Verbalizer:
    def __init__(self, client: LLMClient | None = None, prompt_version: int | None = None):
        self.client = client or get_llm_client()
        self.prompt = load_prompt("verbalize", prompt_version)

    def dien_dat(self, trace: Trace, du_phong: str) -> KetQuaDienDat:
        """Câu trả lời từ ``trace``; ``du_phong`` là bản tất định dùng khi LLM lỗi hoặc không qua kiểm tra."""
        js = json.dumps(trace_cho_llm(trace), ensure_ascii=False, indent=1)
        phan_hoi, kt, n = "", None, 0
        for lan in range(2):
            n += 1
            try:
                text = self.client.generate(self.prompt.render(trace=js, phan_hoi=phan_hoi), system=self.prompt.system)
            except LLMError as e:
                logger.warning("Verbalizer lỗi LLM: {}", e)
                return KetQuaDienDat(du_phong, "tat_dinh", kt, n, f"lỗi LLM: {e}")
            kt = kiem_tra(text, trace)
            if kt.hop_le:
                return KetQuaDienDat(text.strip(), "llm", kt, n)
            logger.warning("Verbalizer lần {} không qua kiểm tra: {}", lan + 1, kt.loi)
            phan_hoi = ("\nBẢN TRƯỚC KHÔNG HỢP LỆ vì:\n" + "\n".join(f"- {x}" for x in kt.loi) +
                        "\nViết lại, chỉ dùng thông tin trong TRACE.\n")
        return KetQuaDienDat(du_phong, "tat_dinh", kt, n, "không qua kiểm tra chống bịa sau 2 lần")
