"""Test trích hình thức xử phạt bổ sung / trừ điểm từ câu chữ nghị định."""

from __future__ import annotations

import json

import pytest

from src.config import PROCESSED_DIR
from src.kb.rules_builder import load_registry
from src.kb.sanctions import applies_to, extract_all, split_clauses


def recs(v: str) -> dict[str, dict]:
    with (PROCESSED_DIR / f"articles_{v}.jsonl").open(encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f)}


@pytest.fixture(scope="module")
def v1():
    r = recs("v1")
    return extract_all(r, {"5", "6", "21"})


@pytest.fixture(scope="module")
def v3():
    r = recs("v3")
    return extract_all(r, {"6", "7", "12", "18"})


def _find(ss, cid, loai, cond=None):
    return [s for s in ss if s.can_cu_id == cid and s.loai == loai and s.dieu_kien == cond]


def test_split_keeps_target_lists():
    t = ("Thực hiện hành vi quy định tại điểm a khoản 6; điểm a, điểm b khoản 7 Điều này bị tước quyền sử dụng "
         "Giấy phép lái xe từ 02 tháng đến 04 tháng; tái phạm hành vi quy định tại điểm b khoản 8 Điều này bị "
         "tịch thu phương tiện.")
    assert len(split_clauses(t)) == 2


def test_v1_unconditional_and_conditional(v1):
    s = _find(v1, "ND100-D5-K11-d", "tuoc_gplx")[0]                      # "khoản 9 Điều này hoặc tái phạm ..."
    assert s.gia_tri == {"tu_thang": 3, "den_thang": 5} and s.targets == [("5", "9", None)]
    t = _find(v1, "ND100-D5-K11-d", "tuoc_gplx", "tai_pham")[0]
    assert t.targets == [("5", "7", "b")]
    g = _find(v1, "ND100-D5-K11-c", "tuoc_gplx", "gay_tai_nan")[0]       # "... mà gây tai nạn ... thì bị ...: <list>"
    assert len(g.targets) > 20
    tt = _find(v1, "ND100-D6-K10-c", "tich_thu_phuong_tien", "tai_pham_hoac_nhieu_lan")[0]
    assert ("6", "8", "b") in tt.targets


def test_v3_points_and_confiscation(v3):
    d = _find(v3, "ND168-D6-K16-d", "tru_diem")[0]
    assert d.gia_tri == {"so_diem": 10} and ("6", "9", "a") in d.targets and ("6", "10", None) in d.targets
    assert applies_to(d, ("6", "10", "a"))                               # cả khoản 10 → mọi điểm của khoản
    t = _find(v3, "ND168-D7-K11-c", "tich_thu_phuong_tien", "tai_pham")[0]  # khoản dẫn "Tịch thu ... sau đây:"
    assert t.targets == [("7", "9", "a")]
    # "Ngoài việc bị áp dụng hình thức xử phạt, ... quy định tại ... bị trừ điểm ..."
    assert _find(v3, "ND168-D18-K12", "tru_diem")[0].gia_tri == {"so_diem": 2}
    assert _find(v3, "ND168-D12-K17", "tru_diem")[0].targets == [("12", "11", "a"), ("12", "11", "b")]


def test_registry_sanctions_for_behaviors():
    reg = load_registry()["hanh_vi"]
    con2 = reg["OT_CON_2"]["phien_ban"]
    assert {(s["loai"], s["dieu_kien"]) for s in con2["V1"]["che_tai"]} >= {("tuoc_gplx", None)}
    assert any(s["loai"] == "tru_diem" and s["gia_tri"]["so_diem"] == 10 for s in con2["V3"]["che_tai"])
    assert not any(s["loai"] == "tru_diem" for s in con2["V2"]["che_tai"])   # NĐ 100 không có trừ điểm
    ll = reg["XM_LANG_LACH"]["phien_ban"]["V3"]["che_tai"]
    assert any(s["loai"] == "tich_thu_phuong_tien" and s["dieu_kien"] == "tai_pham" for s in ll)
