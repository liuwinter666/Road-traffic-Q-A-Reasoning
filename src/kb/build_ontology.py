"""Sinh ontology ``ontology/traffic_law.owl`` (OWL 2, RDF/XML — mở được bằng Protégé).

Chạy:  python -m src.kb.build_ontology

Nguồn dữ liệu (ontology là SẢN PHẨM SINH RA, không sửa tay):
  * TBox khái niệm chung: định nghĩa trong file này (lớp, thuộc tính, ràng buộc).
  * Ngưỡng pháp lý, dấu hiệu sự kiện: ``config/ontology_concepts.yaml``.
  * Lớp hành vi vi phạm: ``config/mvp_behaviors.yaml``.
  * Văn bản, phiên bản pháp lý: ``config/legal_sources.yaml``.
  * Cá thể điều khoản + khung phạt: ``data/processed/articles_v*.jsonl`` (chỉ các phần tử
    được hành vi MVP dẫn tới, cùng khoản/điều cha).

Cá thể ``QuyTac`` (luật SWRL) và hình thức xử phạt bổ sung được thêm ở Phase 3.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import types
from pathlib import Path

import yaml
from loguru import logger
from owlready2 import (
    AnnotationProperty,
    AllDisjoint,
    ConstrainedDatatype,
    DataProperty,
    FunctionalProperty,
    ObjectProperty,
    Or,
    PropertyChain,
    Thing,
    TransitiveProperty,
    World,
    locstr,
)

from src.config import ONTOLOGY_DIR, PROCESSED_DIR, ROOT_DIR

ONTO_IRI = "http://www.semanticweb.org/traffic-law-vn/ontology#"
OUT_FILE = ONTOLOGY_DIR / "traffic_law.owl"
CONCEPTS_FILE = ROOT_DIR / "config" / "ontology_concepts.yaml"
BEHAVIORS_FILE = ROOT_DIR / "config" / "mvp_behaviors.yaml"

# Nhóm hành vi (trường `nhom` trong mvp_behaviors.yaml) → lớp cha + nhãn
BEHAVIOR_GROUPS = {
    "nong_do_con": ("ViPhamNongDoCon", "Vi phạm về nồng độ cồn"),
    "ma_tuy": ("ViPhamMaTuy", "Vi phạm về chất ma túy"),
    "toc_do": ("ViPhamTocDo", "Vi phạm về tốc độ"),
    "tin_hieu": ("ViPhamTinHieuHieuLenh", "Vi phạm hiệu lệnh, tín hiệu giao thông"),
    "phan_lan": ("ViPhamPhanDuongLanDuong", "Vi phạm phần đường, làn đường, chiều đi"),
    "thiet_bi": ("ViPhamSuDungThietBi", "Vi phạm sử dụng thiết bị khi lái xe"),
    "an_toan": ("ViPhamThietBiAnToan", "Vi phạm về mũ bảo hiểm, dây an toàn"),
    "tai_nan": ("ViPhamLienQuanTaiNan", "Vi phạm liên quan tai nạn giao thông"),
    "lai_nguy_hiem": ("ViPhamLaiXeNguyHiem", "Lạng lách, đánh võng, điều khiển nguy hiểm"),
    "cong_vu": ("ViPhamDoiVoiNguoiThiHanhCongVu", "Vi phạm đối với người thi hành công vụ"),
    "giay_to": ("ViPhamGiayToXe", "Vi phạm về giấy tờ xe, bảo hiểm"),
    "gplx": ("ViPhamGiayPhepLaiXe", "Vi phạm về giấy phép lái xe"),
    "do_tuoi": ("ViPhamDoTuoi", "Vi phạm về độ tuổi điều khiển xe"),
    "chu_xe": ("ViPhamCuaChuXe", "Vi phạm của chủ phương tiện"),
}
LEVEL_CLASS = {"dieu": "Dieu", "khoan": "Khoan", "diem": "Diem"}
PY_TYPES = {"float": float, "int": int}


def label(entity, vi: str, comment: str | None = None) -> None:
    """Gán rdfs:label tiếng Việt (và rdfs:comment nếu có)."""
    entity.label = [locstr(vi, lang="vi")]
    if comment:
        entity.comment = [locstr(comment, lang="vi")]


def prov_iri(version: str, rid: str) -> str:
    """Tên cá thể điều khoản theo phiên bản, vd. ``V3_ND168-D6-K9-a``."""
    return f"{version}_{rid}"


# ---------------------------------------------------------------------------
# TBox
# ---------------------------------------------------------------------------


def build_tbox(onto) -> types.SimpleNamespace:
    """Khai báo lớp và thuộc tính cốt lõi. Trả về namespace để truy cập nhanh."""
    with onto:
        # ---------- Annotation ----------
        class canCuPhapLy(AnnotationProperty):  # noqa: N801
            pass

        class maHanhVi(AnnotationProperty):  # noqa: N801
            pass

        class ghiChu(AnnotationProperty):  # noqa: N801
            pass

        # ---------- Phương tiện ----------
        class PhuongTien(Thing): pass
        class XeCoGioi(PhuongTien): pass
        class NhomXeOTo(XeCoGioi): pass
        class OTo(NhomXeOTo): pass
        class XeOToTai(OTo): pass
        class XeOToChoNguoi(OTo): pass
        class XeChoNguoiBonBanhCoGanDongCo(NhomXeOTo): pass
        class XeChoHangBonBanhCoGanDongCo(NhomXeOTo): pass
        class XeTuongTuOTo(NhomXeOTo): pass
        class NhomXeMoTo(XeCoGioi): pass
        class XeMoTo(NhomXeMoTo): pass
        class XeMoToHaiBanh(XeMoTo): pass
        class XeMoToBaBanh(XeMoTo): pass
        class XeGanMay(NhomXeMoTo): pass
        class XeMayDien(XeGanMay): pass
        class XeTuongTuXeMoTo(NhomXeMoTo): pass
        class XeTuongTuXeGanMay(NhomXeMoTo): pass
        class XeMayChuyenDung(XeCoGioi): pass
        class XeThoSo(PhuongTien): pass
        class XeDap(XeThoSo): pass
        class XeDapMay(XeThoSo): pass
        class XeDapDien(XeDapMay): pass
        AllDisjoint([NhomXeOTo, NhomXeMoTo, XeMayChuyenDung])
        AllDisjoint([XeCoGioi, XeThoSo])

        # ---------- Con người ----------
        class Nguoi(Thing): pass
        class NguoiDieuKhien(Nguoi): pass
        class ChuXe(Nguoi): pass
        class NguoiThiHanhCongVu(Nguoi): pass
        class NguoiKhongDuDieuKienDieuKhienXe(Nguoi): pass

        # ---------- Đường ----------
        class LoaiDuong(Thing): pass
        class DuongCaoToc(LoaiDuong): pass
        class DuongMotChieu(LoaiDuong): pass
        class KhuDanCu(LoaiDuong): pass
        class NgoaiKhuDanCu(LoaiDuong): pass
        AllDisjoint([KhuDanCu, NgoaiKhuDanCu])

        # ---------- Vụ việc, hành vi ----------
        class VuViec(Thing): pass
        class HanhVi(Thing): pass
        class HanhViDieuKhienXe(HanhVi): pass
        class HanhViGiaoXe(HanhVi): pass
        class HanhViViPham(HanhVi): pass

        # Nhóm khái niệm định nghĩa (dấu hiệu, ngưỡng)
        class DauHieuSuKien(HanhVi): pass
        class MucNongDoCon(HanhVi): pass
        class MucVuotTocDo(HanhVi): pass
        class NhomTuoi(Nguoi): pass
        class NhomDungTichCongSuat(PhuongTien): pass

        # ---------- Tình tiết ----------
        class TinhTiet(Thing): pass
        class TinhTietTangNang(TinhTiet): pass
        class TinhTietGiamNhe(TinhTiet): pass
        AllDisjoint([TinhTietTangNang, TinhTietGiamNhe])

        # ---------- Văn bản, điều khoản, phiên bản ----------
        class VanBan(Thing): pass
        class NghiDinh(VanBan): pass
        class PhienBanPhapLy(Thing): pass
        class DieuKhoan(Thing): pass
        class Dieu(DieuKhoan): pass
        class Khoan(DieuKhoan): pass
        class Diem(DieuKhoan): pass
        AllDisjoint([Dieu, Khoan, Diem])

        # ---------- Chế tài ----------
        class KhungPhat(Thing): pass
        class HinhThucXuPhat(Thing): pass
        class PhatCanhCao(HinhThucXuPhat): pass
        class HinhThucBoSung(HinhThucXuPhat): pass
        class TuocGPLX(HinhThucBoSung): pass
        class TichThuPhuongTien(HinhThucBoSung): pass
        class TichThuTangVat(HinhThucBoSung): pass
        class BienPhapKhac(Thing): pass
        class TruDiemGPLX(BienPhapKhac): pass
        class TamGiuPhuongTien(BienPhapKhac): pass
        class BienPhapKhacPhucHauQua(BienPhapKhac): pass

        # ---------- Quy tắc suy luận ----------
        class QuyTac(Thing): pass

        AllDisjoint([PhuongTien, Nguoi, LoaiDuong, VuViec, HanhVi, TinhTiet, VanBan,
                     PhienBanPhapLy, DieuKhoan, KhungPhat, HinhThucXuPhat, BienPhapKhac, QuyTac])

        # ================= Thuộc tính đối tượng =================
        class dieuKhien(ObjectProperty):  # noqa: N801
            domain = [Nguoi]; range = [PhuongTien]
        class laChuSoHuu(ObjectProperty):  # noqa: N801
            domain = [Nguoi]; range = [PhuongTien]
        class coHanhVi(ObjectProperty):  # noqa: N801
            domain = [VuViec]; range = [HanhVi]
        class thuocVuViec(ObjectProperty, FunctionalProperty):  # noqa: N801
            domain = [HanhVi]; range = [VuViec]; inverse_property = coHanhVi
        class chuThe(ObjectProperty, FunctionalProperty):  # noqa: N801
            domain = [HanhVi]; range = [Nguoi]
        class suDungPhuongTien(ObjectProperty, FunctionalProperty):  # noqa: N801
            domain = [HanhVi]; range = [PhuongTien]
        class giaoXeCho(ObjectProperty):  # noqa: N801
            domain = [HanhViGiaoXe]; range = [Nguoi]
        class trenLoaiDuong(ObjectProperty):  # noqa: N801
            domain = [HanhVi]; range = [LoaiDuong]
        class apDungPhienBan(ObjectProperty, FunctionalProperty):  # noqa: N801
            domain = [VuViec]; range = [PhienBanPhapLy]
        class viPhamHanhVi(ObjectProperty):  # noqa: N801
            domain = [Nguoi]; range = [HanhViViPham]
        class apDungDieuKhoan(ObjectProperty):  # noqa: N801
            domain = [HanhVi]; range = [DieuKhoan]
        class coTinhTiet(ObjectProperty):  # noqa: N801
            range = [TinhTiet]
        class duocSuyRaBoi(ObjectProperty):  # noqa: N801
            range = [QuyTac]
        # Cấu trúc văn bản
        class thuocDieuKhoan(ObjectProperty, TransitiveProperty):  # noqa: N801
            domain = [DieuKhoan]; range = [DieuKhoan]
        class thuocDieuKhoanCha(thuocDieuKhoan, FunctionalProperty):  # noqa: N801
            pass
        class thuocVanBan(ObjectProperty):  # noqa: N801
            domain = [DieuKhoan]; range = [VanBan]
        class duocSuaDoiBoi(ObjectProperty):  # noqa: N801
            domain = [DieuKhoan]; range = [VanBan]
        class thuocPhienBan(ObjectProperty, FunctionalProperty):  # noqa: N801
            domain = [DieuKhoan]; range = [PhienBanPhapLy]
        class gomVanBan(ObjectProperty):  # noqa: N801
            domain = [PhienBanPhapLy]; range = [VanBan]
        # Chế tài
        class coKhungPhat(ObjectProperty):  # noqa: N801
            domain = [DieuKhoan]; range = [KhungPhat]
        class chiuKhungPhat(ObjectProperty):  # noqa: N801
            domain = [HanhVi]; range = [KhungPhat]
        class coHinhThucBoSung(ObjectProperty):  # noqa: N801
            range = [HinhThucXuPhat]
        class coBienPhapKhac(ObjectProperty):  # noqa: N801
            range = [BienPhapKhac]
        # Quy tắc
        class canCuDieuKhoan(ObjectProperty):  # noqa: N801
            domain = [QuyTac]; range = [DieuKhoan]
        class apDungChoPhienBan(ObjectProperty):  # noqa: N801
            domain = [QuyTac]; range = [PhienBanPhapLy]

        # Chuỗi thuộc tính (OWL 2 property chain):
        #   điểm thuộc khoản có khung phạt ⇒ điểm có khung phạt
        coKhungPhat.property_chain.append(PropertyChain([thuocDieuKhoanCha, coKhungPhat]))
        #   hành vi áp dụng điều khoản có khung phạt ⇒ hành vi chịu khung phạt đó
        chiuKhungPhat.property_chain.append(PropertyChain([apDungDieuKhoan, coKhungPhat]))

        # ================= Thuộc tính dữ liệu =================
        def dprop(name, dom, rng, functional=True, vi=None):
            bases = (DataProperty, FunctionalProperty) if functional else (DataProperty,)
            p = types.new_class(name, bases)
            p.domain = [dom]
            p.range = [rng]
            if vi:
                label(p, vi)
            return p

        dprop("thoiDiemViPham", VuViec, dt.datetime, vi="Thời điểm vi phạm")
        dprop("thoiDiemKhongRo", VuViec, bool, vi="Không rõ thời điểm vi phạm (dùng phiên bản mặc định)")
        dprop("tuoi", Nguoi, int, vi="Tuổi")
        dprop("dungTichXiLanh", PhuongTien, float, vi="Dung tích xi-lanh (cm3)")
        dprop("congSuatDongCoDien", PhuongTien, float, vi="Công suất động cơ điện (kW)")
        dprop("nongDoConKhiTho", HanhViDieuKhienXe, float, vi="Nồng độ cồn trong khí thở (mg/L)")
        dprop("nongDoConMau", HanhViDieuKhienXe, float, vi="Nồng độ cồn trong máu (mg/100 mL)")
        dprop("tocDoThucTe", HanhViDieuKhienXe, float, vi="Tốc độ thực tế (km/h)")
        dprop("tocDoToiDaChoPhep", HanhViDieuKhienXe, float, vi="Tốc độ tối đa cho phép (km/h)")
        dprop("tocDoVuot", HanhViDieuKhienXe, float,
              vi="Mức vượt tốc độ (km/h) = tocDoThucTe − tocDoToiDaChoPhep, do fact_builder tính")
        bool_facts = {
            "coMaTuyTrongCoThe": "Trong cơ thể có chất ma túy",
            "tuChoiKiemTraNongDoCon": "Không chấp hành yêu cầu kiểm tra nồng độ cồn",
            "tuChoiKiemTraMaTuy": "Không chấp hành yêu cầu kiểm tra ma túy",
            "khongChapHanhDenTinHieu": "Không chấp hành hiệu lệnh đèn tín hiệu",
            "coHieuLenhNguoiDieuKhienGT": "Có hiệu lệnh của người điều khiển/kiểm soát giao thông",
            "coHieuLenhDungXe": "Có hiệu lệnh dừng xe của người thi hành công vụ",
            "chapHanhHieuLenh": "Có chấp hành hiệu lệnh",
            "coYeuCauKiemTraCuaNguoiThiHanhCongVu": "Có yêu cầu kiểm tra, kiểm soát",
            "chapHanhYeuCauKiemTra": "Có chấp hành yêu cầu kiểm tra, kiểm soát",
            "boChay": "Bỏ chạy",
            "chongDoiNguoiThiHanhCongVu": "Chống đối, cản trở người thi hành công vụ",
            "diNguocChieu": "Đi ngược chiều",
            "diSaiPhanDuongLanDuong": "Đi không đúng phần đường, làn đường",
            "chuyenLanSaiQuyDinh": "Chuyển làn sai quy định",
            "dungTaySuDungDienThoai": "Dùng tay sử dụng điện thoại",
            "doiMuBaoHiem": "Có đội mũ bảo hiểm (cài quai đúng quy cách)",
            "nguoiNgoiSauDoiMuBaoHiem": "Người ngồi sau có đội mũ bảo hiểm",
            "thatDayAnToan": "Có thắt dây an toàn",
            "lienQuanTrucTiepTaiNan": "Liên quan trực tiếp đến vụ tai nạn",
            "gayTaiNan": "Gây tai nạn",
            "dungLaiSauTaiNan": "Dừng lại, giữ hiện trường, cứu giúp sau tai nạn",
            "langLachDanhVong": "Lạng lách, đánh võng",
            "coGPLX": "Có giấy phép lái xe hợp lệ, phù hợp",
            "mangTheoGPLX": "Mang theo giấy phép lái xe",
            "coDangKyXe": "Có giấy (chứng nhận) đăng ký xe",
            "mangTheoDangKyXe": "Mang theo đăng ký xe",
            "coBaoHiemTNDS": "Có bảo hiểm TNDS bắt buộc còn hiệu lực",
            "mangTheoBaoHiemTNDS": "Mang theo chứng nhận bảo hiểm TNDS",
            "kinhDoanhVanTai": "Xe kinh doanh vận tải",
        }
        for name, vi in bool_facts.items():
            dprop(name, HanhViDieuKhienXe, bool, vi=vi)
        # Văn bản / điều khoản
        dprop("soHieu", VanBan, str, vi="Số hiệu văn bản")
        dprop("ngayBanHanh", VanBan, dt.datetime, vi="Ngày ban hành")
        dprop("maPhienBan", PhienBanPhapLy, str, vi="Mã phiên bản")
        for nm, vi in (("hieuLucTu", "Hiệu lực từ ngày"), ("hieuLucDen", "Hiệu lực đến ngày")):
            p = types.new_class(nm, (DataProperty, FunctionalProperty))
            p.range = [dt.datetime]  # xsd:date không thuộc OWL 2 datatype map (HermiT từ chối)
            label(p, vi)
        dprop("maDieuKhoan", DieuKhoan, str, vi="Mã phần tử (vd. ND168-D6-K9-a)")
        dprop("trichDan", DieuKhoan, str, vi="Trích dẫn (vd. điểm a khoản 9 Điều 6 NĐ 168/2024)")
        dprop("noiDung", DieuKhoan, str, vi="Nguyên văn nội dung")
        dprop("trangThai", DieuKhoan, str, vi="active | bai_bo")
        dprop("hieuLucChuaXacDinh", DieuKhoan, bool, vi="Ngày hiệu lực chưa xác định được từ văn bản")
        dprop("mucToiThieu", KhungPhat, int, vi="Mức phạt tối thiểu (VND)")
        dprop("mucToiDa", KhungPhat, int, vi="Mức phạt tối đa (VND)")
        dprop("doiTuongApDung", KhungPhat, str, vi="ca_nhan | to_chuc")
        dprop("thoiHanToiThieuThang", HinhThucBoSung, int, vi="Thời hạn tước tối thiểu (tháng)")
        dprop("thoiHanToiDaThang", HinhThucBoSung, int, vi="Thời hạn tước tối đa (tháng)")
        dprop("soDiemTru", TruDiemGPLX, int, vi="Số điểm GPLX bị trừ")
        dprop("maQuyTac", QuyTac, str, vi="Mã quy tắc (R001...)")
        dprop("ketLuanMaHanhVi", QuyTac, str, vi="Mã hành vi mà quy tắc kết luận")
        dprop("moTaQuyTac", QuyTac, str, vi="Mô tả quy tắc")

    labels = {
        "PhuongTien": "Phương tiện", "XeCoGioi": "Xe cơ giới",
        "NhomXeOTo": "Nhóm xe ô tô (đối tượng Điều 5 NĐ 100 / Điều 6 NĐ 168)",
        "OTo": "Xe ô tô", "XeOToTai": "Xe ô tô tải", "XeOToChoNguoi": "Xe ô tô chở người",
        "XeChoNguoiBonBanhCoGanDongCo": "Xe chở người bốn bánh có gắn động cơ",
        "XeChoHangBonBanhCoGanDongCo": "Xe chở hàng bốn bánh có gắn động cơ",
        "XeTuongTuOTo": "Các loại xe tương tự xe ô tô",
        "NhomXeMoTo": "Nhóm xe mô tô, xe gắn máy (đối tượng Điều 6 NĐ 100 / Điều 7 NĐ 168)",
        "XeMoTo": "Xe mô tô", "XeMoToHaiBanh": "Xe mô tô hai bánh", "XeMoToBaBanh": "Xe mô tô ba bánh",
        "XeGanMay": "Xe gắn máy", "XeMayDien": "Xe máy điện",
        "XeTuongTuXeMoTo": "Các loại xe tương tự xe mô tô", "XeTuongTuXeGanMay": "Các loại xe tương tự xe gắn máy",
        "XeMayChuyenDung": "Xe máy chuyên dùng", "XeThoSo": "Xe thô sơ", "XeDap": "Xe đạp",
        "XeDapMay": "Xe đạp máy", "XeDapDien": "Xe đạp điện",
        "Nguoi": "Người", "NguoiDieuKhien": "Người điều khiển phương tiện", "ChuXe": "Chủ phương tiện",
        "NguoiThiHanhCongVu": "Người thi hành công vụ",
        "NguoiKhongDuDieuKienDieuKhienXe": "Người không đủ điều kiện điều khiển xe (suy ra từ vi phạm của chính họ)",
        "LoaiDuong": "Loại đường", "DuongCaoToc": "Đường cao tốc", "DuongMotChieu": "Đường một chiều",
        "KhuDanCu": "Đường trong khu dân cư", "NgoaiKhuDanCu": "Đường ngoài khu dân cư",
        "VuViec": "Vụ việc", "HanhVi": "Hành vi", "HanhViDieuKhienXe": "Hành vi điều khiển xe",
        "HanhViGiaoXe": "Hành vi giao xe / để người khác điều khiển xe",
        "HanhViViPham": "Hành vi vi phạm hành chính",
        "DauHieuSuKien": "Dấu hiệu sự kiện (định nghĩa bằng giá trị quan sát)",
        "MucNongDoCon": "Mức nồng độ cồn", "MucVuotTocDo": "Mức vượt tốc độ", "NhomTuoi": "Nhóm tuổi",
        "NhomDungTichCongSuat": "Nhóm dung tích xi-lanh / công suất",
        "TinhTiet": "Tình tiết", "TinhTietTangNang": "Tình tiết tăng nặng", "TinhTietGiamNhe": "Tình tiết giảm nhẹ",
        "VanBan": "Văn bản quy phạm", "NghiDinh": "Nghị định", "PhienBanPhapLy": "Phiên bản pháp lý",
        "DieuKhoan": "Điều khoản", "Dieu": "Điều", "Khoan": "Khoản", "Diem": "Điểm",
        "KhungPhat": "Khung phạt tiền", "HinhThucXuPhat": "Hình thức xử phạt", "PhatCanhCao": "Phạt cảnh cáo",
        "HinhThucBoSung": "Hình thức xử phạt bổ sung", "TuocGPLX": "Tước quyền sử dụng GPLX",
        "TichThuPhuongTien": "Tịch thu phương tiện", "TichThuTangVat": "Tịch thu tang vật",
        "BienPhapKhac": "Biện pháp khác", "TruDiemGPLX": "Trừ điểm GPLX", "TamGiuPhuongTien": "Tạm giữ phương tiện",
        "BienPhapKhacPhucHauQua": "Biện pháp khắc phục hậu quả", "QuyTac": "Quy tắc suy luận (luật SWRL)",
    }
    for name, vi in labels.items():
        label(onto[name], vi)
    for name, vi in {
        "dieuKhien": "điều khiển", "laChuSoHuu": "là chủ sở hữu", "coHanhVi": "có hành vi",
        "thuocVuViec": "thuộc vụ việc", "chuThe": "chủ thể thực hiện", "suDungPhuongTien": "sử dụng phương tiện",
        "giaoXeCho": "giao xe cho", "trenLoaiDuong": "trên loại đường", "apDungPhienBan": "áp dụng phiên bản",
        "viPhamHanhVi": "vi phạm hành vi", "apDungDieuKhoan": "áp dụng điều khoản", "coTinhTiet": "có tình tiết",
        "duocSuyRaBoi": "được suy ra bởi (quy tắc)", "thuocDieuKhoan": "thuộc điều khoản (bắc cầu)",
        "thuocDieuKhoanCha": "thuộc điều khoản cha trực tiếp", "thuocVanBan": "thuộc văn bản",
        "duocSuaDoiBoi": "được sửa đổi bởi", "thuocPhienBan": "thuộc phiên bản", "gomVanBan": "gồm văn bản",
        "coKhungPhat": "có khung phạt", "chiuKhungPhat": "chịu khung phạt",
        "coHinhThucBoSung": "có hình thức xử phạt bổ sung", "coBienPhapKhac": "có biện pháp khác",
        "canCuDieuKhoan": "căn cứ điều khoản", "apDungChoPhienBan": "áp dụng cho phiên bản",
    }.items():
        label(onto[name], vi)
    label(onto.canCuPhapLy, "căn cứ pháp lý (id phần tử + trích dẫn)")
    label(onto.maHanhVi, "mã hành vi")
    return types.SimpleNamespace(**{e.name: e for e in list(onto.classes()) + list(onto.properties())})


# ---------------------------------------------------------------------------
# Khái niệm định nghĩa từ cấu hình
# ---------------------------------------------------------------------------


def _facets(spec: dict) -> dict:
    return {k: spec[k] for k in ("min_inclusive", "min_exclusive", "max_inclusive", "max_exclusive") if k in spec}


def build_defined_classes(onto, cfg: dict) -> None:
    """Sinh lớp ngưỡng (ràng buộc kiểu dữ liệu), lớp hợp và lớp dấu hiệu sự kiện."""
    with onto:
        for t in cfg["thresholds"]:
            base, prop = onto[t["cls"]], onto[t["property"]]
            dt_ = ConstrainedDatatype(PY_TYPES[t["datatype"]], **_facets(t))
            c = types.new_class(t["name"], (onto[t["group"]],))
            c.equivalent_to = [base & prop.some(dt_)]
            label(c, t["label"])
            c.canCuPhapLy = [f"{e['version']}:{e['id']} — “{e['phrase']}”" for e in t["evidence"]]
        for u in cfg["unions"]:
            c = types.new_class(u["name"], (onto[u["group"]],))
            c.equivalent_to = [Or([onto[x] for x in u["of"]])]
            label(c, u["label"], u.get("note"))
        for o in cfg["observations"]:
            expr = onto[o["cls"]]
            for p, v in o.get("values", {}).items():
                expr = expr & onto[p].value(v)
            for p, cls in (o.get("some") or {}).items():
                expr = expr & onto[p].some(onto[cls])
            c = types.new_class(o["name"], (onto.DauHieuSuKien,))
            c.equivalent_to = [expr]
            label(c, o["label"])


def build_behavior_classes(onto, behaviors: list[dict], versions: list[str]) -> None:
    """Sinh lớp hành vi vi phạm ``HV_<mã>`` dưới lớp nhóm tương ứng."""
    with onto:
        for key, (cname, vi) in BEHAVIOR_GROUPS.items():
            g = types.new_class(cname, (onto.HanhViViPham,))
            label(g, vi)
        for b in behaviors:
            parent = onto[BEHAVIOR_GROUPS[b["nhom"]][0]]
            c = types.new_class(f"HV_{b['code']}", (parent,))
            label(c, b["ten"], b.get("note"))
            c.maHanhVi = [b["code"]]
            refs = list(b["refs"]) + [b["refs"][-1]] * (len(versions) - len(b["refs"]))
            c.canCuPhapLy = [f"{v}:{r}" for v, r in zip(versions, refs) if r]


# ---------------------------------------------------------------------------
# ABox: văn bản, phiên bản, điều khoản
# ---------------------------------------------------------------------------

DOC_LABEL = {"ND100": "NĐ 100/2019", "ND123": "NĐ 123/2021", "ND168": "NĐ 168/2024", "ND238": "NĐ 238/2026"}


def cite(r: dict) -> str:
    bits = []
    if r["diem"]:
        bits.append(f"điểm {r['diem']}")
    if r["khoan"]:
        bits.append(f"khoản {r['khoan']}")
    bits.append(f"Điều {r['dieu']}")
    return " ".join(bits) + " " + DOC_LABEL.get(r["doc"], r["doc"])


def _date(s) -> dt.datetime:
    """Ngày → xsd:dateTime lúc 00:00 (xsd:date không được HermiT hỗ trợ)."""
    d = dt.date.fromisoformat(s) if isinstance(s, str) else s
    return dt.datetime(d.year, d.month, d.day)


def build_abox(onto, sources: dict, behaviors: list[dict], concepts: dict) -> dict[str, int]:
    """Tạo cá thể văn bản, phiên bản, điều khoản (MVP) và khung phạt."""
    versions = list(sources["versions"])
    stats = {"van_ban": 0, "phien_ban": 0, "dieu_khoan": 0, "khung_phat": 0}
    with onto:
        docs = {}
        for key, m in sources["documents"].items():
            d = onto.NghiDinh(key)
            d.soHieu = m["so_hieu"]
            d.ngayBanHanh = _date(m["ngay_ban_hanh"])
            d.hieuLucTu = _date(m["effective_from"])
            label(d, f"Nghị định {m['so_hieu']}", m.get("ten"))
            docs[key] = d
            stats["van_ban"] += 1
        pbs = {}
        for v, m in sources["versions"].items():
            pb = onto.PhienBanPhapLy(v)
            pb.maPhienBan = v
            pb.hieuLucTu = _date(m["effective_from"])
            if m.get("effective_to"):
                pb.hieuLucDen = _date(m["effective_to"])
            label(pb, f"{v}: {m['label']}")
            pbs[v] = pb
            stats["phien_ban"] += 1
        # nguồn văn bản của từng phiên bản
        def srcs(v):
            b = sources["versions"][v]["build"]
            base = srcs(b["base_version"]) if "base_version" in b else [b["base"]]
            return base + list(b.get("amendments", []))
        for v in versions:
            pbs[v].gomVanBan = [docs[k] for k in srcs(v)]

        # Tập id cần đưa vào ontology theo phiên bản
        wanted: dict[str, set[str]] = {v: set() for v in versions}
        for b in behaviors:
            refs = list(b["refs"]) + [b["refs"][-1]] * (len(versions) - len(b["refs"]))
            for v, r in zip(versions, refs):
                if r:
                    wanted[v].add(r)
        for t in concepts["thresholds"]:
            for e in t["evidence"]:
                wanted[e["version"]].add(e["id"])

        for v in versions:
            arts = {r["id"]: r for r in map(json.loads, (PROCESSED_DIR / f"articles_{v.lower()}.jsonl")
                                             .open(encoding="utf-8"))}
            closure = set()
            for rid in wanted[v]:
                r = arts[rid]
                while r is not None:
                    closure.add(r["id"])
                    r = arts.get(r["parent_id"]) if r["parent_id"] else None
            for rid in sorted(closure):
                r = arts[rid]
                ind = onto[LEVEL_CLASS[r["level"]]](prov_iri(v, rid))
                ind.maDieuKhoan = rid
                ind.trichDan = cite(r)
                ind.noiDung = r["text"]
                ind.trangThai = r["status"]
                ind.thuocPhienBan = pbs[v]
                ind.thuocVanBan = [docs[r["doc"]]]
                if r["effective_from"]:
                    ind.hieuLucTu = _date(r["effective_from"])
                else:
                    ind.hieuLucChuaXacDinh = True
                if r["effective_to"]:
                    ind.hieuLucDen = _date(r["effective_to"])
                if r["history"] or r["history_inherited"]:
                    ind.duocSuaDoiBoi = [docs[k] for k in r["nguon_hop_nhat"][1:]]
                label(ind, f"{v} — {cite(r)}")
                stats["dieu_khoan"] += 1
                kp = r["khung_phat"]
                if r["level"] == "khoan" and kp:
                    k = onto.KhungPhat(f"KP_{prov_iri(v, rid)}")
                    k.mucToiThieu, k.mucToiDa = kp["ca_nhan"]
                    k.doiTuongApDung = "ca_nhan"
                    label(k, f"{kp['ca_nhan'][0]:,}–{kp['ca_nhan'][1]:,} đồng ({v} {cite(r)})".replace(",", "."))
                    ind.coKhungPhat = [k]
                    stats["khung_phat"] += 1
                    if kp.get("to_chuc"):
                        k2 = onto.KhungPhat(f"KP_TC_{prov_iri(v, rid)}")
                        k2.mucToiThieu, k2.mucToiDa = kp["to_chuc"]
                        k2.doiTuongApDung = "to_chuc"
                        ind.coKhungPhat.append(k2)
                        stats["khung_phat"] += 1
            # quan hệ cha – con
            for rid in closure:
                pid = arts[rid]["parent_id"]
                if pid:
                    onto[prov_iri(v, rid)].thuocDieuKhoanCha = onto[prov_iri(v, pid)]
    return stats


def build(out: Path = OUT_FILE) -> Path:
    """Dựng toàn bộ ontology và ghi ra file RDF/XML."""
    from src.ingest.build_articles import load_sources

    sources = load_sources()
    concepts = yaml.safe_load(CONCEPTS_FILE.read_text(encoding="utf-8"))
    behaviors = yaml.safe_load(BEHAVIORS_FILE.read_text(encoding="utf-8"))["behaviors"]
    versions = list(sources["versions"])

    world = World()
    onto = world.get_ontology(ONTO_IRI)
    with onto:
        onto.metadata.comment = [locstr(
            "Ontology hệ chuyên gia tư vấn vi phạm luật giao thông đường bộ. Sinh tự động bởi "
            "src/kb/build_ontology.py — không sửa tay; sửa config/*.yaml rồi chạy lại.", lang="vi")]
    build_tbox(onto)
    build_defined_classes(onto, concepts)
    build_behavior_classes(onto, behaviors, versions)
    stats = build_abox(onto, sources, behaviors, concepts)
    out.parent.mkdir(parents=True, exist_ok=True)
    onto.save(file=str(out), format="rdfxml")
    n_cls, n_prop = len(list(onto.classes())), len(list(onto.properties()))
    logger.info("Ontology: {} lớp, {} thuộc tính, cá thể {} -> {}", n_cls, n_prop, stats,
                out.relative_to(ROOT_DIR))
    return out


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    build()
