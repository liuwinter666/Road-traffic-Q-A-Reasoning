"""Test Phase 8: nhãn sinh tự động, metric, người dùng mô phỏng, baseline, thành phần ablation (không gọi LLM)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from evaluation.baseline_llm_only import HanhViBaseline, id_dieu_khoan
from evaluation.metrics import phan_loai_loi, tinh
from evaluation.run_eval import KICH_BAN, doc_kich_ban, tra_loi_mo_phong
from evaluation.thanh_phan_ablation import NormalizerDonGian
from src.extraction.schema import HoSoVuViec, SuKienSuyRa


def test_kich_ban_va_nhan_tra_tu_so_dang_ky():
    from src.kb.rules_builder import load_registry

    ds = doc_kich_ban()
    assert len(ds) >= 50 and len({x["id"] for x in ds}) == len(ds)
    assert {x["nhom"] for x in ds} == {"don_loi", "da_loi", "gian_tiep", "thieu_thong_tin", "khac_thoi_diem",
                                       "khong_vi_pham"}
    hv = load_registry()["hanh_vi"]
    for x in ds:
        n = x["nhan"]
        assert [d["ma"] for d in n["dieu_khoan"]] == n["hanh_vi"]
        for d in n["dieu_khoan"]:
            assert hv[d["ma"]]["phien_ban"][n["phien_ban"]]["can_cu"]["id"] == d["id"]


def _kb(**nhan):
    return {"id": "X1", "nhom": "don_loi", "nhan": {"phien_ban": "V3", "hanh_vi": [], "dieu_khoan": [], "nodes": [],
                                                    "hoi_luot_dau": [], "su_kien": {}, "truong": {}, **nhan}}


def test_metric_dung_het_va_dan_het_hieu_luc():
    kb = _kb(hanh_vi=["OT_DEN_DO"], dieu_khoan=[{"ma": "OT_DEN_DO", "id": "ND168-D6-K9-b", "khung_phat": [1, 2]}],
             truong={"loai_xe": ["OTo"]})
    dung = {"id": "X1", "nhom": "don_loi", "trang_thai": "ket_luan", "phien_ban": "V3",
            "luot": [{"hoi": [], "thoi_gian_s": 2.0}],
            "hanh_vi": [{"ma": "OT_DEN_DO", "id": "ND168-D6-K9-b", "khung_phat": [1, 2]}],
            "ho_so": {"loai_xe": "OTo"}, "nodes": [], "tra_loi": "theo NĐ 168/2024"}
    m = tinh([dung], [kb])
    assert m["dieu_khoan_f1"] == 1 and m["khop_tron_ven"] == 1 and m["khung_phat_acc"] == 1
    assert m["hoi_dung_luc"] == 1 and m["dan_het_hieu_luc"] == 0 and m["truong_f1"]["loai_xe"] == 1
    sai = {**dung, "hanh_vi": [{"id": "ND100-D5-K5-a", "khung_phat": [3, 5]}], "phien_ban": None,
           "can_hoi_luot_dau": True, "tra_loi": "Theo Nghị định 100/2019/NĐ-CP"}
    m2 = tinh([sai], [kb])
    assert m2["dieu_khoan_f1"] == 0 and m2["dan_sai_luat"] == 1 and m2["dan_het_hieu_luc"] == 1
    assert m2["hoi_dung_luc"] == 0 and m2["hoi_thua"] == 1 and m2["tra_loi_nhac_van_ban_het_hieu_luc"] == 1
    assert "hanh_vi_f1" not in m2                     # baseline không có mã hành vi


def test_phan_loai_loi_theo_tang():
    co_ban = {"dung_het": False, "hoi_dung_luc": True, "trang_thai": "ket_luan", "phien_ban": "V3",
              "phien_ban_chuan": "V3", "sai_truong": [], "sai_su_kien": [], "thieu_node": []}
    assert phan_loai_loi({**co_ban, "dung_het": True}) is None
    assert phan_loai_loi({**co_ban, "trang_thai": "can_hoi"}).startswith("hội thoại")
    assert phan_loai_loi({**co_ban, "phien_ban": "V4"}).startswith("thời điểm")
    assert phan_loai_loi({**co_ban, "sai_truong": ["loai_xe: thiếu"]}).startswith("trích xuất")
    assert phan_loai_loi({**co_ban, "sai_su_kien": ["boChay"]}).startswith("ánh xạ")
    assert phan_loai_loi(co_ban).startswith("suy luận")


def test_nguoi_dung_mo_phong():
    kb = {"tra_loi": {"loai_xe": "Tôi đi xe máy."},
          "nhan": {"su_kien": {"boChay": True}, "truong": {"loai_xe": ["NhomXeMoTo"]}, "nodes": []}}
    q = lambda truong, muc=(): SimpleNamespace(truong=truong, muc_xac_nhan=list(muc))
    tin, ngoai = tra_loi_mo_phong(SimpleNamespace(cau_hoi=[q("loai_xe"), q("tuoi_nguoi_lai")], ho_so=HoSoVuViec()), kb)
    assert tin == "Tôi đi xe máy." and ngoai == ["tuoi_nguoi_lai"]
    hs = HoSoVuViec(su_kien_suy_ra=[SuKienSuyRa(thuoc_tinh="boChay", gia_tri=True, do_tin_cay=0.7, bang_chung="x",
                                                trang_thai="cho_xac_nhan")])
    assert tra_loi_mo_phong(SimpleNamespace(cau_hoi=[q("xac_nhan", ["su_kien:boChay"])], ho_so=hs), kb)[0] == "Đúng."
    hs.su_kien_suy_ra[0].gia_tri = False
    assert tra_loi_mo_phong(SimpleNamespace(cau_hoi=[q("xac_nhan", ["su_kien:boChay"])], ho_so=hs), kb)[0] == "Không phải."


@pytest.mark.parametrize("vb,dieu,khoan,diem,id_", [
    ("Nghị định 168/2024/NĐ-CP", 7, 8, "b", "ND168-D7-K8-b"), ("NĐ 100/2019", 5, 5, "đ", "ND100-D5-K5-dd"),
    ("Nghị định số 168/2024/NĐ-CP", 6, 8, None, "ND168-D6-K8"), ("Nghị định 168", 18, 5, "điểm a)", "ND168-D18-K5-a")])
def test_baseline_quy_ve_id(vb, dieu, khoan, diem, id_):
    assert id_dieu_khoan(HanhViBaseline(mo_ta="x", van_ban=vb, dieu=dieu, khoan=khoan, diem=diem)) == id_


def test_normalizer_don_gian_kem_hon_normalizer_that():
    from src.extraction import normalizer as N

    nm = NormalizerDonGian()
    assert nm.toc_do("80 km/h").gia_tri == 80 and nm.toc_do("tám mươi cây") is None
    assert N.toc_do("tám mươi cây").gia_tri == 80
    assert nm.nong_do_con("0,3 miligam một lít khí thở") == (None, None)        # dấu phẩy + đơn vị nói dài
    assert nm.thoi_diem("tối qua") is None and nm.thoi_diem("10/3/2025").tu.isoformat() == "2025-03-10"


def test_file_kich_ban_khop_nguon():
    """scenarios.jsonl phải được sinh lại sau khi sửa scenarios_src.yaml."""
    import yaml

    src = yaml.safe_load(KICH_BAN.with_name("scenarios_src.yaml").read_text(encoding="utf-8"))
    ids = [t["id"] for t in src["tinh_huong"]]
    assert ids == [json.loads(x)["id"] for x in KICH_BAN.read_text(encoding="utf-8").splitlines() if x.strip()]
