"""Test Phase 6: retriever (tra nguyên văn, tìm ngữ nghĩa), tracer, kiểm tra chống bịa, verbalizer."""

from __future__ import annotations

import hashlib
import re
from datetime import date

import numpy as np
import pytest

from src.explanation.retriever import Retriever, lay
from src.explanation.tracer import dung_trace, id_tinh_tiet, sach
from src.explanation.verbalizer import Verbalizer, kiem_tra, tham_chieu, trace_cho_llm
from src.inference.pipeline import PhienLamViec
from tests.test_pipeline import MSG1, MSG2, SUY_RA, TRICH, FakeLLM, _pipeline


# ---------------- retriever ----------------

def test_lay_theo_phien_ban_va_ngay():
    b = lay("ND168-D7-K8-b", "V4")
    assert b.trich_dan == "điểm b khoản 8 Điều 7 NĐ 168/2024/NĐ-CP" and "0,25 miligam" in b.text
    assert lay("ND100-D5-K8-c", "V2").nguon == "articles_v2"
    assert lay("LTTATGT-D2-K10", None, date(2026, 11, 3)).nguon == "support_lttatgt_2026b"
    assert lay("TT38-D6-K1").trich_dan.startswith("khoản 1 Điều 6 TT 38/2024")
    assert lay("ND168-D999-K1", "V4") is None


class TuVungEmbedder:
    """Embedding giả theo từ (băm) — đủ để test cơ chế chỉ mục/tìm kiếm mà không tải model."""

    model_name = "fake-bow"

    def encode(self, texts):
        out = np.zeros((len(texts), 256), dtype="float32")
        for i, t in enumerate(texts):
            for w in re.findall(r"\w+", t.lower()):
                out[i, int(hashlib.md5(w.encode()).hexdigest(), 16) % 256] += 1
        return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)


def test_tim_ngu_nghia_co_cache(tmp_path):
    r = Retriever(embedder=TuVungEmbedder(), thu_muc=tmp_path)
    kq = r.tim("dừng xe đỗ xe trên vỉa hè", "V4", k=3, nguong=0.0)
    assert kq and any("vỉa hè" in b.text for b, _ in kq)
    assert all(b.nguon == "articles_v4" for b, _ in kq)
    assert list(tmp_path.glob("emb_*.npz"))                     # vector được cache theo nội dung
    r2 = Retriever(embedder=TuVungEmbedder(), thu_muc=tmp_path)
    assert [b.id for b, _ in r2.tim("dừng xe đỗ xe trên vỉa hè", "V4", k=3, nguong=0.0)] == [b.id for b, _ in kq]


# ---------------- tracer ----------------

@pytest.fixture(scope="module")
def reasoner():
    from src.kb.reasoner import TrafficReasoner

    return TrafficReasoner()


@pytest.fixture(scope="module")
def ca_csgt(tmp_path_factory, reasoner):
    pl, _ = _pipeline(tmp_path_factory.mktemp("a"), reasoner, {"TrichXuatLLM": TRICH, "KetQuaSuyRaLLM": SUY_RA})
    ph = PhienLamViec()
    pl.xu_ly(ph, MSG1)
    return pl.xu_ly(ph, MSG2)


MSG_TD = "Ngày 10/3/2025 con tôi 17 tuổi chạy xe máy 110 phân khối 75 cây ngoài khu dân cư đường đôi"


@pytest.fixture(scope="module")
def ca_toc_do(tmp_path_factory, reasoner):
    trich = {MSG_TD: {"thoi_diem": "10/3/2025", "loai_xe": "xe máy", "dung_tich_xi_lanh": "110 phân khối",
                      "tuoi_nguoi_lai": "17 tuổi", "toc_do_thuc_te": "75 cây",
                      "loai_duong": ["ngoài khu dân cư", "đường đôi"]}}
    pl, _ = _pipeline(tmp_path_factory.mktemp("b"), reasoner, {"TrichXuatLLM": trich})
    return pl.xu_ly(PhienLamViec(), MSG_TD)


