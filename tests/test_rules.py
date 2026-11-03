"""Test luật SWRL: sổ đăng ký đầy đủ, luật phân tích được, mỗi luật cho đúng điều khoản trên tình huống mẫu,
các bẫy (không vi phạm, khác thời điểm, loại trừ) và suy luận hai bước (chủ xe giao xe)."""

from __future__ import annotations

import re
from datetime import date

import pytest
import yaml

from src.config import ROOT_DIR
from src.kb.java_env import find_java
from src.kb.rules_builder import load_registry, read_swrl_files

needs_java = pytest.mark.skipif(find_java() is None, reason="Chưa cài Java")
SPECS = yaml.safe_load((ROOT_DIR / "config" / "rule_specs.yaml").read_text(encoding="utf-8"))
REG = load_registry()
VERSIONS = ["V1", "V2", "V3", "V4"]
TODAY = date(2026, 11, 4)

# Kết luận đi kèm hợp lệ của tình huống mẫu (suy luận nhiều bước)
EXTRA_OK = {
    "CHU_XM_GIAO_XE": {"CHUA_DU_TUOI_14_16"},
    "CHU_OT_GIAO_XE": {"OT_KHONG_GPLX"},
}


@pytest.fixture(scope="module")
def reasoner():
    from src.kb.reasoner import TrafficReasoner

    return TrafficReasoner()


# ---------------- sổ đăng ký, file luật ----------------

def test_registry_traceability():
    """Mỗi luật có mã, căn cứ (văn bản, điều, khoản, điểm, nguyên văn, ngày hiệu lực) và khớp file .swrl."""
    swrl = read_swrl_files()
    assert set(swrl) == set(REG["quy_tac"])
    for qid, q in REG["quy_tac"].items():
        assert q["swrl"] == swrl[qid] and f"duocSuyRaBoi(" in q["swrl"] and qid in q["swrl"]
        bases = q["can_cu"] if isinstance(q["can_cu"], list) else [q["can_cu"]]
        for b in bases:
            assert b["nguyen_van"].strip() and b["hieu_luc_tu"], qid
        if q["loai"] == "hanh_vi":
            c = q["can_cu"]
            assert c["van_ban"] and c["dieu"] and c["trich_dan"], qid


def test_every_behavior_version_has_rule():
    beh = yaml.safe_load((ROOT_DIR / "config" / "mvp_behaviors.yaml").read_text(encoding="utf-8"))["behaviors"]
    for b in beh:
        refs = list(b["refs"]) + [b["refs"][-1]] * (len(VERSIONS) - len(b["refs"]))
        for v, rid in zip(VERSIONS, refs):
            info = REG["hanh_vi"][b["code"]]["phien_ban"].get(v)
            if rid is None:
                assert info is None
            else:
                assert info["quy_tac"] and info["can_cu"]["id"] == rid, (b["code"], v)


def test_no_builtins_and_names_exist():
    """Luật không dùng built-in; mọi lớp/thuộc tính/cá thể được dẫn đều có trong ontology."""
    from src.kb.loader import load_world

    _, onto = load_world()
    for qid, q in REG["quy_tac"].items():
        assert "swrlb:" not in q["swrl"] and "greaterThan" not in q["swrl"]
        for name in re.findall(r"([A-Za-z_][\w-]*)\(", q["swrl"]):
            assert onto[name] is not None, (qid, name)
        for name in re.findall(r", ([A-Z][\w-]*)\)", q["swrl"]):
            assert onto[name] is not None or name.startswith("R"), (qid, name)


# ---------------- tình huống mẫu của từng luật ----------------

def _vi_du(code: str, v: str) -> dict:
    spec = SPECS["specs"][code]
    ex = dict(spec["vi_du"])
    for keys, ov in (spec.get("phien_ban") or {}).items():
        if v in [k.strip() for k in str(keys).split(",")] and "vi_du" in ov:
            ex = dict(ov["vi_du"])
    return dict(ex, version=v)


