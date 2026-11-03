"""Test ontology: cấu trúc, căn cứ pháp lý của ngưỡng, suy luận OWL với Pellet/HermiT."""

from __future__ import annotations

import json

import pytest
import yaml
from owlready2 import OwlReadyInconsistentOntologyError, sync_reasoner_hermit, sync_reasoner_pellet

from src.config import PROCESSED_DIR, ROOT_DIR
from src.kb.java_env import configure_owlready, find_java
from src.kb.loader import load_world

CONCEPTS = yaml.safe_load((ROOT_DIR / "config" / "ontology_concepts.yaml").read_text(encoding="utf-8"))
needs_java = pytest.mark.skipif(find_java() is None, reason="Chưa cài Java")


@pytest.fixture(scope="module")
def onto():
    return load_world()[1]


def articles(v: str) -> dict[str, dict]:
    """Bản ghi theo phiên bản (V1..) hoặc văn bản bổ trợ (LXLVPHC, LTTATGT, TT38)."""
    name = f"articles_{v.lower()}" if v[1:].isdigit() else f"support_{v.lower()}"
    with (PROCESSED_DIR / f"{name}.jsonl").open(encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f)}


# ---------------- cấu trúc ----------------

def test_core_classes_exist(onto):
    for c in ["PhuongTien", "XeMoTo", "XeGanMay", "OTo", "XeOToTai", "NguoiDieuKhien", "VuViec",
              "HanhViViPham", "TinhTietTangNang", "TinhTietGiamNhe", "NghiDinh", "Dieu", "Khoan", "Diem",
              "PhienBanPhapLy", "KhungPhat", "TuocGPLX", "TruDiemGPLX", "TamGiuPhuongTien",
              "KhuDanCu", "NgoaiKhuDanCu", "DuongCaoToc", "QuyTac"]:
        assert onto[c] is not None, c
    for p in ["nongDoConKhiTho", "nongDoConMau", "tocDoThucTe", "tocDoToiDaChoPhep", "thoiDiemViPham",
              "dieuKhien", "viPhamHanhVi", "apDungDieuKhoan", "coKhungPhat", "coTinhTiet", "duocSuyRaBoi"]:
        assert onto[p] is not None, p


def test_behavior_classes_cover_mvp(onto):
    beh = yaml.safe_load((ROOT_DIR / "config" / "mvp_behaviors.yaml").read_text(encoding="utf-8"))["behaviors"]
    for b in beh:
        c = onto[f"HV_{b['code']}"]
        assert c is not None and onto.HanhViViPham in c.ancestors()
        # mọi id căn cứ phải có cá thể điều khoản tương ứng
        for ref in c.canCuPhapLy:
            v, rid = ref.split(":")
            assert onto[f"{v}_{rid}"] is not None, ref


def test_provision_individuals(onto):
    d = onto["V3_ND168-D6-K9-a"]
    assert onto.Diem in d.is_a and d.thuocPhienBan == onto.V3
    assert d.thuocDieuKhoanCha == onto["V3_ND168-D6-K9"]
    kp = onto["V3_ND168-D6-K9"].coKhungPhat[0]
    assert (kp.mucToiThieu, kp.mucToiDa) == (18_000_000, 20_000_000)
    # cùng id nhưng khác phiên bản là hai cá thể khác nhau
    assert onto["V1_ND100-D5-K4"].coKhungPhat[0].mucToiDa != onto["V2_ND100-D5-K4"].coKhungPhat[0].mucToiDa
    assert onto["V2_ND100-D6-K3-n"].duocSuaDoiBoi == [onto.ND123]


def test_threshold_evidence_in_source():
    """Cụm từ căn cứ của mọi ngưỡng phải có nguyên văn trong phần tử được dẫn."""
    cache: dict[str, dict] = {}
    for t in CONCEPTS["thresholds"] + CONCEPTS["thresholds_luat"]:
        for e in t["evidence"]:
            arts = cache.setdefault(e["version"], articles(e["version"]))
            assert e["phrase"] in arts[e["id"]]["full_text"], f"{t['name']}: {e}"