def test_trace_gian_tiep(ca_csgt):
    tr = ca_csgt.trace
    assert tr is not None and {k.ma_hanh_vi for k in tr.ket_luan} == {"XM_HIEU_LENH_CSGT", "XM_MU_BAO_HIEM"}
    dong = "\n".join(tr.dong_suy_luan())
    assert "R124" in dong and "R140" in dong and "điểm d khoản 7 Điều 7" in dong
    hl = next(k for k in tr.ket_luan if k.ma_hanh_vi == "XM_HIEU_LENH_CSGT")
    la = [n for q in hl.quy_tac for d in q.dieu_kien for n in d.con if n.loai == "su_kien"]
    suy = {n.ten: n for n in la}
    assert suy["chapHanhHieuLenh"].nguon == "suy_ra" and suy["chapHanhHieuLenh"].bang_chung == "rồ ga chạy luôn"
    assert any(c.id == "LTTATGT-D2-K10" for c in suy["coHieuLenhNguoiDieuKhienGT"].can_cu)
    ids = tr.can_cu_hop_le()
    assert {"ND168-D7-K7-d", "ND168-D7-K2-h", "ND168-D7-K13-b", "LTTATGT-D2-K10", "LXLVPHC-D23-K4"} <= set(ids)
    assert tr.ma_quy_tac() == {"R124", "R140"}
    assert {5_000_000, 500_000, 5_500_000} <= tr.so_tien_hop_le()
    g = tr.do_thi()
    assert {"from": "hanh_vi:XM_HIEU_LENH_CSGT", "to": "dieu_khoan:ND168-D7-K7-d", "label": "áp dụng"} in g["edges"]


def test_trace_nguong_toc_do_va_do_tuoi(ca_toc_do):
    tr = ca_toc_do.trace
    td = next(k for k in tr.ket_luan if k.ma_hanh_vi.startswith("XM_TD"))
    nguong = next(d for q in td.quy_tac for d in q.dieu_kien if d.loai == "nguong")
    assert nguong.can_cu[0].id == td.dieu_khoan.id                # bằng chứng ngưỡng = chính điều khoản kết luận
    vuot = nguong.con[0]
    assert vuot.ten == "tocDoVuot" and vuot.gia_tri == 5 and vuot.nguon == "tinh_toan"
    toi_da = next(n for n in vuot.con if n.ten == "tocDoToiDaChoPhep")
    assert toi_da.nguon == "tra_bang" and toi_da.can_cu[0].id == "TT38-D6-K2"
    assert tr.nguoi_khong_du_dieu_kien and "TT38-D6-K2" in tr.can_cu_hop_le()


def test_nhan_sach_va_id_tinh_tiet():
    assert sach("Nhóm xe mô tô, xe gắn máy (đối tượng Điều 6 NĐ 100 / Điều 7 NĐ 168)") == "Nhóm xe mô tô, xe gắn máy"
    assert sach("Nồng độ cồn mức 2 (máu hoặc hơi thở)") == "Nồng độ cồn mức 2 (máu hoặc hơi thở)"
    assert id_tinh_tiet("TTTN_b") == "LXLVPHC-D10-K1-b" and id_tinh_tiet("TTGN_2") == "LXLVPHC-D9-K2"
    assert lay(id_tinh_tiet("TTTN_b")) is not None


# ---------------- kiểm tra chống bịa ----------------

TOT = """**Hành vi vi phạm**
- Không chấp hành hiệu lệnh của người điều khiển giao thông — căn cứ điểm d khoản 7 Điều 7 NĐ 168/2024/NĐ-CP;
  mức đề xuất 5.000.000 đồng (khung từ 4.000.000 đồng đến 6.000.000 đồng), trừ 4 điểm giấy phép lái xe.
- Không đội mũ bảo hiểm — điểm h khoản 2 Điều 7 Nghị định 168/2024/NĐ-CP; mức đề xuất 500.000 đồng.
Tổng 5,5 triệu đồng. Mức trung bình của khung theo khoản 4 Điều 23 Luật Xử lý vi phạm hành chính.
CSGT là người điều khiển giao thông (khoản 10 Điều 2 Luật Trật tự, an toàn giao thông đường bộ).
Kết quả chỉ mang tính tham khảo, không thay thế quyết định của người có thẩm quyền."""


