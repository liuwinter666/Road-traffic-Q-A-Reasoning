"""Test quyết định mức phạt: căn cứ trong cấu hình có thật, mức trung bình, tình tiết, người chưa thành niên,
chế tài có điều kiện, trừ điểm khi nhiều hành vi."""

from __future__ import annotations

import json
import re
from datetime import date

import pytest
import yaml

from src.config import PROCESSED_DIR, ROOT_DIR
from src.kb.java_env import find_java

needs_java = pytest.mark.skipif(find_java() is None, reason="Chưa cài Java")
CFG = yaml.safe_load((ROOT_DIR / "config" / "penalty_decision.yaml").read_text(encoding="utf-8"))
TODAY = date(2026, 11, 4)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def _items(d):
    if isinstance(d, dict):
        if "id" in d and "trich" in d:
            yield d
        for v in d.values():
            yield from _items(v)


def test_penalty_quotes_exist():
    """Mọi trích dẫn trong config/penalty_decision.yaml có nguyên văn trong phần tử được dẫn."""
    def load(name):
        with (PROCESSED_DIR / f"{name}.jsonl").open(encoding="utf-8") as f:
            return {r["id"]: r for r in map(json.loads, f)}
    srcs = {"LXLVPHC": load("support_lxlvphc"), "ND168": load("articles_v4")}
    v3 = load("articles_v3")
    for it in _items(CFG):
        rec = srcs[it["id"].split("-")[0]][it["id"]]
        assert _norm(it["trich"]) in _norm(rec["full_text"]), it["id"]
        if it["id"].startswith("ND168"):
            assert _norm(it["trich"]) in _norm(v3[it["id"]]["full_text"]), it["id"]   # cả V3 lẫn V4


@pytest.fixture(scope="module")
def run():
    from src.kb.penalty import quyet_dinh
    from src.kb.reasoner import TrafficReasoner

    r = TrafficReasoner()

    def _run(cases):
        res = r.run(cases, hom_nay=TODAY)
        return [quyet_dinh(k, c, date.fromisoformat(c["ngay"]) if c.get("ngay") else TODAY)
                for k, c in zip(res, cases)]
    return _run


@needs_java
def test_penalty_scenarios(run):
    cases = [
        # 0: mức trung bình, một hành vi
        {"ngay": "2025-03-01", "xe": "OTo", "nguoi": {"tuoi": 35}, "su_kien": {"khongChapHanhDenTinHieu": True}},
        # 1: giảm nhẹ
        {"ngay": "2025-03-01", "xe": "OTo", "nguoi": {"tuoi": 35},
         "su_kien": {"khongChapHanhDenTinHieu": True, "thanhThatHoiLoi": True}},
        # 2: 16–18 tuổi: không quá 1/2
        {"ngay": "2025-03-01", "xe": "XeMoToHaiBanh", "nguoi": {"tuoi": 17}, "su_kien": {"doiMuBaoHiem": False}},
        # 3: 15 tuổi: không phạt tiền
        {"ngay": "2025-03-01", "xe": "XeGanMay", "nguoi": {"tuoi": 15}, "su_kien": {"doiMuBaoHiem": False}},
        # 4: nhiều hành vi bị trừ điểm → chỉ trừ mức cao nhất; tổng tiền = tổng
        {"ngay": "2025-03-01", "xe": "XeMoToHaiBanh", "nguoi": {"tuoi": 30},
         "su_kien": {"nongDoConKhiTho": 0.3, "coHieuLenhNguoiDieuKhienGT": True, "chapHanhHieuLenh": False}},
        # 5: tái phạm lạng lách → tịch thu phương tiện; không tính tái phạm là tăng nặng lần nữa
        {"ngay": "2025-03-01", "xe": "XeMoToHaiBanh", "nguoi": {"tuoi": 30},
         "su_kien": {"langLachDanhVong": True, "taiPham": True}},
        # 6: vi phạm năm 2021: căn cứ mức phạt của Luật XLVPHC chỉ có câu chữ từ 2022
        {"ngay": "2021-03-01", "xe": "OTo", "nguoi": {"tuoi": 35}, "su_kien": {"khongChapHanhDenTinHieu": True}},
    ]
    qd = run(cases)
    d0 = qd[0].hanh_vi[0]
    assert d0.khung_phat == (18_000_000, 20_000_000) and d0.muc_de_xuat == 19_000_000
    assert qd[1].hanh_vi[0].muc_de_xuat < 19_000_000 and qd[1].hanh_vi[0].tinh_tiet_giam == ["TTGN_2"]
    d2 = qd[2].hanh_vi[0]
    assert d2.muc_de_xuat == (d2.khung_phat[0] + d2.khung_phat[1]) // 2 // 2
    assert qd[3].hanh_vi[0].hinh_thuc_chinh == "canh_cao" and qd[3].hanh_vi[0].muc_de_xuat is None
    q4 = qd[4]
    assert len(q4.hanh_vi) == 2 and q4.tru_diem_ap_dung == max(d.tru_diem for d in q4.hanh_vi)
    assert q4.tong_tien_de_xuat == sum(d.muc_de_xuat for d in q4.hanh_vi)
    assert any(c["id"] == "ND168-D50-K1-b" for c in q4.can_cu_chung)
    d5 = qd[5].hanh_vi[0]
    assert any(c.loai == "tich_thu_phuong_tien" and c.trang_thai == "ap_dung_do_thoa_dieu_kien" for c in d5.che_tai)
    assert d5.tinh_tiet_tang == []
    assert any("LXLVPHC-D23-K4" in n and "không có trong dữ liệu" in n.lower() for n in qd[6].ghi_chu)
    assert qd[6].tru_diem_ap_dung is None                                 # NĐ 100 không có trừ điểm
