"""Chuyển kết quả một lượt (``KetQuaLuot``) thành dict JSON — dùng chung cho API, giao diện và CLI ``--json``."""

from __future__ import annotations

import dataclasses
from datetime import date


def chuyen(x):
    """dataclass / Pydantic / date / tuple → kiểu JSON."""
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        return {k: chuyen(v) for k, v in dataclasses.asdict(x).items()}
    if hasattr(x, "model_dump"):
        return x.model_dump(mode="json")
    if isinstance(x, dict):
        return {str(k): chuyen(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [chuyen(v) for v in x]
    if isinstance(x, date):
        return x.isoformat()
    return x


def nguyen_van_can_cu(trace) -> list[dict]:
    """Nguyên văn (kèm tiêu đề điều + câu dẫn khoản) của mọi căn cứ trong trace — kết luận trước, căn cứ khác sau."""
    from src.explanation.retriever import lay

    if trace is None:
        return []
    v, ngay = trace.phien_ban["ma"], trace.phien_ban.get("ngay")
    ngay = date.fromisoformat(ngay) if ngay else None
    ket_luan = [k.dieu_khoan.id for k in trace.ket_luan]
    ids = list(dict.fromkeys(ket_luan + list(trace.can_cu_hop_le())))
    out = []
    for i in ids:
        b = lay(i, v if i.startswith("ND") else None, ngay)
        if b is None:
            continue
        out.append({"id": i, "trich_dan": b.trich_dan, "van_ban": b.so_hieu, "nguyen_van": b.full_text,
                    "hieu_luc_tu": b.hieu_luc_tu, "hieu_luc_den": b.hieu_luc_den, "la_ket_luan": i in ket_luan})
    return out


def ket_qua_json(kq) -> dict:
    """Toàn bộ thông tin một lượt cho giao diện: câu trả lời, câu hỏi, hồ sơ, kết luận, trace, đồ thị, nguyên văn."""
    qd, tr = kq.quyet_dinh, kq.trace
    hanh_vi = []
    if qd is not None:
        for d in qd.hanh_vi:
            hanh_vi.append({"ma": d.ma_hanh_vi, "ten": d.ten, "dieu_khoan": d.dieu_khoan, "dieu_khoan_id": d.dieu_khoan_id,
                            "khung_phat": list(d.khung_phat) if d.khung_phat else None, "muc_de_xuat": d.muc_de_xuat,
                            "hinh_thuc_chinh": d.hinh_thuc_chinh, "tru_diem": d.tru_diem, "ly_do": d.ly_do,
                            "che_tai": [chuyen(c) for c in d.che_tai]})
    return {
        "trang_thai": kq.trang_thai,
        "tra_loi": kq.tra_loi,
        "cau_hoi": [{"truong": q.truong, "cau_hoi": q.cau_hoi, "ly_do": q.ly_do} for q in kq.cau_hoi],
        "ho_so": kq.ho_so.model_dump(mode="json"),
        "phien_ban": (tr.phien_ban if tr else
                      {"ma": kq.suy_luan.phien_ban, "ghi_chu": kq.suy_luan.ghi_chu_phien_ban} if kq.suy_luan else None),
        "hanh_vi": hanh_vi,
        "tong_tien_de_xuat": qd.tong_tien_de_xuat if qd else None,
        "tru_diem_ap_dung": qd.tru_diem_ap_dung if qd else None,
        "case": chuyen(kq.du_lieu.case) if kq.du_lieu else None,
        "trace": tr.to_dict() if tr else None,
        "chuoi_suy_luan": tr.dong_suy_luan() if tr else [],
        "do_thi": tr.do_thi() if tr else None,
        "dieu_khoan_nguyen_van": nguyen_van_can_cu(tr),
        "dien_dat": chuyen(kq.dien_dat) if kq.dien_dat else None,
        "lien_quan": [{"id": b.id, "trich_dan": b.trich_dan, "text": b.text, "diem": round(s, 3)} for b, s in kq.lien_quan],
        "ghi_chu": kq.ghi_chu,
        "thoi_gian_s": {k: round(v, 3) for k, v in kq.thoi_gian_s.items()},
    }
