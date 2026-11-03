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


def test_luat_118_lui_hieu_luc_khoan_3_dieu_10():
    """Luật 118 (điểm a khoản 20 Điều 7, hiệu lực 01/01/2026) lùi hiệu lực khoản 3 Điều 10 Luật TTATGT
    từ 01/01/2026 sang 01/07/2026 — mốc cũ không bao giờ có hiệu lực."""
    v2025, v2026a, v2026b = (recs(f"support_lttatgt_{x}") for x in ("2025", "2026a", "2026b"))
    assert T.trang_thai_hieu_luc(v2025["LTTATGT-D10-K3"], date(2025, 6, 1)).ma == T.CHUA_HIEU_LUC
    assert T.trang_thai_hieu_luc(v2026a["LTTATGT-D10-K3"], date(2026, 3, 1)).ma == T.CHUA_HIEU_LUC
    t = T.trang_thai_hieu_luc(v2026b["LTTATGT-D10-K3"], date(2026, 8, 1))
    assert t.ma == T.CO_HIEU_LUC and v2026b["LTTATGT-D10-K3"]["history"]   # câu chữ mới do Luật 118 sửa
    assert "01 tháng 7 năm 2026" in v2026a["LTTATGT-D88-K2"]["text"]


def test_luat_118_hieu_luc_mot_phan_dieu_35():
    r = recs("support_lttatgt_2026b")["LTTATGT-D35-K2"]
    assert [x["tu"] for x in r["hieu_luc_chi_tiet"]] == ["2026-07-01", "2028-01-01", "2029-01-01"]
    t = T.trang_thai_hieu_luc(r, date(2030, 1, 1))
    assert t.ma == T.MOT_PHAN and "lộ trình do Chính phủ quy định" in t.giai_thich


def test_chon_van_ban_bo_tro():
    c = T.chon_van_ban_bo_tro
    assert c("toc_do_toi_da", date(2021, 5, 1)).khoa == "TT31"
    assert c("toc_do_toi_da", date(2025, 1, 1)).khoa == "TT38"
    assert c("toc_do_toi_da", date(2019, 6, 1)).khoa is None          # trước TT 31 — không có dữ liệu
    assert c("dieu_kien_nguoi_lai", date(2024, 12, 31)).khoa == "GTDB2008"
    assert c("dieu_kien_nguoi_lai", date(2025, 3, 1)).khoa == "LTTATGT_2025"
    assert c("dieu_kien_nguoi_lai", date(2026, 3, 1)).khoa == "LTTATGT_2026A"
    assert c("dieu_kien_nguoi_lai", date(2026, 9, 1)).khoa == "LTTATGT_2026B"
