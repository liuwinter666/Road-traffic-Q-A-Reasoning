"""Test kiểm chứng cụm từ: LLM không được thêm thông tin người dùng không nói.

Các ca lấy từ lỗi thật của Ollama qwen2.5:7b khi chạy thử Phase 4.
"""

from src.extraction.grounding import kiem_chung, loc_cum, tap_tu
from src.extraction.schema import SuKienTho, TrichXuatLLM


def test_bo_loai_xe_va_ngay_tu_bia():
    msg = "Thấy CSGT vẫy thì em rồ ga chạy luôn, không đội mũ bảo hiểm"
    tx = TrichXuatLLM(thoi_diem="04/11/2026", loai_xe="xe máy",
                      su_kien=[SuKienTho(mo_ta="rồ ga chạy", trich_dan="thấy CSGT vẫy thì em rồ ga chạy luôn"),
                               SuKienTho(mo_ta="không đội mũ bảo hiểm", trich_dan="không đội mũ bảo hiểm")])
    kq = kiem_chung(tx, msg)
    assert kq.trich_xuat.loai_xe is None and kq.trich_xuat.thoi_diem is None
    assert [s.mo_ta for s in kq.trich_xuat.su_kien] == ["rồ ga chạy", "không đội mũ bảo hiểm"]
    assert len(kq.loai_bo) == 2


def test_giu_cum_dung_nguyen_van():
    msg = "Hôm 10/3/2025 tôi lái ô tô chạy 80 cây trong khu dân cư, đường đôi"
    tx = TrichXuatLLM(thoi_diem="10/3/2025", loai_xe="ô tô", toc_do_thuc_te="80 cây",
                      loai_duong=["trong khu dân cư", "đường đôi"])
    kq = kiem_chung(tx, msg)
    assert kq.trich_xuat == tx and kq.loai_bo == []


def test_khong_phan_biet_dau_va_hoa_thuong():
    kq = kiem_chung(TrichXuatLLM(loai_xe="Xe máy", su_kien=[SuKienTho(mo_ta="vượt đèn đỏ", trich_dan="vượt đèn đỏ")]),
                    "toi di xe may vuot den do")
    assert kq.trich_xuat.loai_xe == "Xe máy" and len(kq.trich_xuat.su_kien) == 1


def test_cat_don_vi_tu_them():
    kq = kiem_chung(TrichXuatLLM(nong_do_con="0,3 mg/l"), "bị thổi, đo được 0,3")
    assert kq.trich_xuat.nong_do_con == "0,3" and "mg/l" in kq.loai_bo[0]


def test_so_viet_bang_chu():
    assert {"80", "120", "0", "25"} <= tap_tu("chạy tám mươi cây, có lúc một trăm hai mươi, đo không phẩy hai lăm")
    assert loc_cum("80 cây", tap_tu("chạy tám mươi cây")) == "80 cây"


def test_ngay_viet_bang_chu():
    kq = kiem_chung(TrichXuatLLM(thoi_diem="10/3/2025"), "ngày 10 tháng 3 năm 2025 tôi bị phạt")
    assert kq.trich_xuat.thoi_diem == "10/3/2025"


def test_su_kien_dien_dat_lai_dung_trich_dan():
    kq = kiem_chung(TrichXuatLLM(su_kien=[SuKienTho(mo_ta="bỏ chạy", trich_dan="rồ ga chạy luôn")]),
                    "thấy CSGT thì rồ ga chạy luôn")
    assert kq.trich_xuat.su_kien[0].mo_ta == "rồ ga chạy luôn"


def test_su_kien_bia_bi_bo():
    kq = kiem_chung(TrichXuatLLM(su_kien=[SuKienTho(mo_ta="vượt đèn đỏ", trich_dan="tôi vượt đèn đỏ")]),
                    "tôi không đội mũ bảo hiểm")
    assert kq.trich_xuat.su_kien == []


def test_khong_doi_chieu_voi_cau_hoi_he_thong(tmp_path):
    """Câu hỏi hệ thống liệt kê 'xe máy, ô tô' — người dùng trả lời 'có' thì LLM không được lấy 'xe máy'."""
    import json

    from src.extraction.entity_linker import EntityLinker
    from src.extraction.llm_extractor import LLMExtractor
    from src.llm.client import DiskCache, LLMClient

    class Fake(LLMClient):
        provider = "fake"

        def _call(self, prompt, system, json_schema, schema_model):
            return json.dumps({"loai_xe": "xe máy"})

    ex = LLMExtractor(client=Fake("f", cache=DiskCache(tmp_path, enabled=False), max_rpm=0),
                      linker=EntityLinker(embedder=None))
    hs = ex.ho_so("có", cau_hoi_truoc=["Bạn điều khiển loại xe gì (xe máy, xe máy điện, ô tô...)?"])
    assert hs.loai_xe is None and hs.cum_tu_loai_bo
    ex_off = LLMExtractor(client=ex.client, linker=ex.linker, kiem_chung_cum_tu=False)
    assert ex_off.ho_so("có").loai_xe is not None          # ablation: tắt kiểm chứng thì giữ nguyên
