"""Kiểm chứng đầu ra LLM: mọi cụm từ LLM trả về phải có trong lời người dùng (chống LLM tự thêm thông tin).

LLM chỉ được CHÉP cụm từ bề mặt (prompt ``extraction``). Bước này kiểm tra tất định điều đó:

  * So khớp theo từ, sau khi bỏ dấu + viết thường (người dùng gõ không dấu / LLM sửa dấu vẫn khớp).
    Số trong lời người dùng viết bằng chữ ("tám mươi") được quy ra chữ số để khớp với "80" LLM chép lại.
  * Cụm từ được tách theo khoảng trắng thành từng mảnh; mảnh nào có từ KHÔNG xuất hiện trong lời người dùng thì
    bị bỏ. Ví dụ người dùng nói "đo được 0,3", LLM trả "0,3 mg/l" → giữ "0,3", bỏ đơn vị tự thêm "mg/l"
    (normalizer sẽ ghi giả định về đơn vị). Không còn mảnh nào → bỏ cả trường (slot checker sẽ hỏi lại).
  * Sự kiện: giữ nếu ``mo_ta`` khớp; nếu ``mo_ta`` là lời LLM diễn đạt lại nhưng ``trich_dan`` khớp thì thay
    ``mo_ta`` bằng ``trich_dan`` (để entity linker làm việc trên lời gốc, không trên suy diễn của LLM);
    cả hai đều không khớp → bỏ sự kiện.
  * Trường boolean (``nguoi_lai_khong_phai_chu_xe``) không có cụm từ để đối chiếu → giữ nguyên.

Chỉ đối chiếu với tin nhắn của người dùng, KHÔNG với câu hỏi hệ thống vừa hỏi (câu hỏi có liệt kê ví dụ
"xe máy, ô tô..." — chép từ đó là bịa).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.extraction import normalizer as N
from src.extraction.schema import SuKienTho, TrichXuatLLM

TRUONG_CHUOI = ("thoi_diem", "loai_xe", "dung_tich_xi_lanh", "cong_suat_dong_co", "tuoi_nguoi_lai",
                "nong_do_con", "toc_do_thuc_te", "toc_do_toi_da", "tuoi_chu_xe")
RE_TU = re.compile(r"[a-z]+|\d+")


@dataclass
class KetQuaKiemChung:
    trich_xuat: TrichXuatLLM
    loai_bo: list[str] = field(default_factory=list)      # mô tả từng chỗ bị bỏ/cắt (để log, UI, đánh giá)


def _tu(s: str) -> list[str]:
    """Tách từ không dấu, chữ thường; chữ và số tách riêng ('10/3/2025' → 10, 3, 2025; 'mg/l' → mg, l)."""
    return RE_TU.findall(N.bo_dau(N.chuan_hoa_chu(s)))


def tap_tu(tin_nhan: str) -> set[str]:
    """Tập từ của lời người dùng + chữ số tương ứng với các cụm số viết bằng chữ."""
    tu = set(_tu(tin_nhan))
    words = [w.strip(".,;:!?()\"'") for w in N.chuan_hoa_chu(tin_nhan).split()]
    run: list[str] = []
    for w in words + [""]:                                   # "" để xả cụm cuối
        if w in N.NUM_WORDS:
            run.append(w)
            continue
        if run:
            v = N.so_tu_chu(" ".join(run))
            if v is not None:
                tu.update(RE_TU.findall(f"{v:g}"))
            run = []
    return tu


def loc_cum(cum: str, tap: set[str]) -> str | None:
    """Giữ các mảnh (theo khoảng trắng) của ``cum`` có mọi từ nằm trong ``tap``; None nếu không còn gì."""
    giu = [m for m in cum.split() if (ws := _tu(m)) and all(w in tap for w in ws)]
    return " ".join(giu) if giu else None


def khop_hoan_toan(cum: str, tap: set[str]) -> bool:
    ws = _tu(cum)
    return bool(ws) and all(w in tap for w in ws)


def kiem_chung(tx: TrichXuatLLM, tin_nhan: str) -> KetQuaKiemChung:
    """Trả bản ``TrichXuatLLM`` chỉ còn cụm từ có trong ``tin_nhan`` + danh sách chỗ đã bỏ."""
    tap = tap_tu(tin_nhan)
    data = tx.model_dump()
    loai_bo: list[str] = []

    for f in TRUONG_CHUOI:
        v = data[f]
        if not v:
            continue
        moi = loc_cum(v, tap)
        if moi != v:
            loai_bo.append(f"{f}: '{v}' → " + (f"'{moi}'" if moi else "bỏ (không có trong lời người dùng)"))
        data[f] = moi

    duong = []
    for v in data["loai_duong"]:
        if moi := loc_cum(v, tap):
            duong.append(moi)
            if moi != v:
                loai_bo.append(f"loai_duong: '{v}' → '{moi}'")
        else:
            loai_bo.append(f"loai_duong: '{v}' → bỏ (không có trong lời người dùng)")
    data["loai_duong"] = duong

    su_kien = []
    for sk in tx.su_kien:
        if khop_hoan_toan(sk.mo_ta, tap):
            su_kien.append(sk.model_dump())
        elif sk.trich_dan and khop_hoan_toan(sk.trich_dan, tap):
            su_kien.append(SuKienTho(mo_ta=sk.trich_dan, trich_dan=sk.trich_dan, phu_dinh=sk.phu_dinh).model_dump())
            loai_bo.append(f"su_kien: mô tả '{sk.mo_ta}' là diễn đạt lại → dùng trích dẫn '{sk.trich_dan}'")
        else:
            loai_bo.append(f"su_kien: '{sk.mo_ta}' → bỏ (không có trong lời người dùng)")
    data["su_kien"] = su_kien

    return KetQuaKiemChung(TrichXuatLLM.model_validate(data), loai_bo)
