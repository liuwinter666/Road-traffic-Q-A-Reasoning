"""Test Phase 5: tra tốc độ, fact_inducer (LLM giả), fact_builder, pipeline đầu-cuối (LLM giả + reasoner thật)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from src.extraction.entity_linker import EntityLinker
from src.extraction.llm_extractor import LLMExtractor, xay_dung_ho_so
from src.extraction.schema import HoSoVuViec, NguonGoc, TrichXuatLLM
from src.inference.fact_builder import xay_dung
from src.inference.fact_inducer import FactInducer, danh_muc, dinh_nghia_phap_ly
from src.inference.pipeline import PhienLamViec, Pipeline, tra_loi_co_khong
from src.kb.toc_do import tra_toc_do_toi_da
from src.llm.client import DiskCache, LLMClient

T = date(2026, 11, 4)


# ---------------- tra tốc độ tối đa ----------------

@pytest.mark.parametrize("xe,ngay,kdc,doi,duong,gia_tri,thieu,vb", [
    ("OTo", date(2025, 3, 10), True, True, [], 60, None, "TT38"),
    ("OTo", date(2025, 3, 10), False, False, [], 80, None, "TT38"),
    ("XeMoToHaiBanh", date(2023, 5, 1), False, True, [], 70, None, "TT31"),
    ("XeGanMay", date(2025, 3, 10), None, None, [], 40, None, "TT38"),        # mọi loại đường
    ("NhomXeMoTo", date(2025, 3, 10), True, True, [], None, "dung_tich", "TT38"),
    ("OTo", date(2025, 3, 10), None, None, [], None, "dac_diem_duong", "TT38"),
    ("OTo", date(2025, 3, 10), None, None, ["DuongCaoToc"], None, "toc_do_toi_da", "TT38"),
    (None, date(2025, 3, 10), True, True, [], None, "loai_xe", "TT38"),
])
def test_tra_toc_do(xe, ngay, kdc, doi, duong, gia_tri, thieu, vb):
    tc = tra_toc_do_toi_da(xe, ngay, kdc, doi, duong)
    assert (tc.gia_tri, tc.thieu, tc.van_ban) == (gia_tri, thieu, vb)
    if gia_tri:
        assert tc.can_cu["id"].startswith(vb) and str(gia_tri) in tc.can_cu["nguyen_van"]


# ---------------- trả lời có / không ----------------

@pytest.mark.parametrize("msg,ok", [("đúng", True), ("Đúng rồi", True), ("có", True), ("ừ", True), ("dung", True),
                                    ("không", False), ("Không phải", False), ("sai", False), ("ko", False),
                                    ("dừng lại rồi", None), ("xe máy", None)])
def test_tra_loi_co_khong(msg, ok):
    assert tra_loi_co_khong(msg)[0] is ok


# ---------------- fact_inducer (phần tất định) ----------------

def _sk(t, v, c, bc, gt=""):
    return {"thuoc_tinh": t, "gia_tri": v, "do_tin_cay": c, "bang_chung": bc, "giai_thich": gt}


def test_danh_muc_tu_ontology():
    dm = danh_muc()
    assert {"chapHanhHieuLenh", "coHieuLenhDungXe", "boChay", "taiPham", "doiMuBaoHiem"} <= set(dm)
    assert "gplxDangBiTuoc" not in dm and "thoiDiemKhongRo" not in dm and "hieuLucMotPhan" not in dm


def test_dinh_nghia_theo_ngay():
    assert [d["id"] for d in dinh_nghia_phap_ly(date(2023, 1, 1))] == ["GTDB2008-D3-K25", "GTDB2008-D10-K3-c"]
    d = {x["id"]: x for x in dinh_nghia_phap_ly(date(2026, 1, 1))}
    assert set(d) == {"LTTATGT-D2-K10", "LTTATGT-D11-K4-b"}
    assert "Cảnh sát giao thông" in d["LTTATGT-D2-K10"]["nguyen_van"]
    assert "vạch dừng" in d["LTTATGT-D11-K4-b"]["nguyen_van"]


def test_ap_dung_phan_loai():
    loi_ke = ["Thấy CSGT vẫy thì em rồ ga chạy luôn, lần trước cũng bị phạt rồi"]
    hs = HoSoVuViec(su_kien={"doiMuBaoHiem": False}, nguon={"su_kien.doiMuBaoHiem": NguonGoc(phuong_phap="tu_dien")})
    FactInducer.ap_dung(hs, [
        _sk("chapHanhHieuLenh", False, 0.9, "rồ ga chạy luôn"),
        _sk("coHieuLenhNguoiDieuKhienGT", True, 0.9, "Thấy CSGT vẫy"),
        _sk("boChay", True, 0.7, "rồ ga chạy luôn"),                      # vừa phải → hỏi lại
        _sk("taiPham", True, 0.95, "lần trước cũng bị phạt rồi"),          # luôn hỏi lại
        _sk("langLachDanhVong", True, 0.9, "lạng lách đánh võng giữa phố"),  # bằng chứng bịa
        _sk("diNguocChieu", True, 0.3, "rồ ga chạy luôn"),                 # tin cậy thấp
        _sk("doiMuBaoHiem", True, 0.9, "rồ ga chạy luôn"),                 # trái sự kiện trực tiếp
    ], loi_ke, T)
    tt = {s.thuoc_tinh: s.trang_thai for s in hs.su_kien_suy_ra}
    assert tt == {"chapHanhHieuLenh": "chap_nhan", "coHieuLenhNguoiDieuKhienGT": "chap_nhan", "boChay": "cho_xac_nhan",
                  "taiPham": "cho_xac_nhan", "langLachDanhVong": "khong_can_cu", "diNguocChieu": "tin_cay_thap",
                  "doiMuBaoHiem": "xung_dot"}
    assert hs.su_kien == {"doiMuBaoHiem": False, "chapHanhHieuLenh": False, "coHieuLenhNguoiDieuKhienGT": True}
    assert hs.nguon["su_kien.chapHanhHieuLenh"].phuong_phap == "suy_ra"
    gt = next(s for s in hs.su_kien_suy_ra if s.thuoc_tinh == "coHieuLenhNguoiDieuKhienGT").giai_thich
    assert "LTTATGT-D2-K10" in gt


def test_ap_dung_khong_ghi_de_xac_nhan():
    hs = HoSoVuViec()
    FactInducer.ap_dung(hs, [_sk("boChay", True, 0.7, "chạy luôn")], ["tôi chạy luôn"], T)
    hs.su_kien_suy_ra[0].trang_thai = "tu_choi"
    FactInducer.ap_dung(hs, [_sk("boChay", True, 0.95, "chạy luôn")], ["tôi chạy luôn"], T)
    assert hs.su_kien_suy_ra[0].trang_thai == "tu_choi" and "boChay" not in hs.su_kien


# ---------------- fact_builder ----------------

def test_fact_builder_tra_toc_do_va_su_kien():
    linker = EntityLinker(embedder=None)
    hs = xay_dung_ho_so(TrichXuatLLM(thoi_diem="10/3/2025", loai_xe="ô tô", toc_do_thuc_te="80 cây",
                                     loai_duong=["trong khu dân cư", "đường đôi"]), linker, T)
    dl = xay_dung(hs, T)
    assert dl.case["ngay"] == date(2025, 3, 10) and dl.case["xe"] == "OTo"
    assert dl.case["su_kien"] == {"tocDoThucTe": 80.0, "tocDoToiDaChoPhep": 60.0}
    assert dl.can_cu_bo_tro[0]["id"] == "TT38-D6-K1" and any("TT38" in g for g in dl.gia_dinh)
    assert dl.case["duong"] == ["KhuDanCu"]


def test_fact_builder_khoang_thoi_gian():
    hs = HoSoVuViec(ngay_tu=date(2023, 3, 1), ngay_den=date(2023, 3, 31), loai_xe="OTo")
    dl = xay_dung(hs, T)
    assert dl.case["ngay"] == date(2023, 3, 1) and "cùng phiên bản V2" in dl.gia_dinh[0]


# ---------------- pipeline đầu-cuối (LLM giả) ----------------

class FakeLLM(LLMClient):
    """Trả lời theo tên schema + tin nhắn cuối cùng xuất hiện trong prompt."""

    provider = "fake"

    def __init__(self, tra_loi: dict[str, dict[str, dict]], tmp_path):
        super().__init__("fake", cache=DiskCache(tmp_path, enabled=False), max_rpm=0)
        self.tra_loi = tra_loi
        self.calls: list[str] = []

    def _call(self, prompt, system, json_schema, schema_model):
        name = schema_model.__name__ if schema_model else "text"
        self.calls.append(name)
        if schema_model is None:                       # generate(): danh sách câu trả lời theo thứ tự gọi
            ds = self.tra_loi.get("text", [""])
            return ds[min(self.calls.count("text"), len(ds)) - 1]
        bang = self.tra_loi.get(name, {})
        khop = [k for k in bang if k in prompt]
        return json.dumps(bang[max(khop, key=prompt.rindex)] if khop else {}, ensure_ascii=False)


MSG1 = "Tối qua thấy CSGT vẫy thì em rồ ga chạy luôn, không đội mũ bảo hiểm"
MSG2 = "xe máy 110 phân khối"
TRICH = {
    MSG1: {"thoi_diem": "Tối qua", "su_kien": [
        {"mo_ta": "thấy CSGT vẫy thì em rồ ga chạy luôn", "trich_dan": "thấy CSGT vẫy thì em rồ ga chạy luôn"},
        {"mo_ta": "không đội mũ bảo hiểm", "trich_dan": "không đội mũ bảo hiểm"}]},
    MSG2: {"loai_xe": "xe máy", "dung_tich_xi_lanh": "110 phân khối"},
}
SUY_RA = {MSG1: {"su_kien": [_sk("coHieuLenhNguoiDieuKhienGT", True, 0.9, "thấy CSGT vẫy"),
                             _sk("chapHanhHieuLenh", False, 0.9, "rồ ga chạy luôn"),
                             _sk("boChay", True, 0.9, "rồ ga chạy luôn")]}}


@pytest.fixture(scope="module")
def reasoner():
    from src.kb.reasoner import TrafficReasoner

    return TrafficReasoner()


def _pipeline(tmp_path, reasoner, tra_loi, **kw):
    """Pipeline với LLM giả; mặc định tắt verbalizer (LLM) và gợi ý RAG (embedding) — test riêng ở test_explanation."""
    fake = FakeLLM(tra_loi, tmp_path)
    kw = {"dung_dien_dat": False, "dung_goi_y_lien_quan": False, **kw}
    return Pipeline(client=fake, extractor=LLMExtractor(client=fake, linker=EntityLinker(embedder=None)),
                    reasoner=reasoner, hom_nay=T, **kw), fake


def test_pipeline_gian_tiep_nhieu_luot(tmp_path, reasoner):
    pl, fake = _pipeline(tmp_path, reasoner, {"TrichXuatLLM": TRICH, "KetQuaSuyRaLLM": SUY_RA})
    phien = PhienLamViec()
    k1 = pl.xu_ly(phien, MSG1)
    assert k1.trang_thai == "can_hoi" and [q.truong for q in k1.cau_hoi] == ["loai_xe"]
    k2 = pl.xu_ly(phien, MSG2)
    assert k2.trang_thai == "ket_luan" and k2.suy_luan.phien_ban == "V4"
    assert k2.suy_luan.ma_hanh_vi == {"XM_HIEU_LENH_CSGT", "XM_MU_BAO_HIEM"}
    assert k2.du_lieu.nguon_su_kien["chapHanhHieuLenh"] == "suy_ra"
    assert k2.quyet_dinh.tong_tien_de_xuat > 0
    from src.inference.report import trinh_bay

    txt = trinh_bay(k2)
    assert "ND168-D7-K7-d" in txt and "suy ra từ lời kể" in txt and "LTTATGT-D2-K10" in txt


def test_pipeline_ablation_khong_suy_ra(tmp_path, reasoner):
    pl, fake = _pipeline(tmp_path, reasoner, {"TrichXuatLLM": TRICH, "KetQuaSuyRaLLM": SUY_RA},
                         dung_fact_inducer=False)
    phien = PhienLamViec()
    pl.xu_ly(phien, MSG1)
    k = pl.xu_ly(phien, MSG2)
    assert k.suy_luan.ma_hanh_vi == {"XM_MU_BAO_HIEM"} and "KetQuaSuyRaLLM" not in fake.calls


@pytest.mark.parametrize("tra_loi,ky_vong", [("đúng", {"XM_HIEU_LENH_CSGT"}), ("không", set())])
def test_pipeline_xac_nhan_su_kien(tmp_path, reasoner, tra_loi, ky_vong):
    msg = "Chạy xe máy 110 phân khối ngày 3/11/2026, thấy chú công an giơ tay thì tôi cứ đi"
    trich = {msg: {"thoi_diem": "3/11/2026", "loai_xe": "xe máy", "dung_tich_xi_lanh": "110 phân khối",
                   "su_kien": [{"mo_ta": "thấy chú công an giơ tay thì tôi cứ đi",
                                "trich_dan": "thấy chú công an giơ tay thì tôi cứ đi"}]}}
    suy_ra = {msg: {"su_kien": [_sk("coHieuLenhNguoiDieuKhienGT", True, 0.7, "chú công an giơ tay"),
                                _sk("chapHanhHieuLenh", False, 0.7, "chú công an giơ tay")]}}
    pl, fake = _pipeline(tmp_path, reasoner, {"TrichXuatLLM": trich, "KetQuaSuyRaLLM": suy_ra})
    phien = PhienLamViec()
    k1 = pl.xu_ly(phien, msg)
    assert k1.trang_thai == "can_hoi" and [q.truong for q in k1.cau_hoi] == ["xac_nhan"]
    assert "chú công an giơ tay" in k1.cau_hoi[0].cau_hoi
    n = len(fake.calls)
    k2 = pl.xu_ly(phien, tra_loi)
    assert len(fake.calls) == n                                   # "đúng"/"không": không gọi LLM
    assert k2.suy_luan.ma_hanh_vi == ky_vong
    assert k2.trang_thai == ("ket_luan" if ky_vong else "khong_phat_hien")


def test_pipeline_ngay_tu_giao_dien(tmp_path, reasoner):
    msg = "Tôi lái ô tô có nồng độ cồn 0,3 mg/l khí thở"
    trich = {msg: {"loai_xe": "ô tô", "nong_do_con": "0,3 mg/l khí thở",
                   "su_kien": [{"mo_ta": "có nồng độ cồn", "trich_dan": msg}]}}
    pl, _ = _pipeline(tmp_path, reasoner, {"TrichXuatLLM": trich})
    k = pl.xu_ly(PhienLamViec(), msg, ngay_vi_pham=date(2023, 6, 1))
    assert k.suy_luan.phien_ban == "V2" and not k.suy_luan.mac_dinh_phien_ban
    assert k.suy_luan.ma_hanh_vi == {"OT_CON_2"}


def test_pipeline_inducer_loi_van_ket_luan(tmp_path, reasoner):
    """fact_inducer lỗi (vd. Ollama quá thời gian) → vẫn kết luận từ sự kiện trực tiếp và ghi chú rõ."""
    from src.llm.client import LLMError

    class InducerLoi(FactInducer):
        def goi_llm(self, *a, **k):
            raise LLMError("quá thời gian chờ")

    pl, fake = _pipeline(tmp_path, reasoner, {"TrichXuatLLM": TRICH})
    pl._inducer = InducerLoi(client=fake)
    phien = PhienLamViec()
    pl.xu_ly(phien, MSG1)
    k = pl.xu_ly(phien, MSG2)
    assert k.suy_luan.ma_hanh_vi == {"XM_MU_BAO_HIEM"}
    assert any("Không suy ra được sự kiện gián tiếp" in g for g in k.ghi_chu)



def test_xac_nhan_chi_ap_dung_muc_da_hoi():
    """'Có' chỉ áp cho mục được hỏi; mục chờ khác (không được hỏi ở lượt đó) giữ nguyên."""
    from src.extraction.schema import SuKienSuyRa

    hs = HoSoVuViec(su_kien_suy_ra=[
        SuKienSuyRa(thuoc_tinh="boChay", gia_tri=True, do_tin_cay=0.7, bang_chung="chạy luôn", trang_thai="cho_xac_nhan"),
        SuKienSuyRa(thuoc_tinh="khongChapHanhDenTinHieu", gia_tri=True, do_tin_cay=0.7, bang_chung="đèn vàng",
                    trang_thai="cho_xac_nhan")])
    Pipeline._ap_dung_xac_nhan(hs, True, {"su_kien:boChay"})
    tt = {s.thuoc_tinh: s.trang_thai for s in hs.su_kien_suy_ra}
    assert tt == {"boChay": "xac_nhan", "khongChapHanhDenTinHieu": "cho_xac_nhan"}
    assert hs.su_kien == {"boChay": True}


def test_xac_nhan_loai_xe_bi_bac():
    hs = HoSoVuViec(loai_xe="OTo", nguon={"loai_xe": NguonGoc(goc="con xe cũ", phuong_phap="embedding")})
    Pipeline._ap_dung_xac_nhan(hs, False, {"loai_xe"})
    assert hs.loai_xe is None and "loai_xe" not in hs.nguon


def test_xep_loai_xe_khi_dung_tich_den_o_luot_sau(tmp_path, reasoner):
    """Lượt 1 nói "xe máy", lượt 3 mới nói dung tích → hồ sơ gộp phải được xếp loại lại (xe mô tô hai bánh)."""
    m1 = "Hôm 3/11/2026 tôi đi xe máy, chưa có giấy phép lái xe"
    m2 = "xe 110 phân khối"
    trich = {m1: {"thoi_diem": "3/11/2026", "loai_xe": "xe máy",
                  "su_kien": [{"mo_ta": "chưa có giấy phép lái xe", "trich_dan": "chưa có giấy phép lái xe"}]},
             m2: {"dung_tich_xi_lanh": "110 phân khối"}}
    pl, _ = _pipeline(tmp_path, reasoner, {"TrichXuatLLM": trich})
    ph = PhienLamViec()
    k1 = pl.xu_ly(ph, m1)
    assert k1.trang_thai == "can_hoi" and "dung_tich" in [q.truong for q in k1.cau_hoi]
    k2 = pl.xu_ly(ph, m2)
    assert k2.ho_so.loai_xe == "XeMoToHaiBanh" and k2.ho_so.nguon["loai_xe"].phuong_phap == "suy_ra"
    assert any("GPLX" in d.ten for d in k2.quyet_dinh.hanh_vi)
