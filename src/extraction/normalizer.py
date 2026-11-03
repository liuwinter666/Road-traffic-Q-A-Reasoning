"""Chuẩn hóa cụm từ tiếng Việt thành số, đơn vị, ngày — tất định, không dùng LLM.

Ví dụ: "80 cây" → 80 km/h; "không phẩy ba miligam" → 0,3 (mg/L khí thở, giả định theo độ lớn);
"50mg/100ml máu" → 50 (mg/100 mL máu); "110 phân khối" → 110 cm3; "1500W" → 1,5 kW;
"mười lăm tuổi" → 15; "sinh năm 2k10" + ngày vi phạm → tuổi; "tối qua", "tuần trước", "10/3/2025",
"tháng 3 năm 2026" → khoảng ngày (kèm độ chính xác).

Mỗi kết quả có ``gia_dinh`` (giả định đã dùng) để câu trả lời nêu rõ; không chắc thì trả None để
slot checker hỏi lại.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Văn bản
# ---------------------------------------------------------------------------


def bo_dau(s: str) -> str:
    """Bỏ dấu tiếng Việt (đ → d) để so khớp không phân biệt dấu."""
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def chuan_hoa_chu(s: str) -> str:
    """Chữ thường, gộp khoảng trắng, chuẩn Unicode NFC."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s).lower()).strip()


# ---------------------------------------------------------------------------
# Số viết bằng chữ
# ---------------------------------------------------------------------------

DIGITS = {"không": 0, "linh": 0, "lẻ": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5,
          "lăm": 5, "nhăm": 5, "sáu": 6, "bảy": 7, "bẩy": 7, "tám": 8, "chín": 9}
NUM_WORDS = set(DIGITS) | {"mười", "mươi", "trăm", "nghìn", "ngàn", "phẩy", "chấm"}


def _int_words(ws: list[str]) -> int | None:
    """'một trăm hai mươi' → 120; 'mười lăm' → 15; 'hai lăm' → 25 (cách nói rút gọn)."""
    if not ws:
        return None
    if all(w in DIGITS for w in ws) and len(ws) > 1:      # "hai lăm" → 25, "không tám" → 8
        return int("".join(str(DIGITS[w]) for w in ws))
    # Đọc theo hàng: chữ số đứng trước "trăm"/"mươi" là hệ số của hàng đó
    total, cur, last = 0, 0, None
    for w in ws:
        if w in DIGITS:
            last = DIGITS[w]
        elif w == "mười":
            cur += 10
            last = None
        elif w == "mươi":
            cur += (last if last is not None else 1) * 10
            last = None
        elif w == "trăm":
            cur += (last if last is not None else 1) * 100
            last = None
        elif w in ("nghìn", "ngàn"):
            total += (cur + (last or 0) or 1) * 1000
            cur, last = 0, None
        else:
            return None
    return total + cur + (last or 0)


def so_tu_chu(text: str) -> float | None:
    """Đọc số đầu tiên trong chuỗi chữ: 'tám mươi' → 80, 'không phẩy hai lăm' → 0.25."""
    ws = [w for w in chuan_hoa_chu(text).split() if w in NUM_WORDS]
    if not ws:
        return None
    if "phẩy" in ws or "chấm" in ws:
        k = ws.index("phẩy") if "phẩy" in ws else ws.index("chấm")
        a, b = ws[:k], ws[k + 1:]
        ia = _int_words(a) if a else 0
        if not b or ia is None:
            return None
        if all(w in DIGITS for w in b):
            frac = "".join(str(DIGITS[w]) for w in b)
        else:
            ib = _int_words(b)
            if ib is None:
                return None
            frac = str(ib)
        return float(f"{ia}.{frac}")
    v = _int_words(ws)
    return float(v) if v is not None else None


RE_NUM = re.compile(r"(\d+(?:[.,]\d+)?)")


