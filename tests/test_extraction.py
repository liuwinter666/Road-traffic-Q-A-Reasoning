"""Test entity linker, xây dựng hồ sơ, slot checker, gộp nhiều lượt và LLM extractor (LLM giả)."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pytest
import yaml

from src.config import PROCESSED_DIR, ROOT_DIR
from src.extraction.entity_linker import EntityLinker
from src.extraction.llm_extractor import LLMExtractor, xay_dung_ho_so
from src.extraction.schema import HoSoVuViec, SuKienTho, TrichXuatLLM
from src.extraction.slot_checker import kiem_tra
from src.llm.client import DiskCache, LLMClient

T = date(2026, 11, 4)
K = ["dau_hieu", "tinh_tiet", "goi_y"]


@pytest.fixture(scope="module")
def linker():
    return EntityLinker(embedder=None)


# ---------------- entity linker ----------------

@pytest.mark.parametrize("m,nodes", [
    ("tôi uống 3 lon bia rồi vượt đèn đỏ", {"_CO_CON", "KhongChapHanhDenTinHieu"}),
    ("vuot den do", {"KhongChapHanhDenTinHieu"}),                              # không dấu
    ("chạy grab, không đội mũ, nghe điện thoại", {"XeKinhDoanhVanTai", "KhongDoiMuBaoHiem", "DungTaySuDungDienThoai"}),
    ("gây tai nạn rồi bỏ chạy", {"GayTaiNanBoTron", "CoGayTaiNan", "_BO_CHAY"}),
    ("thấy CSGT vẫy thì rồ ga chạy", {"_CSGT", "_BO_CHAY"}),
    ("con tôi 15 tuổi đi xe máy", {"_NGUOI_TRE"}),
    ("tôi đi làm", set()),                                                      # "tôi" không phải "con tôi"
])
def test_link_signs(linker, m, nodes):
    assert {x.node for x in linker.link(m, K)} == nodes


def test_link_facts_from_ontology_concepts(linker):
    lk = linker.link_one("không đội mũ bảo hiểm", "dau_hieu")
    assert lk.su_kien == {"doiMuBaoHiem": False}
    lk = linker.link_one("thành thật hối lỗi", "tinh_tiet")
    assert lk.su_kien == {"thanhThatHoiLoi": True}


@pytest.mark.parametrize("m,node", [("đi chiếc SH", "XeMoToHaiBanh"), ("xe máy", "NhomXeMoTo"),
                                    ("xe máy điện", "XeMayDien"), ("xe đạp điện", "XeDapDien"),
                                    ("ô tô con", "OTo"), ("xe tải", "XeOToTai")])
def test_link_vehicle(linker, m, node):
    assert linker.link_one(m, "xe").node == node


def test_synonym_nodes_exist_in_ontology():
    from src.kb.loader import load_world

    _, onto = load_world()
    data = json.loads((PROCESSED_DIR / "synonyms.json").read_text(encoding="utf-8"))
    for kieu in ("xe", "duong", "dau_hieu"):
        for node in data[kieu]:
            assert onto[node] is not None, node


class FakeEmbedder:
    """Embedding giả: vectơ theo chữ cái đầu của mỗi từ (đủ để kiểm tra luồng dự phòng và ngưỡng)."""

    def encode(self, texts):
        out = []
        for t in texts:
            v = np.zeros(32)
            for w in t.split():
                v[ord(w[0]) % 32] += 1
            out.append(v / (np.linalg.norm(v) or 1))
        return np.array(out)


def test_embedding_fallback_and_threshold():
    lk = EntityLinker(embedder=FakeEmbedder(), threshold=0.5)
    r = lk.link("vượt đỏ đèn", "dau_hieu")                     # không khớp từ điển, gần nghĩa theo embedding
    assert r and r[0].phuong_phap == "embedding"
    # cụm không liên quan: độ tương đồng thấp hơn ngưỡng → không liên kết (để slot checker/người dùng xử lý)
    assert EntityLinker(embedder=FakeEmbedder(), threshold=0.9).link("ăn phở", "dau_hieu") == []


# ---------------- xây dựng hồ sơ ----------------

def test_build_profile(linker):
    tx = TrichXuatLLM(thoi_diem="tối qua", loai_xe="xe máy", dung_tich_xi_lanh="110 phân khối",
                      nong_do_con="0,3mg/l", toc_do_thuc_te="80 cây", toc_do_toi_da="biển 60",
                      loai_duong=["trong khu dân cư", "đường hai chiều"],
                      su_kien=[SuKienTho(mo_ta="vượt đèn đỏ", trich_dan="tôi vượt đèn đỏ"),
                               SuKienTho(mo_ta="đội mũ bảo hiểm", trich_dan="tôi có đội mũ", phu_dinh=True)])
    hs = xay_dung_ho_so(tx, linker, T)
    assert hs.ngay_vi_pham == date(2026, 11, 3) and hs.loai_xe == "XeMoToHaiBanh"
    assert (hs.nong_do_con_khi_tho, hs.toc_do_thuc_te, hs.toc_do_toi_da) == (0.3, 80, 60)
    assert hs.khu_dong_dan_cu is True and hs.duong_doi is False and hs.loai_duong == ["KhuDanCu"]
    assert hs.su_kien == {"khongChapHanhDenTinHieu": True}
    assert hs.nguon["loai_xe"].phuong_phap == "suy_ra" and any("LTTATGT-D34-K1-g" in g for g in hs.gia_dinh)


def test_profile_50cc_depends_on_date(linker):
    tx = TrichXuatLLM(loai_xe="xe máy", dung_tich_xi_lanh="50 phân")
    assert xay_dung_ho_so(tx.model_copy(update={"thoi_diem": "10/3/2024"}), linker, T).loai_xe == "XeMoToHaiBanh"
    assert xay_dung_ho_so(tx.model_copy(update={"thoi_diem": "10/3/2025"}), linker, T).loai_xe == "XeGanMay"


def test_classification_quotes_exist():
    cfg = yaml.safe_load((ROOT_DIR / "config" / "phan_loai_xe.yaml").read_text(encoding="utf-8"))
    for vb, rules in cfg["theo_van_ban"].items():
        for r in rules.values():
            src = r.get("nguon", vb)
            name = f"articles_{src.lower()}" if src[1:].isdigit() else f"support_{src.lower()}"
            recs = {x["id"]: x for x in map(json.loads, (PROCESSED_DIR / f"{name}.jsonl").open(encoding="utf-8"))}
            assert r["trich"] in recs[r["id"]]["text"], r["id"]


def test_multi_turn_merge(linker):
    hs1 = xay_dung_ho_so(TrichXuatLLM(loai_xe="xe máy", su_kien=[SuKienTho(mo_ta="uống bia", trich_dan="")]), linker, T)
    hs2 = xay_dung_ho_so(TrichXuatLLM(nong_do_con="0,45 mg/l khí thở"), linker, T)
    hs = hs1.cap_nhat(hs2)
    assert hs.loai_xe == "NhomXeMoTo" and hs.nong_do_con_khi_tho == 0.45 and "_CO_CON" in hs.goi_y()


# ---------------- slot checker ----------------

def _q(hs, today=T):
    return [q.truong for q in kiem_tra(hs, today).cau_hoi]


def test_slot_nothing_described():
    assert _q(HoSoVuViec()) == ["mo_ta_hanh_vi"]


def test_slot_alcohol_needs_measurement_and_vehicle(linker):
    hs = xay_dung_ho_so(TrichXuatLLM(su_kien=[SuKienTho(mo_ta="uống 2 lon bia", trich_dan="")]), linker, T)
    assert _q(hs) == ["loai_xe", "nong_do_con"]


def test_slot_speed_limit_inferable_or_not(linker):
    base = dict(loai_xe="ô tô", toc_do_thuc_te="80 cây", thoi_diem="10/3/2025")
    hs = xay_dung_ho_so(TrichXuatLLM(**base), linker, T)
    assert _q(hs) == ["dac_diem_duong"]
    hs = xay_dung_ho_so(TrichXuatLLM(**base, loai_duong=["ngoài khu dân cư", "đường đôi"]), linker, T)
    assert kiem_tra(hs, T).du_thong_tin                           # tra được bảng TT 38
    hs = xay_dung_ho_so(TrichXuatLLM(**base, loai_duong=["cao tốc"]), linker, T)
    assert _q(hs) == ["toc_do_toi_da"]                            # cao tốc: hỏi biển báo
    hs = xay_dung_ho_so(TrichXuatLLM(loai_xe="xe 50 phân", toc_do_thuc_te="55", thoi_diem="10/3/2025"), linker, T)
    assert kiem_tra(hs, T).du_thong_tin                           # xe gắn máy: 40 km/h mọi đường


def test_slot_documents_kdvt_only_v3_v4(linker):
    tx = TrichXuatLLM(loai_xe="xe máy", su_kien=[SuKienTho(mo_ta="quên bằng lái", trich_dan="")])
    assert _q(xay_dung_ho_so(tx.model_copy(update={"thoi_diem": "10/3/2025"}), linker, T)) == ["kinh_doanh_van_tai"]
    assert _q(xay_dung_ho_so(tx.model_copy(update={"thoi_diem": "10/3/2023"}), linker, T)) == []


def test_slot_no_license_needs_engine_size(linker):
    hs = xay_dung_ho_so(TrichXuatLLM(loai_xe="xe máy", thoi_diem="10/3/2025",
                                     su_kien=[SuKienTho(mo_ta="không có bằng lái", trich_dan="")]), linker, T)
    assert _q(hs) == ["dung_tich"]


def test_slot_date_spanning_versions(linker):
    hs = xay_dung_ho_so(TrichXuatLLM(thoi_diem="tháng 8 năm 2026", loai_xe="ô tô",
                                     su_kien=[SuKienTho(mo_ta="vượt đèn đỏ", trich_dan="")]), linker, T)
    assert _q(hs) == ["ngay_chinh_xac"]                           # V3 đến 14/8, V4 từ 15/8
    hs = xay_dung_ho_so(TrichXuatLLM(thoi_diem="tháng 3 năm 2026", loai_xe="ô tô",
                                     su_kien=[SuKienTho(mo_ta="vượt đèn đỏ", trich_dan="")]), linker, T)
    assert _q(hs) == []


def test_slot_accident_and_minor(linker):
    hs = xay_dung_ho_so(TrichXuatLLM(loai_xe="xe máy", su_kien=[SuKienTho(mo_ta="va chạm với xe khác", trich_dan=""),
                                                                SuKienTho(mo_ta="con tôi chở", trich_dan="")]),
                        linker, T)
    assert _q(hs) == ["tuoi_nguoi_lai", "tai_nan"]


def test_slot_max_questions(linker):
    hs = xay_dung_ho_so(TrichXuatLLM(su_kien=[SuKienTho(mo_ta="uống bia, chạy nhanh, va chạm, quên giấy tờ",
                                                        trich_dan="")]), linker, T)
    assert len(kiem_tra(hs, T).cau_hoi) == 3 and not kiem_tra(hs, T).du_thong_tin


# ---------------- LLM extractor (LLM giả) ----------------

class FakeLLM(LLMClient):
    provider = "fake"

    def __init__(self, response: dict, tmp_path):
        super().__init__("fake", cache=DiskCache(tmp_path, enabled=False), max_rpm=0)
        self.response = response
        self.prompts = []

    def _call(self, prompt, system, json_schema, schema_model):
        self.prompts.append((system, prompt, json_schema))
        return json.dumps(self.response, ensure_ascii=False)


def test_llm_extractor_with_mock(tmp_path, linker):
    resp = {"thoi_diem": "tối qua", "loai_xe": "xe SH", "nong_do_con": "0,3 mg/l",
            "su_kien": [{"mo_ta": "uống 3 lon bia", "trich_dan": "tối qua tôi uống 3 lon bia"},
                        {"mo_ta": "thấy CSGT vẫy thì rồ ga chạy", "trich_dan": "thấy CSGT vẫy thì rồ ga chạy"}]}
    fake = FakeLLM(resp, tmp_path)
    ex = LLMExtractor(client=fake, linker=linker)
    hs = ex.ho_so("Tối qua tôi uống 3 lon bia, đi chiếc SH, thấy CSGT vẫy thì rồ ga chạy. Đo được 0,3", hom_nay=T,
                  cau_hoi_truoc=["Bạn điều khiển loại xe gì?"])
    system, prompt, schema = fake.prompts[0]
    assert "KHÔNG kết luận vi phạm" in system and "04/11/2026" in prompt and "loại xe gì" in prompt
    assert schema["title"] == "TrichXuatLLM"
    assert hs.loai_xe == "XeMoToHaiBanh" and hs.nong_do_con_khi_tho == 0.3
    assert {"_CO_CON", "_CSGT", "_BO_CHAY"} <= hs.goi_y()
    assert kiem_tra(hs, T).du_thong_tin


def test_prompt_loader():
    from src.llm.prompts import load_prompt

    p = load_prompt("extraction")
    assert p.ma == "extraction@v1" and "{tin_nhan}" in p.user and p.system
