"""Quản lý hội thoại nhiều lượt (mục 8 đặc tả, bước 1).

Mỗi phiên = một vụ việc: ``PhienLamViec`` của pipeline (hồ sơ Pydantic tích lũy qua các lượt + lời kể + câu hỏi vừa
hỏi) và lịch sử tin nhắn. Chức năng:
  * ``gui(phien_id, tin_nhan, ngay_vi_pham)`` — một lượt (lệnh ``/moi`` bắt đầu vụ việc mới trong cùng phiên).
  * ``sua_ho_so(phien_id, thay_doi)`` — người dùng sửa bảng sự kiện trên giao diện rồi chạy lại: áp thay đổi vào hồ
    sơ (nguồn = người dùng sửa, luôn thắng sự kiện do LLM suy ra) và chạy lại từ bước kiểm tra thiếu thông tin,
    KHÔNG gọi lại LLM trích xuất.
  * ``dat_ngay`` — ô chọn ngày vi phạm trên giao diện (None = không rõ → phiên bản mặc định).
Phiên lưu trong bộ nhớ, hết hạn sau ``ttl_phut`` phút không dùng. Một khóa chung bao các lượt xử lý vì reasoner
(owlready2 + Java) không an toàn khi chạy song song.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache

from loguru import logger

from src.dialogue.serialize import ket_qua_json
from src.extraction.schema import HoSoVuViec, NguonGoc
from src.inference.pipeline import PhienLamViec, Pipeline

TRUONG_SO = {"dung_tich_xi_lanh": float, "cong_suat_dong_co_dien": float, "tuoi_nguoi_lai": int,
             "nong_do_con_khi_tho": float, "nong_do_con_mau": float, "toc_do_thuc_te": float,
             "toc_do_toi_da": float, "tuoi_chu_xe": int}
TRUONG_BOOL = {"khu_dong_dan_cu", "duong_doi", "kinh_doanh_van_tai", "chu_xe_giao_xe"}
LENH_MOI = {"/moi", "/new"}


class PhienKhongTonTai(KeyError):
    """Không có phiên với id đã cho (hoặc đã hết hạn)."""


@dataclass
class TinNhan:
    vai: str                          # nguoi_dung | he_thong
    noi_dung: str
    luc: str
    ket_qua: dict | None = None


@dataclass
class Phien:
    id: str
    lam_viec: PhienLamViec = field(default_factory=PhienLamViec)
    lich_su: list[TinNhan] = field(default_factory=list)
    ngay_vi_pham: date | None = None
    ket_qua_cuoi: dict | None = None
    dung_luc: float = field(default_factory=time.time)

    def tom_tat(self) -> dict:
        return {"phien_id": self.id, "ngay_vi_pham": self.ngay_vi_pham.isoformat() if self.ngay_vi_pham else None,
                "ho_so": self.lam_viec.ho_so.model_dump(mode="json"), "so_luot": self.lam_viec.so_luot,
                "lich_su": [{"vai": t.vai, "noi_dung": t.noi_dung, "luc": t.luc} for t in self.lich_su],
                "ket_qua_cuoi": self.ket_qua_cuoi}


@lru_cache(maxsize=1)
def danh_muc_giao_dien() -> dict:
    """Lựa chọn cho giao diện: loại xe, loại đường, sự kiện boolean (mã + nhãn tiếng Việt)."""
    import json

    from src.config import PROCESSED_DIR
    from src.explanation.tracer import nhan
    from src.inference.fact_inducer import danh_muc

    syn = json.loads((PROCESSED_DIR / "synonyms.json").read_text(encoding="utf-8"))
    return {"loai_xe": [{"ma": m, "nhan": nhan(m)} for m in syn["xe"]],
            "loai_duong": [{"ma": m, "nhan": nhan(m)} for m in syn["duong"]],
            "su_kien": [{"ma": m, "nhan": n} for m, n in {**danh_muc(), "gplxDangBiTuoc":
                                                         "GPLX đang trong thời hạn bị tước quyền sử dụng"}.items()]}


def ap_dung_sua(hs: HoSoVuViec, thay_doi: dict, hom_nay: date | None = None) -> list[str]:
    """Áp thay đổi người dùng sửa trên bảng sự kiện vào ``hs``. Trả danh sách mô tả thay đổi. ValueError nếu sai."""
    dm = danh_muc_giao_dien()
    xe_ok = {x["ma"] for x in dm["loai_xe"]}
    duong_ok = {x["ma"] for x in dm["loai_duong"]}
    sk_ok = {x["ma"] for x in dm["su_kien"]}
    da_sua: list[str] = []

    def nguon(truong, gt):
        hs.nguon[truong] = NguonGoc(goc=str(gt), phuong_phap="nguoi_dung_sua")

    for k, v in thay_doi.items():
        if k == "ngay_vi_pham":
            d = date.fromisoformat(v) if isinstance(v, str) else v
            hs.ngay_tu = hs.ngay_den = d
            hs.do_chinh_xac_ngay = "ngay" if d else None
            nguon("ngay", v)
        elif k == "loai_xe":
            if v is not None and v not in xe_ok:
                raise ValueError(f"loai_xe '{v}' không hợp lệ (chọn trong: {sorted(xe_ok)})")
            hs.loai_xe = v
            nguon("loai_xe", v)
        elif k in TRUONG_SO:
            if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0):
                raise ValueError(f"{k} phải là số không âm hoặc null")
            setattr(hs, k, None if v is None else TRUONG_SO[k](v))
            nguon(k, v)
        elif k in TRUONG_BOOL:
            if v is not None and not isinstance(v, bool):
                raise ValueError(f"{k} phải là true/false/null")
            setattr(hs, k, v)
            nguon(k, v)
        elif k == "loai_duong":
            if not isinstance(v, list) or set(v) - duong_ok:
                raise ValueError(f"loai_duong phải là danh sách trong {sorted(duong_ok)}")
            hs.loai_duong = list(v)
            if "KhuDanCu" in v or "NgoaiKhuDanCu" in v:
                hs.khu_dong_dan_cu = "KhuDanCu" in v
        elif k == "su_kien":
            for p, gt in (v or {}).items():
                if p not in sk_ok:
                    raise ValueError(f"Sự kiện '{p}' không có trong danh mục ontology")
                if gt is not None and not isinstance(gt, bool):
                    raise ValueError(f"Giá trị sự kiện '{p}' phải là true/false/null")
                for s in hs.su_kien_suy_ra:          # người dùng sửa thì bỏ kết quả suy ra của LLM cho thuộc tính đó
                    if s.thuoc_tinh == p:
                        s.trang_thai = "tu_choi" if gt is None or gt != s.gia_tri else "xac_nhan"
                if gt is None:
                    hs.su_kien.pop(p, None)
                    hs.nguon.pop(f"su_kien.{p}", None)
                else:
                    hs.su_kien[p] = gt
                    nguon(f"su_kien.{p}", gt)
        else:
            raise ValueError(f"Không sửa được trường '{k}'")
        da_sua.append(k)

    # "xe máy" chung chung + dung tích/công suất → xếp loại theo luật có hiệu lực tại ngày vi phạm
    if hs.loai_xe in ("NhomXeMoTo", "XeMayDien") and (hs.dung_tich_xi_lanh or hs.cong_suat_dong_co_dien):
        from src.extraction.llm_extractor import phan_loai_xe_may

        dt = hs.dung_tich_xi_lanh if hs.loai_xe == "NhomXeMoTo" else None
        if pl := phan_loai_xe_may(dt, hs.cong_suat_dong_co_dien, hs.ngay_tu or hom_nay or date.today()):
            hs.loai_xe = pl[0]
            hs.nguon["loai_xe"] = NguonGoc(goc="người dùng sửa", phuong_phap="suy_ra", ghi_chu=[pl[1]])
    return da_sua


class DialogueManager:
    def __init__(self, pipeline: Pipeline | None = None, ttl_phut: int = 180):
        self._pipeline = pipeline
        self.ttl_s = ttl_phut * 60
        self._phien: dict[str, Phien] = {}
        self._khoa = threading.RLock()

    @property
    def pipeline(self) -> Pipeline:
        if self._pipeline is None:
            self._pipeline = Pipeline()
        return self._pipeline

    # ---- phiên ----
    def tao_phien(self) -> str:
        self.don_dep()
        pid = uuid.uuid4().hex[:12]
        self._phien[pid] = Phien(pid)
        logger.info("Tạo phiên {}", pid)
        return pid

    def lay(self, pid: str) -> Phien:
        p = self._phien.get(pid)
        if p is None:
            raise PhienKhongTonTai(pid)
        p.dung_luc = time.time()
        return p

    def xoa(self, pid: str) -> None:
        self._phien.pop(pid, None)

    def don_dep(self) -> None:
        het = [k for k, p in self._phien.items() if time.time() - p.dung_luc > self.ttl_s]
        for k in het:
            self._phien.pop(k, None)
        if het:
            logger.info("Xóa {} phiên hết hạn", len(het))

    def vu_viec_moi(self, pid: str) -> None:
        p = self.lay(pid)
        p.lam_viec, p.ket_qua_cuoi = PhienLamViec(), None
        p.lich_su.append(TinNhan("he_thong", "Đã bắt đầu vụ việc mới.", _bay_gio()))

    def dat_ngay(self, pid: str, ngay: date | None) -> None:
        p = self.lay(pid)
        p.ngay_vi_pham = ngay
        if ngay is not None:
            ap_dung_sua(p.lam_viec.ho_so, {"ngay_vi_pham": ngay}, self.pipeline.hom_nay)

    # ---- lượt ----
    def gui(self, pid: str, tin_nhan: str, ngay_vi_pham: date | None = None) -> dict:
        """Một lượt người dùng → kết quả (dict JSON)."""
        tin_nhan = (tin_nhan or "").strip()
        if not tin_nhan:
            raise ValueError("Tin nhắn rỗng")
        p = self.lay(pid)
        if tin_nhan.lower() in LENH_MOI:
            self.vu_viec_moi(pid)
            return {"trang_thai": "vu_viec_moi", "tra_loi": "Đã bắt đầu vụ việc mới. Bạn mô tả tình huống nhé."}
        if ngay_vi_pham is not None:
            p.ngay_vi_pham = ngay_vi_pham
        p.lich_su.append(TinNhan("nguoi_dung", tin_nhan, _bay_gio()))
        with self._khoa:
            kq = self.pipeline.xu_ly(p.lam_viec, tin_nhan, p.ngay_vi_pham)
        return self._ghi(p, kq)

    def sua_ho_so(self, pid: str, thay_doi: dict) -> dict:
        """Sửa bảng sự kiện rồi chạy lại suy luận (không gọi LLM trích xuất)."""
        p = self.lay(pid)
        if "ngay_vi_pham" in thay_doi:
            v = thay_doi["ngay_vi_pham"]
            p.ngay_vi_pham = date.fromisoformat(v) if isinstance(v, str) else v
        with self._khoa:
            da_sua = ap_dung_sua(p.lam_viec.ho_so, thay_doi, self.pipeline.hom_nay)
            p.lich_su.append(TinNhan("nguoi_dung", f"(sửa hồ sơ: {', '.join(da_sua)})", _bay_gio()))
            kq = self.pipeline.chay_lai(p.lam_viec, p.ngay_vi_pham)
        return self._ghi(p, kq)

    @staticmethod
    def _ghi(p: Phien, kq) -> dict:
        out = ket_qua_json(kq)
        p.ket_qua_cuoi = out
        p.lich_su.append(TinNhan("he_thong", out["tra_loi"], _bay_gio(), out))
        return out


def _bay_gio() -> str:
    return datetime.now().isoformat(timespec="seconds")