def so(text: str) -> float | None:
    """Số đầu tiên trong chuỗi (chữ số, dấu phẩy thập phân kiểu Việt, hoặc số bằng chữ)."""
    t = chuan_hoa_chu(text)
    if m := RE_NUM.search(t):
        raw = m.group(1)
        # "1.500" (phân cách hàng nghìn) vs "0.3" (thập phân): nhóm 3 chữ số sau dấu chấm → hàng nghìn
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", raw):
            return float(raw.replace(".", ""))
        return float(raw.replace(",", "."))
    return so_tu_chu(t)


# ---------------------------------------------------------------------------
# Đại lượng
# ---------------------------------------------------------------------------


@dataclass
class DaiLuong:
    gia_tri: float
    don_vi: str
    goc: str
    gia_dinh: list[str] = field(default_factory=list)


def toc_do(text: str) -> DaiLuong | None:
    """'80 cây', '80km/h', 'tám mươi cây số giờ', '120 km' → km/h."""
    v = so(text)
    if v is None:
        return None
    g = [] if re.search(r"km|cây|ki ?lô ?mét|kilomet", chuan_hoa_chu(text)) else \
        ["Không ghi đơn vị — hiểu là km/h"]
    return DaiLuong(v, "km/h", text, g)


def nong_do_con(text: str) -> tuple[DaiLuong | None, str | None]:
    """→ (đại lượng, loại 'khi_tho' (mg/L) | 'mau' (mg/100 mL) | None nếu không đoán được)."""
    t = chuan_hoa_chu(text)
    v = so(t)
    if v is None:
        return None, None
    if re.search(r"100\s*(ml|mililit|mi-li-lít|mililít)|trong máu|/\s*100|máu", t):
        return DaiLuong(v, "mg/100mL", text), "mau"
    if re.search(r"(mg|miligam|mi-li-gam)\s*(/|trên|một|1)?\s*(1\s*)?(l\b|lít|lit)|khí thở|hơi thở|thổi", t):
        return DaiLuong(v, "mg/L", text), "khi_tho"
    # Không rõ mẫu số: phân biệt theo độ lớn (mg/L khí thở thường < 2; mg/100 mL máu thường > 10)
    if v < 5:
        return DaiLuong(v, "mg/L", text, [f"Không rõ đơn vị — {v} được hiểu là mg/L khí thở"]), "khi_tho"
    if v >= 10:
        return DaiLuong(v, "mg/100mL", text, [f"Không rõ đơn vị — {v} được hiểu là mg/100 mL máu"]), "mau"
    return None, None


def dung_tich(text: str) -> DaiLuong | None:
    """'110 phân khối', '125cc', '50 phân', '150 cm3' → cm3."""
    t = chuan_hoa_chu(text)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(cc|cm3|cm³|phân khối|phân|phan khoi)", t)
    if m:
        return DaiLuong(float(m.group(1).replace(",", ".")), "cm3", text)
    v = so(t)
    return DaiLuong(v, "cm3", text, ["Không ghi đơn vị — hiểu là cm3"]) if v is not None and v >= 30 else None


def cong_suat(text: str) -> DaiLuong | None:
    """'4kW', '1500W', '1,2 kilôoát' → kW."""
    t = chuan_hoa_chu(text)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kw|kilô ?oát|kilowatt|w|oát|watt)\b", t)
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return DaiLuong(v / 1000 if m.group(2) in ("w", "oát", "watt") else v, "kW", text)


