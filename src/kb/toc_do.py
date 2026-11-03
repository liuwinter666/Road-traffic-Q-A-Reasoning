"""Tra tốc độ tối đa cho phép khi không có biển báo, theo thông tư có hiệu lực tại ngày vi phạm.

Số liệu lấy từ ``data/processed/speed_limits.json`` (sinh bởi ``python -m src.ingest.speed_limits`` từ bảng/câu
trong TT 31/2019 và TT 38/2024; không ghi số trong code). Thông tư được chọn qua
``temporal.chon_van_ban_bo_tro("toc_do_toi_da", ngay)``.

Dùng chung cho ``slot_checker`` (có tra được không → không cần hỏi) và ``fact_builder`` (điền
``tocDoToiDaChoPhep`` kèm căn cứ). Đây là phép TRA BẢNG, không phải kết luận vi phạm.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from src.config import PROCESSED_DIR
from src.kb.temporal import chon_van_ban_bo_tro

SPEED_FILE = PROCESSED_DIR / "speed_limits.json"


@dataclass
class TraCuuTocDo:
    gia_tri: float | None                 # km/h; None nếu không tra được
    thieu: str | None = None              # trường cần hỏi thêm: loai_xe | dung_tich | dac_diem_duong | toc_do_toi_da
    can_cu: dict | None = None            # {"id", "nguyen_van"}
    van_ban: str | None = None            # TT31 | TT38
    nhom_xe: str | None = None
    ghi_chu: str | None = None

    @property
    def tra_duoc(self) -> bool:
        return self.gia_tri is not None


@lru_cache(maxsize=1)
def _bang() -> dict[str, dict]:
    data = json.loads(SPEED_FILE.read_text(encoding="utf-8"))
    return {s["nguon"]: s for s in data["nguon"]}


def tra_toc_do_toi_da(loai_xe: str | None, ngay: date, khu_dong_dan_cu: bool | None,
                      duong_doi: bool | None, loai_duong: list[str] | None = None) -> TraCuuTocDo:
    """Tốc độ tối đa theo thông tư (khi không có biển báo).

    ``loai_xe``: lớp ontology; ``NhomXeMoTo`` ("xe máy" chung chung) chưa đủ — xe gắn máy và xe mô tô có giới hạn
    khác nhau, cần dung tích/công suất (``thieu="dung_tich"``). Đường cao tốc: phải theo biển báo
    (``thieu="toc_do_toi_da"``).
    """
    vb = chon_van_ban_bo_tro("toc_do_toi_da", ngay)
    if vb.van_ban is None or vb.van_ban not in _bang():
        return TraCuuTocDo(None, "toc_do_toi_da", ghi_chu=vb.ghi_chu)
    src = _bang()[vb.van_ban]
    if "DuongCaoToc" in (loai_duong or []):
        return TraCuuTocDo(None, "toc_do_toi_da", van_ban=vb.van_ban, ghi_chu=src["cao_toc"].get("ghi_chu"))
    if loai_xe is None:
        return TraCuuTocDo(None, "loai_xe", van_ban=vb.van_ban)
    if loai_xe == "NhomXeMoTo":
        return TraCuuTocDo(None, "dung_tich", van_ban=vb.van_ban,
                           ghi_chu="Xe gắn máy và xe mô tô có tốc độ tối đa khác nhau — cần dung tích/công suất xe")
    nhom = next((n for n in src["nhom"] if loai_xe in n["classes"]), None)
    if nhom is None:
        return TraCuuTocDo(None, "toc_do_toi_da", van_ban=vb.van_ban,
                           ghi_chu=f"Bảng tốc độ {vb.van_ban} trong dữ liệu không có nhóm cho {loai_xe}")
    if "moi_loai_duong" in nhom:
        m = nhom["moi_loai_duong"]
        return TraCuuTocDo(float(m["gia_tri"]), None, m["can_cu"], vb.van_ban, nhom["ten"], nhom.get("ghi_chu"))
    if khu_dong_dan_cu is None or duong_doi is None:
        return TraCuuTocDo(None, "dac_diem_duong", van_ban=vb.van_ban, nhom_xe=nhom["ten"])
    vung = nhom["trong_khu_dong_dan_cu" if khu_dong_dan_cu else "ngoai_khu_dong_dan_cu"]
    v = vung["duong_doi" if duong_doi else "duong_hai_chieu"]
    return TraCuuTocDo(float(v), None, vung["can_cu"], vb.van_ban, nhom["ten"], nhom.get("ghi_chu"))
