"""Test chuẩn hóa số, đơn vị, ngày tiếng Việt."""

from datetime import date

import pytest

from src.extraction import normalizer as N

T = date(2026, 11, 4)


@pytest.mark.parametrize("s,v", [
    ("một trăm hai mươi", 120), ("tám mươi", 80), ("mười lăm", 15), ("hai mươi mốt", 21),
    ("một trăm linh năm", 105), ("không phẩy ba", 0.3), ("không phẩy hai lăm", 0.25),
    ("không phẩy không tám", 0.08), ("một nghìn năm trăm", 1500),
])
def test_so_tu_chu(s, v):
    assert N.so_tu_chu(s) == pytest.approx(v)


@pytest.mark.parametrize("s,v", [("80 cây", 80), ("tám mươi cây số giờ", 80), ("65km/h", 65),
                                 ("một trăm hai mươi km/h", 120), ("1.500", 1500), ("0,3", 0.3)])
def test_so_va_toc_do(s, v):
    assert N.so(s) == pytest.approx(v)


@pytest.mark.parametrize("s,v,loai,gia_dinh", [
    ("0,3mg/1 lít khí thở", 0.3, "khi_tho", False), ("không phẩy hai lăm mg/l", 0.25, "khi_tho", False),
    ("50mg/100ml máu", 50, "mau", False), ("60 miligam trên 100 mililit máu", 60, "mau", False),
    ("0.3 miligam", 0.3, "khi_tho", True), ("80", 80, "mau", True),
])
def test_nong_do_con(s, v, loai, gia_dinh):
    dl, l = N.nong_do_con(s)
    assert dl.gia_tri == pytest.approx(v) and l == loai and bool(dl.gia_dinh) == gia_dinh


def test_nong_do_mo_ho():
    assert N.nong_do_con("7") == (None, None)       # không đoán được đơn vị → slot checker hỏi


def test_dung_tich_cong_suat():
    assert N.dung_tich("110 phân khối").gia_tri == 110 and N.dung_tich("125cc").gia_tri == 125
    assert N.dung_tich("xe 50 phân").gia_tri == 50
    assert N.cong_suat("1500W").gia_tri == pytest.approx(1.5) and N.cong_suat("4kW").gia_tri == 4


def test_tuoi():
    assert N.tuoi("mười lăm tuổi").gia_tri == 15
    t = N.tuoi("sinh 2k9", date(2025, 3, 1))
    assert t.gia_tri == 16 and t.gia_dinh


@pytest.mark.parametrize("s,tu,den,dcx", [
    ("10/3/2025", date(2025, 3, 10), date(2025, 3, 10), "ngay"),
    ("ngày 5 tháng 8 năm 2026", date(2026, 8, 5), date(2026, 8, 5), "ngay"),
    ("tối qua", date(2026, 11, 3), date(2026, 11, 3), "tuong_doi"),
    ("tháng 3 năm 2026", date(2026, 3, 1), date(2026, 3, 31), "thang"),
    ("năm 2021", date(2021, 1, 1), date(2021, 12, 31), "nam"),
    ("ngày 20/12", date(2025, 12, 20), date(2025, 12, 20), "ngay"),   # chưa tới 20/12 năm nay → năm trước
])
def test_thoi_diem(s, tu, den, dcx):
    td = N.thoi_diem(s, T)
    assert (td.tu, td.den, td.do_chinh_xac) == (tu, den, dcx)


def test_bo_dau():
    assert N.bo_dau("Vượt đèn đỏ") == "Vuot den do"
