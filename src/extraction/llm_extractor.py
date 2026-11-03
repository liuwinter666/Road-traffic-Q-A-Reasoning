"""Trích xuất hồ sơ vụ việc từ lời người dùng.

Ba bước:
  1. ``LLMExtractor.trich_xuat``: LLM chép cụm từ bề mặt vào ``TrichXuatLLM`` (prompt ``extraction`` có phiên bản).
  1b. ``grounding.kiem_chung``: tất định — bỏ cụm từ không có trong lời người dùng (chống LLM tự thêm thông tin).
  2. ``xay_dung_ho_so``: tất định — normalizer chuẩn hóa số/đơn vị/ngày; entity_linker ánh xạ cụm từ vào node
     ontology; ghi nguồn gốc và giả định cho từng trường.

Bước 2 không gọi LLM nên test được độc lập; bước 1 test bằng LLM giả (mock).
"""

from __future__ import annotations

from datetime import date

from loguru import logger

from src.config import ROOT_DIR
from src.extraction import normalizer as N
from src.extraction.entity_linker import EntityLinker
from src.extraction.grounding import kiem_chung
from src.extraction.schema import DauHieu, HoSoVuViec, NguonGoc, TrichXuatLLM
from src.llm.client import LLMClient, get_llm_client
from src.llm.prompts import load_prompt

PHAN_LOAI_FILE = ROOT_DIR / "config" / "phan_loai_xe.yaml"
XE_CHUNG_CHUNG = {"xe", "tôi", "của", "mình", "em", "anh", "chị", "bạn", "chiếc", "cái", "con", "nó", "này", "đó",
                  "ấy", "nhà", "cũ", "mới", "kia", "đấy"}


def phan_loai_xe_may(dung_tich: float | None, cong_suat: float | None, ngay: date) -> tuple[str, str] | None:
    """'xe máy' chung chung → (lớp, giải thích) theo luật có hiệu lực tại ``ngay``; None nếu không đủ dữ liệu."""
    import yaml

    from src.kb.temporal import chon_van_ban_bo_tro

    vb = chon_van_ban_bo_tro("phan_loai_xe", ngay)
    if vb.van_ban is None:
        return None
    rules = yaml.safe_load(PHAN_LOAI_FILE.read_text(encoding="utf-8"))["theo_van_ban"][vb.van_ban]
    for val, key, gm, mt, dv in ((dung_tich, "dung_tich", "XeGanMay", "XeMoToHaiBanh", "cm3"),
                                 (cong_suat, "cong_suat", "XeMayDien", "XeMoToHaiBanh", "kW")):
        if val is None:
            continue
        r = rules[key]
        is_gm = val < r["nguong"] if r["so_sanh"] == "<" else val <= r["nguong"]
        cls = gm if is_gm else mt
        return cls, (f"Xe {val:g} {dv} được xếp là {'xe gắn máy' if is_gm else 'xe mô tô hai bánh'} "
                     f"theo {r['id']} (“{r['trich']}”)")
    return None