def test_tham_chieu_regex():
    t = tham_chieu("theo điểm đ khoản 5 Điều 6 NĐ 168/2024/NĐ-CP và khoản 4 Điều 23 Luật Xử lý vi phạm hành chính")
    assert [(x["diem"], x["khoan"], x["dieu"], x["van_ban"]) for x in t] == \
        [("dd", "5", "6", "ND168"), (None, "4", "23", "LXLVPHC")]


def test_kiem_tra_hop_le(ca_csgt):
    kt = kiem_tra(TOT, ca_csgt.trace)
    assert kt.hop_le, kt.loi


@pytest.mark.parametrize("sua,thong_bao", [
    (("điểm d khoản 7 Điều 7", "điểm a khoản 7 Điều 7"), "Tham chiếu không có trong trace"),
    (("NĐ 168/2024/NĐ-CP;", "NĐ 100/2019/NĐ-CP;"), "Văn bản không thuộc"),          # dẫn văn bản hết hiệu lực
    (("5.000.000 đồng (khung", "6.500.000 đồng (khung"), "Số tiền không có trong trace"),
    (("trừ 4 điểm", "trừ 6 điểm"), "Số điểm trừ"),
    (("Tổng 5,5 triệu đồng.", "Tổng 5,5 triệu đồng (quy tắc R124)."), "mã quy tắc nội bộ"),
    (("Tổng 5,5 triệu đồng.", "Tổng 5,5 triệu đồng (ND168-D7-K7-d)."), "mã điều khoản nội bộ"),
    (("Kết quả chỉ mang tính tham khảo, ", ""), "tham khảo"),
    (("- Không đội mũ bảo hiểm — điểm h khoản 2 Điều 7 Nghị định 168/2024/NĐ-CP; mức đề xuất 500.000 đồng.", ""),
     "Thiếu căn cứ"),
    (("Tổng 5,5 triệu đồng.", "Bị tước giấy phép lái xe từ 1 tháng đến 3 tháng."), "Thời hạn"),
])
def test_kiem_tra_phat_hien_bia(ca_csgt, sua, thong_bao):
    kt = kiem_tra(TOT.replace(*sua), ca_csgt.trace)
    assert not kt.hop_le and any(thong_bao in x for x in kt.loi), kt.loi


def test_trace_cho_llm_dinh_dang(ca_csgt):
    d = trace_cho_llm(ca_csgt.trace)
    hv = {x["can_cu"]: x for x in d["hanh_vi_vi_pham"]}
    x = hv["điểm d khoản 7 Điều 7 NĐ 168/2024/NĐ-CP"]
    assert x["muc_de_xuat"] == "5.000.000 đồng" and x["khung_phat"] == "từ 4.000.000 đồng đến 6.000.000 đồng"
    assert any("Trừ điểm giấy phép lái xe 4 điểm" in c for c in x["hinh_thuc_bo_sung"])
    assert d["tong_tien_de_xuat"] == "5.500.000 đồng" and "NĐ 100" not in str(d)


# ---------------- verbalizer ----------------

def test_verbalizer_thu_lai_roi_hop_le(tmp_path, ca_csgt):
    sai = TOT.replace("điểm d khoản 7 Điều 7", "điểm a khoản 7 Điều 7")
    fake = FakeLLM({"text": [sai, TOT]}, tmp_path)
    kq = Verbalizer(client=fake).dien_dat(ca_csgt.trace, "DỰ PHÒNG")
    assert kq.nguon == "llm" and kq.so_lan_goi == 2 and kq.van_ban == TOT.strip()


