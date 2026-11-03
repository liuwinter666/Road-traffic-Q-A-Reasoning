"""Mô hình thời gian: chọn phiên bản pháp lý theo thời điểm vi phạm và xác định hiệu lực của
từng phần tử (tới cấp một phần nội dung của điểm), kể cả hiệu lực có điều kiện.

Quy tắc:
  * Thời điểm vi phạm rõ → phiên bản có khoảng [effective_from, effective_to] chứa ngày đó.
  * Không rõ → ``default_version`` trong ``config/legal_sources.yaml`` ("current" = phiên bản đang
    có hiệu lực tại ngày chạy hệ thống), và câu trả lời phải ghi rõ giả định này.
  * Một phần tử/phần nội dung có ``hieu_luc_dieu_kien`` (hiệu lực còn phụ thuộc văn bản khác) được
    coi là CHƯA có hiệu lực cho tới khi cấu hình ghi ``dieu_kien_da_dap_ung: true``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from src.ingest.build_articles import load_sources

# Mã trạng thái hiệu lực
CO_HIEU_LUC = "co_hieu_luc"
CHUA_HIEU_LUC = "chua_hieu_luc"            # chưa đến ngày
CHUA_HIEU_LUC_DIEU_KIEN = "chua_hieu_luc_dieu_kien"  # đã/chưa đến ngày nhưng điều kiện chưa đáp ứng
CHUA_XAC_DINH = "chua_xac_dinh"            # văn bản không nêu ngày, chỉ nêu điều kiện
HET_HIEU_LUC = "het_hieu_luc"
BAI_BO = "bai_bo"
MOT_PHAN = "mot_phan"                      # phần tử có phần nội dung có hiệu lực, phần chưa
KHONG_CO_DU_LIEU = "khong_co_du_lieu_thoi_diem"  # có quy định tại thời điểm đó nhưng câu chữ cũ không có trong dữ liệu


@dataclass
class ChonPhienBan:
    """Kết quả chọn phiên bản pháp lý."""

    version: str
    ngay_ap_dung: date
    mac_dinh: bool              # True nếu thời điểm vi phạm không rõ
    ghi_chu: str


@dataclass
class TrangThaiDoan:
    """Trạng thái hiệu lực của một đoạn (toàn bộ hoặc một phần nội dung)."""

    pham_vi: str
    mo_ta_pham_vi: str | None
    ma: str
    giai_thich: str


@dataclass
class TrangThaiHieuLuc:
    """Trạng thái hiệu lực của một phần tử tại một ngày."""

    id: str
    ngay: date
    ma: str
    giai_thich: str
    doan: list[TrangThaiDoan] = field(default_factory=list)

    @property
    def co_the_ap_dung(self) -> bool:
        """Có thể dùng làm căn cứ kết luận (toàn bộ hoặc phần nội dung chính có hiệu lực)."""
        return self.ma in (CO_HIEU_LUC, MOT_PHAN)


def _d(s) -> date | None:
    if s is None or isinstance(s, date):
        return s
    return date.fromisoformat(str(s)[:10])


def _fmt(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "?"


def chon_phien_ban(ngay_vi_pham: date | None, cfg: dict | None = None,
                   hom_nay: date | None = None) -> ChonPhienBan:
    """Chọn phiên bản pháp lý cho thời điểm vi phạm."""
    cfg = cfg or load_sources()
    versions = cfg["versions"]
    hom_nay = hom_nay or date.today()
    mac_dinh = ngay_vi_pham is None
    ngay = ngay_vi_pham or hom_nay
    if mac_dinh and cfg.get("default_version", "current") != "current":
        v = cfg["default_version"]
        return ChonPhienBan(v, ngay, True,
                            f"Không rõ thời điểm vi phạm — mặc định áp dụng {v} ({versions[v]['label']}).")
    for v, m in versions.items():
        if _d(m["effective_from"]) <= ngay and (m.get("effective_to") is None or ngay <= _d(m["effective_to"])):
            note = (f"Không rõ thời điểm vi phạm — mặc định áp dụng phiên bản đang có hiệu lực ngày {_fmt(ngay)}: "
                    f"{v} ({m['label']}).") if mac_dinh else (
                    f"Vi phạm ngày {_fmt(ngay)} → {v} ({m['label']}, hiệu lực {_fmt(_d(m['effective_from']))}"
                    f"{' – ' + _fmt(_d(m.get('effective_to'))) if m.get('effective_to') else ' đến nay'}).")
            return ChonPhienBan(v, ngay, mac_dinh, note)
    first = next(iter(versions.values()))
    raise ValueError(f"Ngày {_fmt(ngay)} trước phiên bản sớm nhất ({_fmt(_d(first['effective_from']))}) — "
                     "ngoài phạm vi dữ liệu.")


def _doan_status(seg: dict, ngay: date) -> TrangThaiDoan:
    tu, den = _d(seg.get("tu")), _d(seg.get("den"))
    dk = seg.get("hieu_luc_dieu_kien")
    pv, mo_ta = seg["pham_vi"], seg.get("mo_ta_pham_vi")
    if tu is None and dk:
        return TrangThaiDoan(pv, mo_ta, CHUA_XAC_DINH,
                             f"Văn bản không nêu ngày hiệu lực; hiệu lực {dk}. Hệ thống coi là chưa có hiệu lực.")
    if tu is None:
        return TrangThaiDoan(pv, mo_ta, CHUA_XAC_DINH, "Chưa xác định được ngày hiệu lực từ văn bản.")
    if ngay < tu:
        extra = f", đồng thời {dk}" if dk else ""
        return TrangThaiDoan(pv, mo_ta, CHUA_HIEU_LUC, f"Có hiệu lực từ {_fmt(tu)}{extra}; ngày {_fmt(ngay)} chưa có hiệu lực.")
    if den is not None and ngay > den:
        return TrangThaiDoan(pv, mo_ta, HET_HIEU_LUC, f"Hết hiệu lực sau {_fmt(den)}.")
    if dk and not seg.get("dieu_kien_da_dap_ung"):
        return TrangThaiDoan(pv, mo_ta, CHUA_HIEU_LUC_DIEU_KIEN,
                             f"Mốc {_fmt(tu)} đã đến nhưng hiệu lực còn {dk}; điều kiện này chưa được xác nhận "
                             "trong dữ liệu nên hệ thống coi là chưa có hiệu lực.")
    return TrangThaiDoan(pv, mo_ta, CO_HIEU_LUC, f"Có hiệu lực từ {_fmt(tu)}.")


def trang_thai_hieu_luc(rec: dict, ngay: date) -> TrangThaiHieuLuc:
    """Trạng thái hiệu lực của bản ghi ``articles_v*.jsonl`` / ``support_*.jsonl`` tại ``ngay``."""
    rid = rec["id"]
    if rec.get("status") == "bai_bo":
        bb = _d(rec.get("bai_bo_tu"))
        if bb and ngay < bb:
            return TrangThaiHieuLuc(rid, ngay, KHONG_CO_DU_LIEU,
                                    f"Phần tử bị bãi bỏ từ {_fmt(bb)}; nội dung áp dụng trước ngày đó không có trong dữ liệu.")
        return TrangThaiHieuLuc(rid, ngay, BAI_BO, "Phần tử đã bị bãi bỏ.")
    doan = [_doan_status(s, ngay) for s in rec.get("hieu_luc_chi_tiet") or [
        {"pham_vi": "toan_bo", "tu": rec.get("effective_from"), "den": rec.get("effective_to")}]]
    if len(doan) == 1:
        d = doan[0]
        gt = d.giai_thich
        if d.ma == CHUA_HIEU_LUC and rec.get("noi_dung_truoc_do"):
            # Văn bản hợp nhất: câu chữ hiện hành có từ ngày sửa đổi; trước đó có câu chữ cũ nhưng không có dữ liệu
            return TrangThaiHieuLuc(rid, ngay, KHONG_CO_DU_LIEU,
                                    f"Câu chữ hiện hành {d.giai_thich[0].lower()}{d.giai_thich[1:]} "
                                    + rec["noi_dung_truoc_do"], doan)
        return TrangThaiHieuLuc(rid, ngay, d.ma, gt, doan)
    ok = [d for d in doan if d.ma == CO_HIEU_LUC]
    chinh = next(d for d in doan if d.pham_vi in ("toan_bo", "phan_con_lai"))
    if len(ok) == len(doan):
        return TrangThaiHieuLuc(rid, ngay, CO_HIEU_LUC, "Toàn bộ nội dung có hiệu lực.", doan)
    if chinh.ma == CO_HIEU_LUC:
        chua = "; ".join(f"{d.mo_ta_pham_vi}: {d.giai_thich}" for d in doan if d.ma != CO_HIEU_LUC)
        return TrangThaiHieuLuc(rid, ngay, MOT_PHAN,
                                f"Chỉ có hiệu lực một phần. Phần CHƯA có hiệu lực — {chua}", doan)
    return TrangThaiHieuLuc(rid, ngay, chinh.ma, chinh.giai_thich, doan)
