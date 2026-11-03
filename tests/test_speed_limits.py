"""Bảng tốc độ TT 38 được trích từ văn bản, kèm căn cứ."""

from src.ingest import speed_limits


def test_speed_limits_from_tt38():
    d = speed_limits.build()
    g = {x["ten"]: x for x in d["nhom"]}
    moto = g["Xe mô tô"]
    assert (moto["ngoai_khu_dong_dan_cu"]["duong_doi"], moto["ngoai_khu_dong_dan_cu"]["duong_hai_chieu"]) == (70, 60)
    assert (moto["trong_khu_dong_dan_cu"]["duong_doi"], moto["trong_khu_dong_dan_cu"]["duong_hai_chieu"]) == (60, 50)
    assert g["Xe gắn máy và các loại xe tương tự"]["moi_loai_duong"]["gia_tri"] == 40
    oto = g["Xe ô tô chở người đến 28 chỗ (trừ xe buýt); ô tô tải đến 3,5 tấn"]["ngoai_khu_dong_dan_cu"]
    assert (oto["duong_doi"], oto["duong_hai_chieu"]) == (90, 80) and oto["can_cu"]["id"] == "TT38-D6-K2"
    assert d["cao_toc"]["toi_da"]["gia_tri"] == 120 and d["cao_toc"]["toi_thieu"]["gia_tri"] == 60
    assert d["hieu_luc_tu"] == "2025-01-01"
