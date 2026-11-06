"""Thành phần thay thế cho thí nghiệm ablation (mục 10 đặc tả: bỏ normalizer, bỏ entity linker).

* ``NormalizerDonGian`` — thay ``src/extraction/normalizer.py``: chỉ đọc chữ số Ả-rập (dấu chấm thập phân), ngày
  dạng dd/mm/yyyy; không hiểu "80 cây", "0,3" (dấu phẩy), số viết bằng chữ, "tối qua", đơn vị nói tắt. Mô phỏng
  hệ thống chỉ ép kiểu thô đầu ra LLM.
* ``linker_nhan_ontology()`` — thay entity linker (từ điển đồng nghĩa + embedding): chỉ khớp khi lời kể chứa ĐÚNG
  nhãn tiếng Việt của node trong ontology; không có gợi ý (``_CO_CON``...), không embedding.
"""

from __future__ import annotations

import json
import re
import tempfile
from datetime import date
from pathlib import Path

from src.extraction.normalizer import DaiLuong, ThoiDiem

RE_SO = re.compile(r"\d+(?:\.\d+)?")


def _so(text: str) -> float | None:
    m = RE_SO.search(text or "")
    return float(m.group(0)) if m else None


class NormalizerDonGian:
    """Cùng giao diện với các hàm của ``normalizer`` mà ``xay_dung_ho_so`` dùng."""

    def thoi_diem(self, text: str, hom_nay: date | None = None) -> ThoiDiem | None:
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
        if not m:
            return None
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
        return ThoiDiem(d, d, "ngay", text)

    def tuoi(self, text, ngay_vi_pham=None, hom_nay=None):
        v = _so(text)
        return DaiLuong(v, "tuổi", text) if v is not None else None

    def dung_tich(self, text):
        v = _so(text)
        return DaiLuong(v, "cm3", text) if v is not None else None

    def cong_suat(self, text):
        v = _so(text)
        return DaiLuong(v, "kW", text) if v is not None else None

    def toc_do(self, text):
        v = _so(text)
        return DaiLuong(v, "km/h", text) if v is not None else None

    def nong_do_con(self, text):
        v = _so(text)
        t = (text or "").lower()
        if v is None:
            return None, None
        if "mg/l" in t or "mg/lít" in t:
            return DaiLuong(v, "mg/L", text), "khi_tho"
        if "100ml" in t.replace(" ", "") or "máu" in t:
            return DaiLuong(v, "mg/100mL", text), "mau"
        return None, None


def linker_nhan_ontology():
    """EntityLinker chỉ có nhãn ontology làm "từ điển" (không đồng nghĩa, không gợi ý, không embedding)."""
    from src.config import PROCESSED_DIR
    from src.explanation.tracer import nhan
    from src.extraction.entity_linker import EntityLinker

    syn = json.loads((PROCESSED_DIR / "synonyms.json").read_text(encoding="utf-8"))
    tu_dien: dict = {}
    for kieu in ("xe", "duong", "dau_hieu", "tinh_tiet"):
        tu_dien[kieu] = {node: [nhan(node).lower()] for node in syn[kieu]}
    tu_dien["dac_diem_duong"] = {}
    tu_dien["goi_y"] = {}
    f = Path(tempfile.gettempdir()) / "synonyms_chi_nhan_ontology.json"
    f.write_text(json.dumps(tu_dien, ensure_ascii=False), encoding="utf-8")
    return EntityLinker(synonyms_path=f, embedder=None)
