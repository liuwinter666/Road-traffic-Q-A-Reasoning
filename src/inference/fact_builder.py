"""Chuyển hồ sơ vụ việc (``HoSoVuViec``) thành dict sự kiện cho ``kb.abox.build_case`` — hoàn toàn tất định.

Các việc làm ở đây là chuyển đổi và tra bảng, KHÔNG kết luận pháp lý:
  * thời điểm: ngày chính xác; nếu chỉ biết khoảng (tháng/năm) nằm trọn trong một phiên bản → dùng ngày đầu khoảng
    và ghi giả định; không rõ → để trống (reasoner dùng phiên bản mặc định và ghi chú).
  * tốc độ tối đa: người dùng nêu (biển báo) thì dùng; không thì tra bảng thông tư có hiệu lực tại ngày vi phạm
    (``kb.toc_do``) và ghi căn cứ.
  * sự kiện boolean: lấy từ hồ sơ (trực tiếp + suy ra đã chấp nhận/xác nhận), chỉ giữ thuộc tính có trong ontology.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from src.extraction.schema import HoSoVuViec
from src.kb.temporal import chon_phien_ban
from src.kb.toc_do import tra_toc_do_toi_da


@dataclass
class DuLieuVuViec:
    case: dict                                   # đầu vào abox.build_case
    gia_dinh: list[str] = field(default_factory=list)
    can_cu_bo_tro: list[dict] = field(default_factory=list)    # căn cứ của giá trị tra bảng (vd. tốc độ tối đa)
    nguon_su_kien: dict[str, str] = field(default_factory=dict)  # thuộc tính → trực tiếp | suy_ra | xac_nhan


def ngay_ap_dung(hs: HoSoVuViec, hom_nay: date | None = None) -> tuple[date | None, list[str]]:
    """Ngày dùng để chọn phiên bản (None = không rõ) + giả định."""
    if hs.ngay_vi_pham:
        return hs.ngay_vi_pham, []
    if hs.ngay_tu and hs.ngay_den:
        a = chon_phien_ban(hs.ngay_tu, hom_nay=hom_nay).version
        b = chon_phien_ban(hs.ngay_den, hom_nay=hom_nay).version
        if a == b:
            return hs.ngay_tu, [f"Thời điểm vi phạm chỉ xác định trong khoảng {hs.ngay_tu:%d/%m/%Y} – "
                                f"{hs.ngay_den:%d/%m/%Y}; cả khoảng thuộc cùng phiên bản {a}."]
    return None, []


def xay_dung(hs: HoSoVuViec, hom_nay: date | None = None) -> DuLieuVuViec:
    """Hồ sơ → dict vụ việc (định dạng ở ``src/kb/abox.py``)."""
    from src.inference.fact_inducer import danh_muc

    today = hom_nay or date.today()
    ngay, gia_dinh = ngay_ap_dung(hs, today)
    out = DuLieuVuViec({}, gia_dinh)
    case = out.case
    case["ngay"] = ngay
    case["xe"] = hs.loai_xe or "PhuongTien"
    xe_tt = {"dungTichXiLanh": hs.dung_tich_xi_lanh, "congSuatDongCoDien": hs.cong_suat_dong_co_dien}
    case["xe_tt"] = {k: v for k, v in xe_tt.items() if v is not None}
    case["nguoi"] = {"tuoi": hs.tuoi_nguoi_lai} if hs.tuoi_nguoi_lai is not None else {}

    sk: dict = {}
    for k, v in (("nongDoConKhiTho", hs.nong_do_con_khi_tho), ("nongDoConMau", hs.nong_do_con_mau),
                 ("tocDoThucTe", hs.toc_do_thuc_te)):
        if v is not None:
            sk[k] = v
    if hs.toc_do_thuc_te is not None:
        if hs.toc_do_toi_da is not None:
            sk["tocDoToiDaChoPhep"] = hs.toc_do_toi_da
        else:
            tc = tra_toc_do_toi_da(hs.loai_xe, ngay or today, hs.khu_dong_dan_cu, hs.duong_doi, hs.loai_duong)
            if tc.tra_duoc:
                sk["tocDoToiDaChoPhep"] = tc.gia_tri
                out.can_cu_bo_tro.append({**tc.can_cu, "van_ban": tc.van_ban})
                out.nguon_su_kien["tocDoToiDaChoPhep"] = "tra_bang"
                vung = ("trong" if hs.khu_dong_dan_cu else "ngoài") if hs.khu_dong_dan_cu is not None else ""
                out.gia_dinh.append(
                    f"Không có thông tin biển báo: tốc độ tối đa {tc.gia_tri:g} km/h tra theo {tc.van_ban} "
                    f"({tc.nhom_xe}" + (f", {vung} khu đông dân cư" if vung else "")
                    + (f", {'đường đôi' if hs.duong_doi else 'đường hai chiều'}" if hs.duong_doi is not None
                       and vung else "") + ").")
                if tc.ghi_chu:
                    out.gia_dinh.append(f"Giả định xe thuộc nhóm “{tc.nhom_xe}” của {tc.van_ban}. {tc.ghi_chu}")

    hop_le = set(danh_muc()) | {"gplxDangBiTuoc"}
    for k, v in hs.su_kien.items():
        if k in hop_le:
            sk[k] = v
            pp = (hs.nguon.get(f"su_kien.{k}").phuong_phap if hs.nguon.get(f"su_kien.{k}") else "truc_tiep")
            out.nguon_su_kien[k] = {"suy_ra": "suy_ra", "nguoi_dung_xac_nhan": "xac_nhan"}.get(pp, "truc_tiep")
    if hs.kinh_doanh_van_tai is not None:
        sk["kinhDoanhVanTai"] = hs.kinh_doanh_van_tai
    case["su_kien"] = sk
    case["duong"] = list(hs.loai_duong)
    if hs.chu_xe_giao_xe:
        case["chu_xe"] = {"tuoi": hs.tuoi_chu_xe} if hs.tuoi_chu_xe is not None else {}
    return out