def xay_dung_ho_so(tx: TrichXuatLLM, linker: EntityLinker, hom_nay: date | None = None) -> HoSoVuViec:
    """Chuẩn hóa đầu ra LLM thành hồ sơ vụ việc."""
    hs = HoSoVuViec()
    today = hom_nay or date.today()

    def note(field: str, goc: str | None, pp: str = "normalizer", tin_cay: float = 1.0, ghi_chu=None):
        hs.nguon[field] = NguonGoc(goc=goc, phuong_phap=pp, do_tin_cay=tin_cay, ghi_chu=list(ghi_chu or []))
        hs.gia_dinh.extend(ghi_chu or [])

    if tx.thoi_diem and (td := N.thoi_diem(tx.thoi_diem, today)):
        hs.ngay_tu, hs.ngay_den, hs.do_chinh_xac_ngay = td.tu, td.den, td.do_chinh_xac
        note("ngay", tx.thoi_diem, ghi_chu=td.gia_dinh)
    if tx.tuoi_nguoi_lai and (t := N.tuoi(tx.tuoi_nguoi_lai, hs.ngay_vi_pham, today)):
        hs.tuoi_nguoi_lai = int(t.gia_tri)
        note("tuoi_nguoi_lai", tx.tuoi_nguoi_lai, ghi_chu=t.gia_dinh)
    if tx.tuoi_chu_xe and (t := N.tuoi(tx.tuoi_chu_xe, hs.ngay_vi_pham, today)):
        hs.tuoi_chu_xe = int(t.gia_tri)
        note("tuoi_chu_xe", tx.tuoi_chu_xe, ghi_chu=t.gia_dinh)
    if tx.dung_tich_xi_lanh and (d := N.dung_tich(tx.dung_tich_xi_lanh)):
        hs.dung_tich_xi_lanh = d.gia_tri
        note("dung_tich_xi_lanh", tx.dung_tich_xi_lanh, ghi_chu=d.gia_dinh)
    if tx.cong_suat_dong_co and (c := N.cong_suat(tx.cong_suat_dong_co)):
        hs.cong_suat_dong_co_dien = c.gia_tri
        note("cong_suat_dong_co_dien", tx.cong_suat_dong_co, ghi_chu=c.gia_dinh)
    if tx.nong_do_con:
        dl, loai = N.nong_do_con(tx.nong_do_con)
        if dl and loai == "khi_tho":
            hs.nong_do_con_khi_tho = dl.gia_tri
            note("nong_do_con_khi_tho", tx.nong_do_con, ghi_chu=dl.gia_dinh)
        elif dl and loai == "mau":
            hs.nong_do_con_mau = dl.gia_tri
            note("nong_do_con_mau", tx.nong_do_con, ghi_chu=dl.gia_dinh)
        else:
            hs.khong_lien_ket.append(f"nồng độ cồn: {tx.nong_do_con}")
    for fld, raw in (("toc_do_thuc_te", tx.toc_do_thuc_te), ("toc_do_toi_da", tx.toc_do_toi_da)):
        if raw and (v := N.toc_do(raw)):
            setattr(hs, fld, v.gia_tri)
            note(fld, raw, ghi_chu=v.gia_dinh)

    # Loại xe — cụm chỉ gồm "xe" + đại từ/lượng từ ("xe tôi", "chiếc xe") không cho biết loại xe: bỏ qua, không để
    # embedding đoán (đo được: "xe tôi" → ô tô 0.80, "xe" → xe khách 0.85)
    if tx.loai_xe and not (set(N.chuan_hoa_chu(tx.loai_xe).split()) - XE_CHUNG_CHUNG):
        hs.khong_lien_ket.append(f"loại xe: {tx.loai_xe}")
    elif tx.loai_xe:
        lk = linker.link_one(tx.loai_xe, "xe")
        if lk:
            hs.loai_xe = lk.node
            note("loai_xe", tx.loai_xe, lk.phuong_phap, lk.diem)
        else:
            hs.khong_lien_ket.append(f"loại xe: {tx.loai_xe}")
    if hs.loai_xe in ("NhomXeMoTo", "XeMayDien") and (hs.dung_tich_xi_lanh or hs.cong_suat_dong_co_dien):
        dt = hs.dung_tich_xi_lanh if hs.loai_xe == "NhomXeMoTo" else None
        if pl := phan_loai_xe_may(dt, hs.cong_suat_dong_co_dien, hs.ngay_tu or today):
            hs.loai_xe = pl[0]
            note("loai_xe", tx.loai_xe, "suy_ra", 1.0, [pl[1]])

    # Đường
    for raw in tx.loai_duong:
        for lk in linker.link(raw, ["duong", "dac_diem_duong"]):
            if lk.kieu == "duong":
                if lk.node not in hs.loai_duong:
                    hs.loai_duong.append(lk.node)
                if lk.node in ("KhuDanCu", "NgoaiKhuDanCu"):
                    hs.khu_dong_dan_cu = lk.node == "KhuDanCu"
            else:
                hs.duong_doi = lk.node == "duong_doi"
        if not linker.link(raw, ["duong", "dac_diem_duong"]):
            hs.khong_lien_ket.append(f"đường: {raw}")

    # Sự kiện → dấu hiệu, tình tiết, gợi ý
    for sk in tx.su_kien:
        links = linker.link(sk.mo_ta, ["dau_hieu", "tinh_tiet", "goi_y"])
        if not links and sk.trich_dan:
            links = linker.link(sk.trich_dan, ["dau_hieu", "tinh_tiet", "goi_y"])
        if not links:
            hs.khong_lien_ket.append(sk.mo_ta)
            continue
        # Đèn vàng: cụm chung "vượt đèn" không đủ để kết luận không chấp hành tín hiệu — theo quy tắc đèn vàng
        # (khoản 4 Điều 11 Luật TTATGT; khoản 3 Điều 10 Luật GTĐB 2008), đã đi trên/qua vạch dừng hoặc đèn vàng
        # nhấp nháy thì được đi tiếp. Bỏ liên kết đó; slot_checker hỏi chi tiết, fact_inducer suy ra từ câu trả lời.
        if any(lk.node == "_DEN_VANG" for lk in links):
            links = [lk for lk in links if not (lk.node == "KhongChapHanhDenTinHieu" and "đỏ" not in lk.goc)]
        for lk in links:
            hs.dau_hieu.append(DauHieu(node=lk.node, kieu=lk.kieu, su_kien=lk.su_kien, goc=lk.goc,
                                       trich_dan=sk.trich_dan, phuong_phap=lk.phuong_phap,
                                       do_tin_cay=lk.diem, phu_dinh=sk.phu_dinh))
            if sk.phu_dinh:
                continue
            for k, v in lk.su_kien.items():
                hs.su_kien[k] = v
                hs.nguon[f"su_kien.{k}"] = NguonGoc(goc=lk.goc, phuong_phap=lk.phuong_phap, do_tin_cay=lk.diem)
            if lk.node in ("XeKinhDoanhVanTai", "XeKhongKinhDoanhVanTai"):
                hs.kinh_doanh_van_tai = lk.node == "XeKinhDoanhVanTai"
    if tx.nguoi_lai_khong_phai_chu_xe is not None:
        hs.chu_xe_giao_xe = tx.nguoi_lai_khong_phai_chu_xe
        note("chu_xe_giao_xe", "nguoi_lai_khong_phai_chu_xe", "llm")
    elif "_GIAO_XE" in hs.goi_y():
        hs.chu_xe_giao_xe = True
        note("chu_xe_giao_xe", "_GIAO_XE", "tu_dien", 0.85)
    hs.gia_dinh = list(dict.fromkeys(hs.gia_dinh))
    return hs