# ---------------- suy luận ----------------

def _case(onto):
    """Tạo một vụ việc mẫu (giá trị đặt ở biên để kiểm tra ranh giới)."""
    with onto:
        v = onto.VuViec("vv_test")
        v.apDungPhienBan = onto.V3
        cao_toc = onto.DuongCaoToc("duong_test")
        xe_dien = onto.XeMayDien("xe_dien")
        xe_150 = onto.XeMoToHaiBanh("xe_150"); xe_150.dungTichXiLanh = 150.0
        n15 = onto.Nguoi("nguoi_15"); n15.tuoi = 15
        n18 = onto.Nguoi("nguoi_18"); n18.tuoi = 18
        acts = {}
        for name, kw in {
            "h_con_025": dict(nongDoConKhiTho=0.25),
            "h_con_03": dict(nongDoConKhiTho=0.3),
            "h_mau_81": dict(nongDoConMau=81.0),
            "h_td_4": dict(tocDoVuot=4.0), "h_td_10": dict(tocDoVuot=10.0),
            "h_td_20": dict(tocDoVuot=20.0), "h_td_35": dict(tocDoVuot=35.0),
            "h_csgt": dict(coHieuLenhNguoiDieuKhienGT=True, chapHanhHieuLenh=False),
            "h_csgt_ok": dict(coHieuLenhNguoiDieuKhienGT=True, chapHanhHieuLenh=True),
            "h_nguoc_ct": dict(diNguocChieu=True),
            "h_gplx": dict(coGPLX=True, mangTheoGPLX=False),
        }.items():
            h = onto.HanhViDieuKhienXe(name)
            for k, val in kw.items():
                setattr(h, k, val)
            h.thuocVuViec = v
            acts[name] = h
        acts["h_nguoc_ct"].trenLoaiDuong = [cao_toc]
        acts["h_con_03"].apDungDieuKhoan = [onto["V3_ND168-D6-K9-a"]]
    return locals()


def _types(ind):
    """Tập tên lớp của cá thể, gồm cả lớp tổ tiên (reasoner chỉ giữ lớp cụ thể nhất trong is_a)."""
    return {c.name for c in ind.INDIRECT_is_a if hasattr(c, "name")}


def _assert_classification(onto, c):
    a = c["acts"]
    assert "NongDoConKhiThoMuc1" in _types(a["h_con_025"])      # 0,25 là "chưa vượt quá 0,25"
    assert {"NongDoConKhiThoMuc2"} <= _types(a["h_con_03"])
    assert "NongDoConMauMuc3" in _types(a["h_mau_81"])
    assert not ({"VuotTocDo05Den10", "VuotTocDo10Den20"} & _types(a["h_td_4"]))  # dưới 5 km/h
    assert "VuotTocDo10Den20" in _types(a["h_td_10"]) and "VuotTocDo10Den20" in _types(a["h_td_20"])
    assert {"VuotTocDoTren20Den35", "VuotTocDoTren20"} <= _types(a["h_td_35"])
    assert "KhongChapHanhHieuLenhNguoiDieuKhienGT" in _types(a["h_csgt"])
    assert "KhongChapHanhHieuLenhNguoiDieuKhienGT" not in _types(a["h_csgt_ok"])
    assert "DiNguocChieuTrenCaoToc" in _types(a["h_nguoc_ct"])
    assert "KhongMangTheoGPLX" in _types(a["h_gplx"])
    assert "NguoiTu14Den16Tuoi" in _types(c["n15"]) and "NguoiTu16Den18Tuoi" not in _types(c["n18"])
    assert "NguoiTu18TuoiTroLen" in _types(c["n18"]) and "NguoiTu18TuoiTroLen" not in _types(c["n15"])
    assert {"DungTichDuoi175cm3", "DungTichTren125cm3"} <= _types(c["xe_150"])


