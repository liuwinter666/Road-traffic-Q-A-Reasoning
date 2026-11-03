"""Dựng cá thể (ABox) của một vụ việc từ dict sự kiện đã chuẩn hóa.

Đây là lớp tất định (không dùng LLM); ``inference/fact_builder.py`` (Phase 5) sẽ chuyển kết quả trích xuất
thành dict này. Định dạng:

    {
      "ngay": "2025-03-10" | date | None,      # thời điểm vi phạm → phiên bản pháp lý
      "version": "V3",                          # (tùy chọn) ép phiên bản, bỏ qua "ngay"
      "xe": "XeMoToHaiBanh",                    # lớp phương tiện trong ontology
      "xe_tt": {"dungTichXiLanh": 110},          # thuộc tính phương tiện
      "nguoi": {"tuoi": 17},                    # người điều khiển
      "su_kien": {"nongDoConKhiTho": 0.3, ...}, # thuộc tính của hành vi điều khiển xe (kể cả sự kiện tình tiết)
      "duong": ["DuongCaoToc"],                 # loại đường
      "chu_xe": {"tuoi": 45},                   # (tùy chọn) chủ xe giao xe cho người điều khiển
    }

``tocDoVuot`` được tính = tocDoThucTe − tocDoToiDaChoPhep (phép tính số học, không phải kết luận pháp lý).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from src.kb.temporal import ChonPhienBan, chon_phien_ban


@dataclass
class CaseIndividuals:
    """Các cá thể đã tạo cho một vụ việc."""

    cid: str
    phien_ban: ChonPhienBan
    vu_viec: object
    hanh_vi_lai: object
    nguoi_lai: object
    xe: object
    hanh_vi_giao_xe: object | None = None
    chu_xe: object | None = None
    canh_bao: list[str] = field(default_factory=list)


def _coerce(onto, prop: str, value):
    p = onto[prop]
    if p is None:
        raise KeyError(f"Thuộc tính '{prop}' không có trong ontology")
    rng = p.range[0] if p.range else None
    if rng is float and isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if rng is int and isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _set(onto, ind, props: dict) -> None:
    for k, v in (props or {}).items():
        if v is None:
            continue
        setattr(ind, k, _coerce(onto, k, v))


def _to_date(x) -> date | None:
    if x is None or isinstance(x, date) and not isinstance(x, datetime):
        return x
    if isinstance(x, datetime):
        return x.date()
    return date.fromisoformat(str(x)[:10])


def chon_phien_ban_cho(case: dict, hom_nay: date | None = None) -> ChonPhienBan:
    """Phiên bản pháp lý của vụ việc (theo "version" chỉ định hoặc theo "ngay")."""
    ngay = _to_date(case.get("ngay"))
    if case.get("version"):
        return ChonPhienBan(case["version"], ngay or (hom_nay or date.today()), ngay is None,
                            f"Phiên bản được chỉ định: {case['version']}.")
    return chon_phien_ban(ngay, hom_nay=hom_nay)


def build_case(onto, case: dict, cid: str = "vv", hom_nay: date | None = None,
               pb: ChonPhienBan | None = None) -> CaseIndividuals:
    """Tạo cá thể của vụ việc ``case`` trong ``onto`` (tên cá thể có tiền tố ``cid`` để gộp nhiều vụ việc)."""
    ngay = _to_date(case.get("ngay"))
    if pb is not None:
        pass
    elif case.get("version"):
        pb = ChonPhienBan(case["version"], ngay or (hom_nay or date.today()), ngay is None,
                          f"Phiên bản được chỉ định: {case['version']}.")
    else:
        pb = chon_phien_ban(ngay, hom_nay=hom_nay)
    with onto:
        vv = onto.VuViec(f"{cid}_vu_viec")
        vv.apDungPhienBan = onto[pb.version]
        if ngay:
            vv.thoiDiemViPham = datetime(ngay.year, ngay.month, ngay.day)
        else:
            vv.thoiDiemKhongRo = True
        xe_cls = onto[case.get("xe") or "PhuongTien"]
        if xe_cls is None:
            raise KeyError(f"Lớp phương tiện '{case.get('xe')}' không có trong ontology")
        xe = xe_cls(f"{cid}_xe")
        _set(onto, xe, case.get("xe_tt"))
        nguoi = onto.NguoiDieuKhien(f"{cid}_nguoi_lai")
        _set(onto, nguoi, case.get("nguoi"))
        nguoi.dieuKhien = [xe]
        hv = onto.HanhViDieuKhienXe(f"{cid}_hanh_vi_lai")
        hv.thuocVuViec = vv
        hv.chuThe = nguoi
        hv.suDungPhuongTien = xe
        sk = dict(case.get("su_kien") or {})
        if sk.get("tocDoThucTe") is not None and sk.get("tocDoToiDaChoPhep") is not None:
            sk["tocDoVuot"] = float(sk["tocDoThucTe"]) - float(sk["tocDoToiDaChoPhep"])
        _set(onto, hv, sk)
        for i, d in enumerate(case.get("duong") or []):
            hv.trenLoaiDuong.append(onto[d](f"{cid}_duong_{i}"))
        out = CaseIndividuals(cid, pb, vv, hv, nguoi, xe)
        if case.get("chu_xe") is not None:
            chu = onto.ChuXe(f"{cid}_chu_xe")
            _set(onto, chu, case["chu_xe"].get("nguoi") if "nguoi" in case["chu_xe"] else
                 {k: v for k, v in case["chu_xe"].items() if k in ("tuoi",)})
            chu.laChuSoHuu = [xe]
            gx = onto.HanhViGiaoXe(f"{cid}_hanh_vi_giao_xe")
            gx.thuocVuViec = vv
            gx.chuThe = chu
            gx.suDungPhuongTien = xe
            gx.giaoXeCho = [nguoi]
            _set(onto, gx, case["chu_xe"].get("su_kien"))
            out.hanh_vi_giao_xe, out.chu_xe = gx, chu
    return out