def tuoi(text: str, ngay_vi_pham: date | None = None, hom_nay: date | None = None) -> DaiLuong | None:
    """'15 tuổi', 'mười lăm tuổi', 'sinh năm 2010', 'sinh 2k10' → tuổi (năm)."""
    t = chuan_hoa_chu(text)
    m = re.search(r"(?:sinh|năm sinh)\D*(?:năm\s*)?(\d{4}|2k\d{1,2})", t) or re.search(r"\b(2k\d{1,2})\b", t)
    if m:
        y = m.group(1)
        year = 2000 + int(y[2:]) if y.startswith("2k") else int(y)
        ref = ngay_vi_pham or hom_nay or date.today()
        return DaiLuong(float(ref.year - year), "tuổi", text,
                        [f"Tính tuổi theo năm sinh {year} (có thể chênh 1 tuổi tùy ngày sinh)"])
    if "tuổi" in t or re.fullmatch(r"\d{1,2}", t):
        v = so(t)
        return DaiLuong(v, "tuổi", text) if v is not None else None
    return None


# ---------------------------------------------------------------------------
# Thời điểm
# ---------------------------------------------------------------------------


@dataclass
class ThoiDiem:
    tu: date
    den: date
    do_chinh_xac: str            # ngay | thang | nam | tuong_doi
    goc: str
    gia_dinh: list[str] = field(default_factory=list)

    @property
    def ngay(self) -> date | None:
        return self.tu if self.tu == self.den else None


def _month_end(y: int, m: int) -> date:
    return (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))


def thoi_diem(text: str, hom_nay: date | None = None) -> ThoiDiem | None:
    """Ngày tuyệt đối hoặc tương đối so với ``hom_nay``."""
    today = hom_nay or date.today()
    t = chuan_hoa_chu(text)
    if m := re.search(r"(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{2,4})", t):
        d, mo, y = map(int, m.groups())
        y = y + 2000 if y < 100 else y
        dd = date(y, mo, d)
        return ThoiDiem(dd, dd, "ngay", text)
    if m := re.search(r"ngày\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})", t):
        d, mo, y = map(int, m.groups())
        dd = date(y, mo, d)
        return ThoiDiem(dd, dd, "ngay", text)
    if m := re.search(r"(?:ngày\s*)?(\d{1,2})\s*[/\-]\s*(\d{1,2})\b(?!\s*[/\-]\s*\d)", t):
        d, mo = map(int, m.groups())
        y = today.year if date(today.year, mo, d) <= today else today.year - 1
        dd = date(y, mo, d)
        return ThoiDiem(dd, dd, "ngay", text, [f"Không ghi năm — hiểu là năm {y}"])
    if m := re.search(r"tháng\s*(\d{1,2})\s*(?:/|năm)\s*(\d{4})", t):
        mo, y = map(int, m.groups())
        return ThoiDiem(date(y, mo, 1), _month_end(y, mo), "thang", text)
    if m := re.search(r"(?:năm\s*)(\d{4})\b", t):
        y = int(m.group(1))
        return ThoiDiem(date(y, 1, 1), date(y, 12, 31), "nam", text)
    rel = [(r"hôm kia", 2), (r"hôm qua|tối qua|đêm qua|sáng qua|chiều qua|trưa qua", 1),
           (r"hôm nay|sáng nay|chiều nay|tối nay|trưa nay|vừa nãy|vừa rồi|lúc nãy|ban nãy", 0)]
    for pat, k in rel:
        if re.search(pat, t):
            dd = today - timedelta(days=k)
            return ThoiDiem(dd, dd, "tuong_doi", text, [f"'{text}' được hiểu là ngày {dd:%d/%m/%Y}"])
    if re.search(r"tuần trước", t):
        return ThoiDiem(today - timedelta(days=13), today - timedelta(days=7), "tuong_doi", text,
                        ["'tuần trước' — không rõ ngày cụ thể"])
    if re.search(r"tháng trước", t):
        y, mo = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        return ThoiDiem(date(y, mo, 1), _month_end(y, mo), "thang", text, ["'tháng trước' — không rõ ngày cụ thể"])
    if re.search(r"năm ngoái|năm trước", t):
        y = today.year - 1
        return ThoiDiem(date(y, 1, 1), date(y, 12, 31), "nam", text, ["'năm ngoái' — không rõ ngày cụ thể"])
    return None