@needs_java
@pytest.mark.parametrize("v", VERSIONS)
def test_rule_examples(reasoner, v):
    codes = list(SPECS["specs"])
    results = reasoner.run([_vi_du(c, v) for c in codes], hom_nay=TODAY)
    errors = []
    for code, res in zip(codes, results):
        info = REG["hanh_vi"][code]["phien_ban"].get(v)
        got = res.ma_hanh_vi
        if info is None:
            if code in got:
                errors.append(f"{code}: không có quy định ở {v} nhưng vẫn kết luận")
            continue
        if code not in got:
            errors.append(f"{code}: không kết luận được (có: {sorted(got)})")
            continue
        k = next(x for x in res.hanh_vi if x.ma_hanh_vi == code)
        if k.dieu_khoan != [info["can_cu"]["iri"]]:
            errors.append(f"{code}: điều khoản {k.dieu_khoan} ≠ {info['can_cu']['iri']}")
        if not set(k.quy_tac) <= set(info["quy_tac"]) or not k.quy_tac:
            errors.append(f"{code}: quy tắc {k.quy_tac} không thuộc {info['quy_tac']}")
        extra = got - {code} - EXTRA_OK.get(code, set())
        if extra:
            errors.append(f"{code}: kết luận thừa {sorted(extra)}")
    assert errors == []


# ---------------- bẫy, khác thời điểm, loại trừ ----------------

TRAPS = [
    # (mô tả, vụ việc, mã kỳ vọng (tập), mã KHÔNG được có)
    ("vượt 4 km/h — không vi phạm", {"version": "V3", "xe": "OTo", "su_kien": {"tocDoThucTe": 64, "tocDoToiDaChoPhep": 60}},
     set(), {"OT_TD_05_10"}),
    ("nồng độ cồn 0 — không vi phạm", {"version": "V3", "xe": "OTo", "su_kien": {"nongDoConKhiTho": 0.0}}, set(), {"OT_CON_1"}),
    ("0,25 mg/L là mức 1 (biên)", {"version": "V3", "xe": "XeMoToHaiBanh", "su_kien": {"nongDoConKhiTho": 0.25}},
     {"XM_CON_1"}, {"XM_CON_2"}),
    ("xe đạp điện không đội mũ — không áp lỗi xe máy",
     {"version": "V3", "xe": "XeDapDien", "su_kien": {"doiMuBaoHiem": False}}, set(), {"XM_MU_BAO_HIEM"}),
    ("V3: quên GPLX, xe cá nhân — không vi phạm",
     {"version": "V3", "xe": "XeMoToHaiBanh", "su_kien": {"coGPLX": True, "mangTheoGPLX": False, "kinhDoanhVanTai": False}},
     set(), {"XM_KHONG_MANG_GPLX"}),
    ("V2: quên GPLX, xe cá nhân — vi phạm",
     {"version": "V2", "xe": "XeMoToHaiBanh", "su_kien": {"coGPLX": True, "mangTheoGPLX": False, "kinhDoanhVanTai": False}},
     {"XM_KHONG_MANG_GPLX"}, set()),
    ("V3: 17 tuổi, mô tô 45 cm3 — không vi phạm (ngưỡng 50 cm3)",
     {"version": "V3", "xe": "XeMoToHaiBanh", "xe_tt": {"dungTichXiLanh": 45}, "nguoi": {"tuoi": 17}},
     set(), {"CHUA_DU_TUOI_16_18_MOTO"}),
    ("V4: 17 tuổi, mô tô 45 cm3 — vi phạm (NĐ 238 bỏ ngưỡng 50 cm3)",
     {"version": "V4", "xe": "XeMoToHaiBanh", "xe_tt": {"dungTichXiLanh": 45}, "nguoi": {"tuoi": 17}},
     {"CHUA_DU_TUOI_16_18_MOTO"}, set()),
    ("ngược chiều trên cao tốc — chỉ áp lỗi cao tốc",
     {"version": "V3", "xe": "OTo", "su_kien": {"diNguocChieu": True}, "duong": ["DuongCaoToc"]},
     {"OT_NGUOC_CHIEU_CAO_TOC"}, {"OT_NGUOC_CHIEU"}),
    ("từ chối đo cồn — không áp thêm lỗi không chấp hành kiểm tra",
     {"version": "V3", "xe": "OTo", "su_kien": {"tuChoiKiemTraNongDoCon": True,
                                                "coYeuCauKiemTraCuaNguoiThiHanhCongVu": True, "chapHanhYeuCauKiemTra": False}},
     {"OT_TU_CHOI_DO_CON"}, {"KHONG_CHAP_HANH_KIEM_TRA"}),
    ("13 tuổi lái xe máy: không xử phạt người lái, chủ xe vẫn bị lỗi giao xe",
     {"version": "V3", "xe": "XeMoToHaiBanh", "xe_tt": {"dungTichXiLanh": 110}, "nguoi": {"tuoi": 13}, "chu_xe": {"tuoi": 40}},
     {"CHU_XM_GIAO_XE"}, {"CHUA_DU_TUOI_14_16"}),
    ("không xác định dung tích: không kết luận lỗi GPLX (phải hỏi lại)",
     {"version": "V3", "xe": "XeMoToHaiBanh", "su_kien": {"coGPLX": False}}, set(), {"XM_KHONG_GPLX_NHO", "XM_KHONG_GPLX_LON"}),
]


