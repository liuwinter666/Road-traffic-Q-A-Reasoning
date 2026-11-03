"""Kiểm tra hồ sơ còn thiếu trường quyết định kết luận → sinh câu hỏi làm rõ (thiếu thì hỏi, không đoán).

Nguyên tắc:
  * Chỉ hỏi trường thực sự làm đổi kết luận: loại xe, kết quả đo nồng độ, tốc độ, dung tích khi cần xét
    hạng GPLX/độ tuổi, giấy tờ cụ thể, kinh doanh vận tải (chỉ V3, V4), tình tiết tai nạn...
  * Không hỏi ngày nếu người dùng không nói (dùng phiên bản mặc định và ghi giả định), nhưng HỎI khi khoảng thời
    gian người dùng nêu vắt qua hai phiên bản.
  * Tốc độ tối đa: không hỏi nếu suy ra được từ thông tư tốc độ (loại xe + đặc điểm đường đủ để tra bảng).
  * Mỗi lượt hỏi tối đa ``so_cau_hoi_toi_da`` câu, theo thứ tự ưu tiên.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import yaml

from src.config import ROOT_DIR
from src.extraction.schema import HoSoVuViec
from src.kb.temporal import chon_phien_ban, chon_van_ban_bo_tro

SLOTS_FILE = ROOT_DIR / "config" / "slots.yaml"
XE_MO_TO = {"NhomXeMoTo", "XeMoTo", "XeMoToHaiBanh", "XeMoToBaBanh", "XeTuongTuXeMoTo"}
XE_TOC_DO_MOI_DUONG = {"XeGanMay", "XeMayDien", "XeTuongTuXeGanMay", "XeChoNguoiBonBanhCoGanDongCo",
                       "XeChoHangBonBanhCoGanDongCo"}
KHONG_PHU_THUOC_XE = {"ChongDoiNguoiThiHanhCongVu", "KhongChapHanhYeuCauKiemTra"}
GIAY_TO = {"KhongCoGPLX", "KhongMangTheoGPLX", "KhongCoDangKyXe", "KhongMangTheoDangKyXe",
           "KhongCoBaoHiemTNDS", "KhongMangTheoBaoHiemTNDS"}
TAI_NAN = {"CoGayTaiNan", "GayTaiNanBoTron", "LienQuanTaiNanKhongDungLai"}


@dataclass
class CauHoi:
    truong: str
    cau_hoi: str
    ly_do: str
    uu_tien: int


@dataclass
class KetQuaSlot:
    du_thong_tin: bool
    cau_hoi: list[CauHoi] = field(default_factory=list)
    phien_ban: str | None = None
    ghi_chu: list[str] = field(default_factory=list)


def _cfg() -> dict:
    return yaml.safe_load(SLOTS_FILE.read_text(encoding="utf-8"))


def co_the_suy_ra_toc_do_toi_da(hs: HoSoVuViec, ngay: date) -> tuple[bool, str | None]:
    """(có tra được bảng tốc độ không, trường còn thiếu để tra) — dựa trên thông tư có hiệu lực tại ``ngay``."""
    if chon_van_ban_bo_tro("toc_do_toi_da", ngay).khoa is None:
        return False, "toc_do_toi_da"
    if hs.loai_xe in XE_TOC_DO_MOI_DUONG:
        return True, None
    if "DuongCaoToc" in hs.loai_duong:
        return False, "toc_do_toi_da"          # cao tốc phải có biển báo — hỏi số trên biển
    if hs.loai_xe is None:
        return False, "loai_xe"
    if hs.khu_dong_dan_cu is None or hs.duong_doi is None:
        return False, "dac_diem_duong"
    return True, None


def kiem_tra(hs: HoSoVuViec, hom_nay: date | None = None) -> KetQuaSlot:
    """Danh sách câu hỏi làm rõ (rỗng nếu đủ thông tin để suy luận)."""
    cfg = _cfg()
    today = hom_nay or date.today()
    nodes, hints = hs.nodes(), hs.goi_y()
    need: dict[str, str] = {}               # trường → câu hỏi (có thể đã định dạng)
    ghi_chu: list[str] = []

    # Phiên bản pháp lý
    pb_tu = chon_phien_ban(hs.ngay_tu, hom_nay=today) if hs.ngay_tu else chon_phien_ban(None, hom_nay=today)
    v = pb_tu.version
    if hs.ngay_tu and hs.ngay_den and hs.ngay_tu != hs.ngay_den:
        if chon_phien_ban(hs.ngay_den, hom_nay=today).version != v:
            need["ngay_chinh_xac"] = ""
    if hs.ngay_tu is None:
        ghi_chu.append(pb_tu.ghi_chu)
    ngay = hs.ngay_vi_pham or hs.ngay_tu or today

    co_su_kien = bool(nodes) or any(x is not None for x in (
        hs.nong_do_con_khi_tho, hs.nong_do_con_mau, hs.toc_do_thuc_te)) or bool(hs.su_kien)
    if not co_su_kien:
        need["mo_ta_hanh_vi"] = ""

    # Loại xe
    phu_thuoc_xe = (nodes - KHONG_PHU_THUOC_XE - {d.node for d in hs.dau_hieu if d.kieu == "tinh_tiet"}) \
        or hs.toc_do_thuc_te is not None or hs.nong_do_con_khi_tho is not None or hs.nong_do_con_mau is not None
    if hs.loai_xe is None and phu_thuoc_xe:
        need["loai_xe"] = ""

    # Nồng độ cồn
    if "_CO_CON" in hints and hs.nong_do_con_khi_tho is None and hs.nong_do_con_mau is None \
            and "TuChoiKiemTraNongDoCon" not in nodes:
        need["don_vi_nong_do" if any("nồng độ cồn" in x for x in hs.khong_lien_ket) else "nong_do_con"] = ""

    # Tốc độ
    if "_TOC_DO" in hints or hs.toc_do_thuc_te is not None or hs.toc_do_toi_da is not None:
        if hs.toc_do_thuc_te is None:
            need["toc_do_thuc_te"] = ""
        if hs.toc_do_toi_da is None:
            ok, missing = co_the_suy_ra_toc_do_toi_da(hs, ngay)
            if not ok and missing and missing not in need:
                need[missing] = ""

    # GPLX / độ tuổi cần dung tích xe mô tô
    thieu_dt = hs.dung_tich_xi_lanh is None and hs.cong_suat_dong_co_dien is None
    if hs.loai_xe in XE_MO_TO and thieu_dt:
        if "KhongCoGPLX" in nodes:
            need["dung_tich"] = ""
        if hs.tuoi_nguoi_lai is not None and 16 <= hs.tuoi_nguoi_lai < 18 and v != "V4":
            need["dung_tich"] = ""
    if "_NGUOI_TRE" in hints and hs.tuoi_nguoi_lai is None:
        need["tuoi_nguoi_lai"] = ""

    # Giấy tờ
    if "_GIAY_TO" in hints and not (nodes & GIAY_TO):
        need["loai_giay_to"] = ""
    if nodes & {"KhongMangTheoGPLX", "KhongMangTheoDangKyXe", "KhongMangTheoBaoHiemTNDS"} \
            and v in ("V3", "V4") and hs.kinh_doanh_van_tai is None:
        need["kinh_doanh_van_tai"] = ""

    # Tai nạn
    if "_TAI_NAN" in hints and not (nodes & TAI_NAN):
        need["tai_nan"] = ""
    if (nodes & {"CoGayTaiNan", "LienQuanTaiNanKhongDungLai"}) and "dungLaiSauTaiNan" not in hs.su_kien:
        need["tai_nan"] = ""

    # Chủ xe giao xe
    if hs.chu_xe_giao_xe and hs.tuoi_nguoi_lai is None and "coGPLX" not in hs.su_kien:
        need["nguoi_lai_duoc_giao_xe"] = ""

    # Liên kết bằng embedding → xác nhận
    for d in hs.dau_hieu:
        if d.phuong_phap == "embedding" and not d.phu_dinh:
            need.setdefault("xac_nhan", f"'{d.goc}' nghĩa là {d.node}")

    qs = []
    for truong, extra in need.items():
        c = cfg["cau_hoi"][truong]
        text = c["cau_hoi"].format(mo_ta=extra) if extra else c["cau_hoi"]
        qs.append(CauHoi(truong, text, c["ly_do"], c["uu_tien"]))
    qs.sort(key=lambda q: q.uu_tien)
    return KetQuaSlot(not qs, qs[: cfg["so_cau_hoi_toi_da"]], v, ghi_chu)