def test_verbalizer_du_phong_khi_van_sai(tmp_path, ca_csgt):
    sai = TOT.replace("trừ 4 điểm", "trừ 12 điểm")
    kq = Verbalizer(client=FakeLLM({"text": [sai, sai]}, tmp_path)).dien_dat(ca_csgt.trace, "DỰ PHÒNG")
    assert kq.nguon == "tat_dinh" and kq.van_ban == "DỰ PHÒNG" and kq.so_lan_goi == 2
    assert any("Số điểm trừ" in x for x in kq.kiem_tra.loi)


def test_verbalizer_du_phong_khi_llm_loi(tmp_path, ca_csgt):
    from src.llm.client import LLMError

    class Loi(FakeLLM):
        def _call(self, *a, **k):
            raise LLMError("hết hạn mức")
    kq = Verbalizer(client=Loi({}, tmp_path)).dien_dat(ca_csgt.trace, "DỰ PHÒNG")
    assert kq.nguon == "tat_dinh" and "lỗi LLM" in kq.ly_do_du_phong


def test_pipeline_dien_dat_va_goi_y(tmp_path, reasoner, monkeypatch):
    """Pipeline đủ tầng: verbalizer (LLM giả) + gợi ý RAG khi không phát hiện vi phạm."""
    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "rag_nguong", 0.0)       # ngưỡng 0.55 dành cho bge-m3, embedder giả thấp hơn
    msg = "Hôm qua tôi đỗ xe ô tô trên vỉa hè"
    trich = {msg: {"thoi_diem": "Hôm qua", "loai_xe": "ô tô",
                   "su_kien": [{"mo_ta": "đỗ xe ô tô trên vỉa hè", "trich_dan": msg}]}}
    tra_loi = "Hệ thống không phát hiện hành vi vi phạm trong phạm vi đã mô hình hóa. Kết quả chỉ mang tính tham khảo."
    pl, _ = _pipeline(tmp_path, reasoner, {"TrichXuatLLM": trich, "text": [tra_loi]}, dung_dien_dat=True,
                      dung_goi_y_lien_quan=True, retriever=Retriever(embedder=TuVungEmbedder(), thu_muc=tmp_path))
    k = pl.xu_ly(PhienLamViec(), msg)
    assert k.trang_thai == "khong_phat_hien" and k.dien_dat.nguon == "llm"
    assert k.tra_loi.startswith(tra_loi) and "CHƯA mô hình hóa" in k.tra_loi
    assert k.lien_quan and any("vỉa hè" in b.text for b, _ in k.lien_quan)


def test_ly_do_tinh_tiet_kem_nguon(tmp_path, reasoner):
    msg = "Ngày 3/11/2026 tôi lái ô tô vượt đèn đỏ, sau đó tôi thành thật khai báo với cán bộ"
    trich = {msg: {"thoi_diem": "3/11/2026", "loai_xe": "ô tô",
                   "su_kien": [{"mo_ta": "vượt đèn đỏ", "trich_dan": "vượt đèn đỏ"}]}}
    suy = {msg: {"su_kien": [{"thuoc_tinh": "thanhThatHoiLoi", "gia_tri": True, "do_tin_cay": 0.9,
                              "bang_chung": "tôi thành thật khai báo với cán bộ", "giai_thich": ""}]}}
    pl, _ = _pipeline(tmp_path, reasoner, {"TrichXuatLLM": trich, "KetQuaSuyRaLLM": suy})
    k = pl.xu_ly(PhienLamViec(), msg)
    ly_do = k.trace.ket_luan[0].ly_do
    dong = next(x for x in ly_do if x.startswith("Tình tiết giảm nhẹ:"))
    assert "hệ thống suy ra từ lời kể: “tôi thành thật khai báo với cán bộ”" in dong
    d = trace_cho_llm(k.trace)["hanh_vi_vi_pham"][0]
    assert "suy ra từ lời kể" in d["tinh_tiet_giam_nhe"][0] and "TTGN" not in str(d)