class LLMExtractor:
    """Trích xuất bằng LLM + chuẩn hóa."""

    def __init__(self, client: LLMClient | None = None, linker: EntityLinker | None = None,
                 prompt_version: int | None = None, kiem_chung_cum_tu: bool = True):
        self.client = client or get_llm_client()
        self.linker = linker or EntityLinker()
        self.prompt = load_prompt("extraction", prompt_version)
        self.kiem_chung_cum_tu = kiem_chung_cum_tu      # tắt được cho thí nghiệm ablation
        self.loai_bo_lan_cuoi: list[str] = []

    def trich_xuat(self, tin_nhan: str, hom_nay: date | None = None, cau_hoi_truoc: list[str] | None = None) -> TrichXuatLLM:
        today = hom_nay or date.today()
        ngu_canh = ("Câu hỏi hệ thống vừa hỏi người dùng:\n" + "\n".join(f"- {q}" for q in cau_hoi_truoc)
                    if cau_hoi_truoc else "")
        prompt = self.prompt.render(hom_nay=today.strftime("%d/%m/%Y"), ngu_canh=ngu_canh, tin_nhan=tin_nhan)
        out = self.client.generate_structured(prompt, TrichXuatLLM, system=self.prompt.system)
        logger.debug("Trích xuất ({}): {}", self.prompt.ma, out.model_dump(exclude_defaults=True))
        self.loai_bo_lan_cuoi = []
        if self.kiem_chung_cum_tu:
            kq = kiem_chung(out, tin_nhan)
            out, self.loai_bo_lan_cuoi = kq.trich_xuat, kq.loai_bo
            for x in kq.loai_bo:
                logger.warning("Kiểm chứng cụm từ: {}", x)
        return out

    def ho_so(self, tin_nhan: str, hom_nay: date | None = None, cau_hoi_truoc: list[str] | None = None) -> HoSoVuViec:
        hs = xay_dung_ho_so(self.trich_xuat(tin_nhan, hom_nay, cau_hoi_truoc), self.linker, hom_nay)
        hs.cum_tu_loai_bo = list(self.loai_bo_lan_cuoi)
        return hs
