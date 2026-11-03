"""Bảng tốc độ TT 31/2019 và TT 38/2024 được trích từ văn bản, kèm căn cứ và khoảng hiệu lực."""

from src.ingest import speed_limits


def _src(d, key):
    return next(x for x in d["nguon"] if x["nguon"] == key)


def test_speed_limits_tt38():
    s = _src(speed_limits.build(), "TT38")
    g = {x["ten"]: x for x in s["nhom"]}
    moto = g["Xe mô tô"]
    assert (moto["ngoai_khu_dong_dan_cu"]["duong_doi"], moto["ngoai_khu_dong_dan_cu"]["duong_hai_chieu"]) == (70, 60)
    assert (moto["trong_khu_dong_dan_cu"]["duong_doi"], moto["trong_khu_dong_dan_cu"]["duong_hai_chieu"]) == (60, 50)
    assert g["Xe gắn máy và các loại xe tương tự"]["moi_loai_duong"]["gia_tri"] == 40
    oto = g["Xe ô tô chở người đến 28 chỗ (trừ xe buýt); ô tô tải đến 3,5 tấn"]["ngoai_khu_dong_dan_cu"]
    assert (oto["duong_doi"], oto["duong_hai_chieu"]) == (90, 80) and oto["can_cu"]["id"] == "TT38-D6-K2"
    assert s["cao_toc"]["toi_da"]["gia_tri"] == 120 and s["cao_toc"]["toi_thieu"]["gia_tri"] == 60
    assert s["hieu_luc_tu"] == "2025-01-01"


def test_speed_limits_tt31():
    s = _src(speed_limits.build(), "TT31")
    assert (s["hieu_luc_tu"], s["hieu_luc_den"]) == ("2019-10-15", "2024-12-31")
    g = {x["ten"]: x for x in s["nhom"]}
    oto = g["Xe ô tô con, xe ô tô chở người đến 30 chỗ (trừ xe buýt); ô tô tải đến 3,5 tấn"]
    assert (oto["ngoai_khu_dong_dan_cu"]["duong_doi"], oto["ngoai_khu_dong_dan_cu"]["duong_hai_chieu"]) == (90, 80)
    gm = g["Xe gắn máy (kể cả xe máy điện) và các loại xe tương tự"]["moi_loai_duong"]
    assert gm["gia_tri"] == 40 and "không quá 40 km/h" in gm["can_cu"]["nguyen_van"]
    assert s["cao_toc"]["toi_da"]["gia_tri"] == 120 and "toi_thieu" not in s["cao_toc"]