@needs_java
def test_traps(reasoner):
    results = reasoner.run([c for _, c, _, _ in TRAPS], hom_nay=TODAY)
    errors = []
    for (desc, _, must, mustnt), res in zip(TRAPS, results):
        if not must <= res.ma_hanh_vi or (mustnt & res.ma_hanh_vi):
            errors.append(f"{desc}: {sorted(res.ma_hanh_vi)}")
    assert errors == []


@needs_java
def test_different_versions_different_provision(reasoner):
    """Cùng hành vi vượt đèn đỏ (ô tô) ở bốn thời điểm → bốn căn cứ, mức phạt khác nhau."""
    case = {"xe": "OTo", "su_kien": {"khongChapHanhDenTinHieu": True}}
    days = ["2021-06-01", "2023-06-01", "2025-06-01", "2026-10-01"]
    res = reasoner.run([dict(case, ngay=d) for d in days], hom_nay=TODAY)
    provs = [r.hanh_vi[0].dieu_khoan[0] for r in res]
    assert provs == ["V1_ND100-D5-K5-a", "V2_ND100-D5-K5-a", "V3_ND168-D6-K9-b", "V4_ND168-D6-K9-b"]
    fines = [REG["hanh_vi"]["OT_DEN_DO"]["phien_ban"][r.phien_ban]["khung_phat"]["max"] for r in res]
    assert fines[0] < fines[1] < fines[2]


@needs_java
def test_two_step_inference_trace(reasoner):
    """Chủ xe giao xe cho người 15 tuổi: lỗi chưa đủ tuổi → người không đủ điều kiện → lỗi giao xe."""
    res = reasoner.run([{"version": "V1", "xe": "XeGanMay", "nguoi": {"tuoi": 15}, "chu_xe": {"tuoi": 45}}],
                       hom_nay=TODAY)[0]
    assert res.ma_hanh_vi == {"CHUA_DU_TUOI_14_16", "CHU_XM_GIAO_XE"}
    dk = res.nguoi_khong_du_dieu_kien[0]["quy_tac"]
    assert REG["quy_tac"][dk[0]]["loai"] == "dieu_kien_nguoi_lai"
    assert {b["id"] for b in REG["quy_tac"][dk[0]]["can_cu"]} == {"GTDB2008-D58-K1", "GTDB2008-D60-K1"}


@needs_java
def test_pellet_limitation():
    """Ghi nhận lý do chọn HermiT: trên ontology suy luận thật (đủ luật của phiên bản), Pellet 2.3.1 đi kèm
    owlready2 bỏ sót kết luận của luật SWRL có lớp ngưỡng trong thân luật; HermiT cho đúng. Nếu test này hỏng
    vì Pellet đã chạy đúng, có thể cân nhắc dùng lại Pellet."""
    from src.kb.reasoner import TrafficReasoner

    cases = [_vi_du(c, "V3") for c in ("OT_CON_2", "XM_TD_10_20", "OT_DEN_DO")]
    expect = [{"OT_CON_2"}, {"XM_TD_10_20"}, {"OT_DEN_DO"}]
    got = {eng: [r.ma_hanh_vi for r in TrafficReasoner(eng).run(cases, hom_nay=TODAY)] for eng in ("pellet", "hermit")}
    assert got["hermit"] == expect
    assert got["pellet"] != expect