@needs_java
def test_pellet_reasoning():
    configure_owlready()
    world, onto = load_world()
    c = _case(onto)
    with onto:
        sync_reasoner_pellet(world, infer_property_values=True, infer_data_property_values=True, debug=0)
    _assert_classification(onto, c)
    a = c["acts"]
    # lớp hợp "máu hoặc hơi thở" và lớp hợp phân hạng xe NĐ 168
    assert "NongDoConMuc2" in _types(a["h_con_03"]) and "NongDoConMuc3" in _types(a["h_mau_81"])
    assert "XeMoToHangLonND168" in _types(c["xe_150"])
    # cây phân loại: xe máy điện thuộc nhóm xe mô tô, xe gắn máy
    assert onto.NhomXeMoTo in c["xe_dien"].INDIRECT_is_a
    # chuỗi thuộc tính: áp dụng điểm a khoản 9 ⇒ chịu khung phạt của khoản 9
    assert onto["KP_V3_ND168-D6-K9"] in a["h_con_03"].chiuKhungPhat
    assert onto["KP_V3_ND168-D6-K9"] in onto["V3_ND168-D6-K9-a"].coKhungPhat


@needs_java
def test_hermit_reasoning():
    configure_owlready()
    world, onto = load_world()
    c = _case(onto)
    with onto:
        sync_reasoner_hermit(world, infer_property_values=True, debug=0)
    _assert_classification(onto, c)


@needs_java
def test_disjoint_vehicle_inconsistency():
    """Xe đạp điện không thể đồng thời thuộc nhóm xe mô tô (bẫy phân loại)."""
    configure_owlready()
    world, onto = load_world()
    with onto:
        x = onto.XeDapDien("xe_dap_dien")
        x.is_a.append(onto.NhomXeMoTo)
    with pytest.raises(OwlReadyInconsistentOntologyError):
        with onto:
            sync_reasoner_pellet(world, debug=0)



def test_conditional_and_partial_effectivity(onto):
    """Hiệu lực tới cấp phần nội dung và hiệu lực có điều kiện được mô hình trong ontology."""
    d = onto["V4_ND168-D20-K5-l"]
    assert d.hieuLucMotPhan is True
    parts = [p for p in onto.PhanNoiDung.instances() if p.thuocDieuKhoanCha == d]
    assert len(parts) == 1 and parts[0].hieuLucTu.year == 2028 and "dưới 08 chỗ" in parts[0].moTaPhamVi
    n = onto["V4_ND168-D20-K5-n"]
    assert n.hieuLucTu.year == 2029 and "khoang chở khách" in n.hieuLucDieuKien and n.dieuKienDaDapUng is False
    assert onto["V3_ND168-D32-K1-b"].hieuLucChuaXacDinh is True


def test_tinh_tiet_individuals(onto):
    gn, tn = list(onto.TinhTietGiamNhe.instances()), list(onto.TinhTietTangNang.instances())
    assert len(gn) == 8 and len(tn) == 12
    assert onto.TTTN_b.canCuDieuKhoan == [onto["LXLVPHC-D10-K1-b"]] and "tái phạm" in onto.TTTN_b.label[0]
    assert onto["LXLVPHC-D23-K4"].hieuLucTu.year == 2022 and onto["LXLVPHC-D23-K4"].noiDungTruocDo



def test_supporting_versions_in_ontology(onto):
    assert onto.LTTATGT_2026A is not None and onto.L118 is not None and onto.GTDB2008 is not None
    assert onto["LTTATGT_2025_LTTATGT-D59-K1-b"].thuocPhienBan == onto.LTTATGT_2025
    assert onto["GTDB2008-D60-K1-b"] is not None and onto["TT31-D7"] is not None
    parts = [p for p in onto.PhanNoiDung.instances() if p.thuocDieuKhoanCha == onto["LTTATGT_2026B_LTTATGT-D35-K2"]]
    assert sorted(p.hieuLucTu.year for p in parts) == [2028, 2029]
