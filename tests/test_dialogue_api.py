"""Test Phase 7: dialogue manager, API FastAPI, giao diện Streamlit (LLM giả, reasoner thật)."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.dialogue import manager as M
from src.dialogue.manager import DialogueManager, ap_dung_sua
from src.extraction.entity_linker import EntityLinker
from src.extraction.llm_extractor import LLMExtractor
from src.extraction.schema import HoSoVuViec
from src.inference.pipeline import Pipeline
from tests.test_pipeline import MSG1, MSG2, SUY_RA, TRICH, FakeLLM, T


@pytest.fixture(scope="module")
def reasoner():
    from src.kb.reasoner import TrafficReasoner

    return TrafficReasoner()


def _pipeline(tmp_path, reasoner):
    fake = FakeLLM({"TrichXuatLLM": TRICH, "KetQuaSuyRaLLM": SUY_RA}, tmp_path)
    return Pipeline(client=fake, extractor=LLMExtractor(client=fake, linker=EntityLinker(embedder=None)),
                    reasoner=reasoner, hom_nay=T, dung_dien_dat=False, dung_goi_y_lien_quan=False)


@pytest.fixture
def mgr(tmp_path, reasoner):
    return DialogueManager(_pipeline(tmp_path, reasoner))


# ---------------- dialogue manager ----------------

def test_hoi_thoai_nhieu_luot_va_sua_ho_so(mgr):
    pid = mgr.tao_phien()
    k1 = mgr.gui(pid, MSG1)
    assert k1["trang_thai"] == "can_hoi" and k1["cau_hoi"][0]["truong"] == "loai_xe"
    k2 = mgr.gui(pid, MSG2)
    assert k2["trang_thai"] == "ket_luan" and {h["ma"] for h in k2["hanh_vi"]} == {"XM_HIEU_LENH_CSGT", "XM_MU_BAO_HIEM"}
    assert k2["do_thi"]["nodes"] and k2["chuoi_suy_luan"]
    nv = {d["id"]: d for d in k2["dieu_khoan_nguyen_van"]}
    assert nv["ND168-D7-K7-d"]["la_ket_luan"] and "Điều 7" in nv["ND168-D7-K7-d"]["nguyen_van"]
    # sửa bảng sự kiện: thực ra là ô tô, có đội mũ → chạy lại không gọi LLM
    n_goi = len(mgr.pipeline.client.calls)
    k3 = mgr.sua_ho_so(pid, {"loai_xe": "OTo", "su_kien": {"doiMuBaoHiem": None}})
    assert len(mgr.pipeline.client.calls) == n_goi
    assert {h["ma"] for h in k3["hanh_vi"]} == {"OT_HIEU_LENH_CSGT"}
    assert k3["ho_so"]["nguon"]["loai_xe"]["phuong_phap"] == "nguoi_dung_sua"
    # người dùng bác sự kiện LLM suy ra → không còn kết luận hiệu lệnh
    k4 = mgr.sua_ho_so(pid, {"su_kien": {"chapHanhHieuLenh": True}})
    assert k4["trang_thai"] == "khong_phat_hien"
    p = mgr.lay(pid)
    assert [t.vai for t in p.lich_su] == ["nguoi_dung", "he_thong"] * 4
    assert next(s for s in p.lam_viec.ho_so.su_kien_suy_ra if s.thuoc_tinh == "chapHanhHieuLenh").trang_thai == "tu_choi"


def test_ngay_tu_giao_dien_va_vu_viec_moi(mgr):
    pid = mgr.tao_phien()
    mgr.dat_ngay(pid, date(2023, 6, 1))
    mgr.gui(pid, MSG1)
    k = mgr.gui(pid, MSG2)
    assert k["phien_ban"]["ma"] == "V2"
    assert mgr.gui(pid, "/moi")["trang_thai"] == "vu_viec_moi"
    assert mgr.lay(pid).lam_viec.ho_so == HoSoVuViec() and mgr.lay(pid).ket_qua_cuoi is None


@pytest.mark.parametrize("thay_doi,loi", [({"loai_xe": "TauHoa"}, "loai_xe"), ({"tuoi_nguoi_lai": -3}, "không âm"),
                                          ({"su_kien": {"bayLuon": True}}, "danh mục"), ({"ho_ten": "A"}, "Không sửa")])
def test_ap_dung_sua_kiem_tra(thay_doi, loi):
    with pytest.raises(ValueError, match=loi):
        ap_dung_sua(HoSoVuViec(), thay_doi, T)


def test_ap_dung_sua_xep_loai_xe_may():
    hs = HoSoVuViec()
    ap_dung_sua(hs, {"loai_xe": "NhomXeMoTo", "dung_tich_xi_lanh": 45, "ngay_vi_pham": "2025-03-10"}, T)
    assert hs.loai_xe == "XeGanMay" and hs.ngay_vi_pham == date(2025, 3, 10)


def test_phien_het_han(mgr):
    pid = mgr.tao_phien()
    mgr.ttl_s = -1
    mgr.don_dep()
    with pytest.raises(M.PhienKhongTonTai):
        mgr.lay(pid)


# ---------------- API ----------------

@pytest.fixture
def client(mgr):
    from src.api.main import app, get_manager

    app.dependency_overrides[get_manager] = lambda: mgr
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_luong_day_du(client):
    assert client.get("/suc-khoe").json()["ok"]
    dm = client.get("/danh-muc").json()
    assert {"loai_xe", "loai_duong", "su_kien"} <= set(dm) and any(x["ma"] == "OTo" for x in dm["loai_xe"])
    pid = client.post("/phien").json()["phien_id"]
    r1 = client.post(f"/phien/{pid}/tin-nhan", json={"tin_nhan": MSG1})
    assert r1.status_code == 200 and r1.json()["trang_thai"] == "can_hoi"
    r2 = client.post(f"/phien/{pid}/tin-nhan", json={"tin_nhan": MSG2})
    assert r2.json()["trang_thai"] == "ket_luan" and r2.json()["tong_tien_de_xuat"] > 0
    r3 = client.patch(f"/phien/{pid}/ho-so", json={"thay_doi": {"su_kien": {"doiMuBaoHiem": True}}})
    assert {h["ma"] for h in r3.json()["hanh_vi"]} == {"XM_HIEU_LENH_CSGT"}
    ph = client.get(f"/phien/{pid}").json()
    assert len(ph["lich_su"]) == 6 and ph["ket_qua_cuoi"]["trang_thai"] == "ket_luan"
    assert client.put(f"/phien/{pid}/ngay", json={"ngay_vi_pham": "2024-05-01"}).status_code == 200
    assert client.post(f"/phien/{pid}/moi").json()["ok"]
    assert client.delete(f"/phien/{pid}").json()["ok"]
    assert client.get(f"/phien/{pid}").status_code == 404


def test_api_loi(client):
    assert client.post("/phien/khong-co/tin-nhan", json={"tin_nhan": "x"}).status_code == 404
    pid = client.post("/phien").json()["phien_id"]
    assert client.post(f"/phien/{pid}/tin-nhan", json={"tin_nhan": ""}).status_code == 422
    assert client.patch(f"/phien/{pid}/ho-so", json={"thay_doi": {"loai_xe": "TauHoa"}}).status_code == 422


def test_api_dieu_khoan(client):
    r = client.get("/dieu-khoan/ND168-D7-K8-b", params={"phien_ban": "V4"}).json()
    assert r["trich_dan"] == "điểm b khoản 8 Điều 7 NĐ 168/2024/NĐ-CP" and "0,25 miligam" in r["nguyen_van"]
    assert client.get("/dieu-khoan/ND168-D99-K1").status_code == 404


# ---------------- giao diện Streamlit (AppTest, chạy trực tiếp trong tiến trình) ----------------

def test_streamlit_giao_dien(tmp_path, reasoner, monkeypatch):
    from streamlit.testing.v1 import AppTest

    from src.config import ROOT_DIR

    monkeypatch.setenv("APP_BACKEND", "truc_tiep")
    monkeypatch.setattr(M, "Pipeline", lambda: _pipeline(tmp_path, reasoner))
    import streamlit as st

    st.cache_resource.clear()
    at = AppTest.from_file(str(ROOT_DIR / "app" / "streamlit_app.py"), default_timeout=300)
    at.run()
    assert not at.exception and at.title[0].value == "Tư vấn vi phạm giao thông đường bộ"
    at.chat_input[0].set_value(MSG1).run()
    assert not at.exception
    assert any("loại xe" in m.markdown[0].value for m in at.chat_message if m.name == "assistant")
    at.chat_input[0].set_value(MSG2).run()
    assert not at.exception and len(at.tabs) == 4
    assert at.session_state.ket_qua["trang_thai"] == "ket_luan"
    assert at.get("graphviz_chart"), "tab cây suy luận phải có đồ thị"
    # sửa loại xe trên bảng sự kiện → chạy lại
    xe = next(s for s in at.selectbox if s.label == "Loại xe")
    xe.set_value("OTo")
    next(b for b in at.button if "Chạy lại" in b.label).click().run()
    assert not at.exception
    assert {h["ma"] for h in at.session_state.ket_qua["hanh_vi"]} == {"OT_HIEU_LENH_CSGT"}
