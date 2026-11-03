"""Test chọn phiên bản và trạng thái hiệu lực (kể cả một phần nội dung, có điều kiện)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from src.config import PROCESSED_DIR
from src.kb import temporal as T

TODAY = date(2026, 11, 3)


def recs(name: str) -> dict[str, dict]:
    with (PROCESSED_DIR / f"{name}.jsonl").open(encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f)}


@pytest.mark.parametrize("ngay,version", [
    (date(2020, 1, 1), "V1"), (date(2021, 12, 31), "V1"), (date(2022, 1, 1), "V2"),
    (date(2024, 12, 31), "V2"), (date(2025, 1, 1), "V3"), (date(2026, 8, 14), "V3"), (date(2026, 8, 15), "V4"),
])
def test_chon_phien_ban(ngay, version):
    r = T.chon_phien_ban(ngay, hom_nay=TODAY)
    assert r.version == version and not r.mac_dinh


def test_chon_phien_ban_mac_dinh():
    r = T.chon_phien_ban(None, hom_nay=TODAY)
    assert r.version == "V4" and r.mac_dinh and "Không rõ thời điểm" in r.ghi_chu


def test_truoc_pham_vi_du_lieu():
    with pytest.raises(ValueError):
        T.chon_phien_ban(date(2019, 6, 1), hom_nay=TODAY)


def test_hieu_luc_mot_phan():
    r = recs("articles_v4")["ND168-D20-K5-l"]
    t = T.trang_thai_hieu_luc(r, TODAY)
    assert t.ma == T.MOT_PHAN and t.co_the_ap_dung and "dưới 08 chỗ" in t.giai_thich
    assert T.trang_thai_hieu_luc(r, date(2028, 1, 1)).ma == T.CO_HIEU_LUC


def test_hieu_luc_co_dieu_kien_coi_la_chua_hieu_luc():
    r = recs("articles_v4")["ND168-D20-K5-n"]
    assert T.trang_thai_hieu_luc(r, TODAY).ma == T.CHUA_HIEU_LUC
    t = T.trang_thai_hieu_luc(r, date(2030, 1, 1))      # đã qua mốc 2029 nhưng điều kiện chưa xác nhận
    assert t.ma == T.CHUA_HIEU_LUC_DIEU_KIEN and not t.co_the_ap_dung and "khoang chở khách" in t.giai_thich


def test_hieu_luc_chi_co_dieu_kien_khong_co_ngay():
    t = T.trang_thai_hieu_luc(recs("articles_v3")["ND168-D32-K1-b"], TODAY)
    assert t.ma == T.CHUA_XAC_DINH and not t.co_the_ap_dung


def test_hieu_luc_rieng_cua_diem():
    r = recs("articles_v3")["ND168-D6-K3-m"]          # điểm m khoản 3 Điều 6 NĐ 168: từ 01/01/2026
    assert T.trang_thai_hieu_luc(r, date(2025, 6, 1)).ma == T.CHUA_HIEU_LUC
    assert T.trang_thai_hieu_luc(r, date(2026, 1, 1)).ma == T.CO_HIEU_LUC


def test_van_ban_hop_nhat_khong_co_cau_chu_cu():
    r = recs("support_lxlvphc")["LXLVPHC-D23-K4"]
    t = T.trang_thai_hieu_luc(r, date(2021, 6, 1))
    assert t.ma == T.KHONG_CO_DU_LIEU and "không có trong dữ liệu" in t.giai_thich.lower()
    assert T.trang_thai_hieu_luc(r, date(2023, 1, 1)).ma == T.CO_HIEU_LUC


def test_luat_ttatgt_hieu_luc_rieng_khoan():
    s = recs("support_lttatgt")
    assert T.trang_thai_hieu_luc(s["LTTATGT-D10-K3"], date(2025, 6, 1)).ma == T.CHUA_HIEU_LUC
    assert T.trang_thai_hieu_luc(s["LTTATGT-D10-K3"], date(2026, 1, 1)).ma == T.CO_HIEU_LUC
    assert T.trang_thai_hieu_luc(s["LTTATGT-D56-K1"], date(2024, 6, 1)).ma == T.CHUA_HIEU_LUC
