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
from functools import lru_cache
from datetime import date

import re

import yaml

from src.config import ROOT_DIR
from src.extraction.schema import HoSoVuViec
from src.kb.temporal import chon_phien_ban
from src.kb.toc_do import tra_toc_do_toi_da

SLOTS_FILE = ROOT_DIR / "config" / "slots.yaml"
XE_MO_TO = {"NhomXeMoTo", "XeMoTo", "XeMoToHaiBanh", "XeMoToBaBanh", "XeTuongTuXeMoTo"}
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
    # với câu xác nhận: đúng các mục được hỏi ("loai_xe", "lien_ket:<node>|<cụm>", "su_kien:<thuộc tính>") —
    # câu trả lời có/không chỉ áp cho các mục này
    muc_xac_nhan: list[str] = field(default_factory=list)


@dataclass
class KetQuaSlot:
    du_thong_tin: bool
    cau_hoi: list[CauHoi] = field(default_factory=list)
    phien_ban: str | None = None
    ghi_chu: list[str] = field(default_factory=list)


def _cfg() -> dict:
    return yaml.safe_load(SLOTS_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _quan_sat() -> list[dict]:
    """Lớp dấu hiệu định nghĩa bằng giá trị boolean (config/ontology_concepts.yaml → observations)."""
    cfg = yaml.safe_load((ROOT_DIR / "config" / "ontology_concepts.yaml").read_text(encoding="utf-8"))
    return [o for o in cfg["observations"] if "some" not in o]


@lru_cache(maxsize=1)
def _nhan() -> dict[str, str]:
    cfg = yaml.safe_load((ROOT_DIR / "config" / "ontology_concepts.yaml").read_text(encoding="utf-8"))
    out = {o["name"]: o["label"] for o in cfg["observations"]}
    out.update({t["fact"]: t["label"] for t in cfg["tinh_tiet_facts"]})
    return out


def nhan_node(node: str) -> str:
    """Nhãn tiếng Việt của node (dấu hiệu / tình tiết) để hỏi người dùng — không lộ tên nội bộ."""
    return _nhan().get(node, node).lower()


def loai_xe_cho_xac_nhan(hs: HoSoVuViec) -> bool:
    """Loại xe ánh xạ bằng embedding, chưa được người dùng xác nhận."""
    g = hs.nguon.get("loai_xe")
    return hs.loai_xe is not None and g is not None and g.phuong_phap == "embedding"


def cho_xac_nhan_lien_ket(hs: HoSoVuViec) -> list:
    """Dấu hiệu/tình tiết liên kết bằng embedding, chưa được người dùng xác nhận."""
    return [d for d in hs.dau_hieu if d.phuong_phap == "embedding" and not d.phu_dinh and d.kieu != "goi_y"]


def nodes_hieu_luc(hs: HoSoVuViec) -> set[str]:
    """Dấu hiệu đã liên kết + dấu hiệu được thỏa bởi sự kiện boolean trong hồ sơ (kể cả sự kiện suy ra đã chấp
    nhận) — để câu hỏi không lặp lại điều fact_inducer đã xác định."""
    out = set(hs.nodes())
    for o in _quan_sat():
        if all(hs.su_kien.get(k) == v for k, v in o["values"].items()):
            out.add(o["name"])
    return out


def co_the_suy_ra_toc_do_toi_da(hs: HoSoVuViec, ngay: date) -> tuple[bool, str | None]:
    """(có tra được bảng tốc độ không, trường còn thiếu để tra) — cùng hàm tra với fact_builder
    (``src/kb/toc_do.py``), theo thông tư có hiệu lực tại ``ngay``."""
    tc = tra_toc_do_toi_da(hs.loai_xe, ngay, hs.khu_dong_dan_cu, hs.duong_doi, hs.loai_duong)
    return tc.tra_duoc, tc.thieu


def kiem_tra(hs: HoSoVuViec, hom_nay: date | None = None) -> KetQuaSlot:
    """Danh sách câu hỏi làm rõ (rỗng nếu đủ thông tin để suy luận)."""
    cfg = _cfg()
    today = hom_nay or date.today()
    nodes, hints = nodes_hieu_luc(hs), hs.goi_y()
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

    # Hành vi đã được kể nhưng không ánh xạ được (ngoài phạm vi MVP) cũng tính là "đã mô tả": không hỏi lại mãi,
    # để pipeline trả "không phát hiện" kèm gợi ý tra cứu
    hanh_vi_ngoai_pham_vi = [x for x in hs.khong_lien_ket if not re.match(r"^(loại xe|đường|nồng độ cồn): ", x)]
    co_su_kien = bool(nodes) or any(x is not None for x in (
        hs.nong_do_con_khi_tho, hs.nong_do_con_mau, hs.toc_do_thuc_te)) or bool(hs.su_kien) \
        or bool(hanh_vi_ngoai_pham_vi)
    if not co_su_kien:
        need["mo_ta_hanh_vi"] = ""

    # Loại xe
    phu_thuoc_xe = (nodes - KHONG_PHU_THUOC_XE - {d.node for d in hs.dau_hieu if d.kieu == "tinh_tiet"}) \
        or hs.toc_do_thuc_te is not None or hs.nong_do_con_khi_tho is not None or hs.nong_do_con_mau is not None
    if hs.loai_xe is None and phu_thuoc_xe:
        need["loai_xe"] = ""

    # Đèn vàng: kết luận phụ thuộc vị trí xe so với vạch dừng / đèn nhấp nháy (quy tắc đèn vàng của luật)
    if "_DEN_VANG" in hints and "khongChapHanhDenTinHieu" not in hs.su_kien:
        need["den_vang"] = ""

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

    qs = []
    for truong, extra in need.items():
        c = cfg["cau_hoi"][truong]
        text = c["cau_hoi"].format(mo_ta=extra) if extra else c["cau_hoi"]
        qs.append(CauHoi(truong, text, c["ly_do"], c["uu_tien"]))

    # Xác nhận: liên kết bằng embedding (dấu hiệu/tình tiết — gợi ý "_..." chỉ dùng để chọn câu hỏi nên không cần
    # xác nhận), sự kiện suy ra có độ tin cậy vừa phải. Gộp thành MỘT câu hỏi, hỏi riêng một lượt (trước các câu
    # khác) để câu trả lời "có"/"không" áp đúng cho đúng những mục đã hỏi.
    lien_ket = cho_xac_nhan_lien_ket(hs)
    muc = [f"“{d.goc}” nghĩa là {nhan_node(d.node)}" for d in lien_ket]
    khoa = [f"lien_ket:{d.node}|{d.goc}" for d in lien_ket]
    if loai_xe_cho_xac_nhan(hs):
        from src.explanation.tracer import nhan

        muc.insert(0, f"xe của bạn (“{hs.nguon['loai_xe'].goc}”) là {nhan(hs.loai_xe).lower()}")
        khoa.insert(0, "loai_xe")
    nhom: dict[str, list] = {}
    for sk in hs.su_kien_suy_ra:
        # đèn vàng: hỏi chi tiết vạch dừng trước, không hỏi xác nhận suy đoán của LLM về cùng thuộc tính
        if sk.trang_thai == "cho_xac_nhan" and not (sk.thuoc_tinh == "khongChapHanhDenTinHieu" and "den_vang" in need):
            nhom.setdefault(sk.bang_chung, []).append(sk)
    muc += [f"{'; '.join(x.mo_ta() for x in ds)} (từ “{bc}”)" for bc, ds in nhom.items()]
    khoa += [f"su_kien:{x.thuoc_tinh}" for ds in nhom.values() for x in ds]
    if muc:
        c = cfg["cau_hoi"]["xac_nhan"]
        text = muc[0] if len(muc) == 1 else " ".join(f"({i}) {m};" for i, m in enumerate(muc, 1)).rstrip(";")
        return KetQuaSlot(False, [CauHoi("xac_nhan", c["cau_hoi"].format(mo_ta=text), c["ly_do"], 0, khoa)],
                          v, ghi_chu)

    qs.sort(key=lambda q: q.uu_tien)
    return KetQuaSlot(not qs, qs[: cfg["so_cau_hoi_toi_da"]], v, ghi_chu)
