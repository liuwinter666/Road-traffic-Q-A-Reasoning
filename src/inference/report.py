"""Trình bày kết quả một lượt thành văn bản (tất định, không dùng LLM).

Bản này là phương án dự phòng của verbalizer (LLM lỗi hoặc không qua kiểm tra chống bịa) và là đầu ra khi tắt
diễn đạt bằng LLM (``--khong-dien-dat``); chuỗi suy luận lấy từ tracer.
Thứ tự theo mục 8 đặc tả: hành vi → căn cứ → khung phạt → mức đề xuất + lý do → hình thức bổ sung/trừ điểm →
chuỗi suy luận → lưu ý.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.inference.pipeline import KetQuaLuot

TEN_CHE_TAI = {"tuoc_gplx": "Tước quyền sử dụng GPLX", "tru_diem": "Trừ điểm GPLX",
               "tich_thu_phuong_tien": "Tịch thu phương tiện", "tich_thu": "Tịch thu", "thu_hoi": "Thu hồi"}
TRANG_THAI_CHE_TAI = {"ap_dung": "áp dụng", "ap_dung_do_thoa_dieu_kien": "áp dụng (đã thỏa điều kiện)",
                      "neu_thoa_dieu_kien": "nếu thỏa điều kiện", "khong_ap_dung": "không áp dụng"}
NGUON = {"truc_tiep": "bạn nêu", "suy_ra": "suy ra từ lời kể", "xac_nhan": "bạn đã xác nhận",
         "tra_bang": "tra bảng tốc độ của thông tư", "tinh_toan": "tính toán", "xep_loai": "xếp loại theo luật"}


def _tien(x: int | None) -> str:
    return "—" if x is None else f"{x:,}".replace(",", ".") + " đồng"


def _che_tai(ct) -> str:
    g = ct.gia_tri
    if ct.loai == "tuoc_gplx":
        v = f"từ {g['tu_thang']} đến {g['den_thang']} tháng"
    elif ct.loai == "tru_diem":
        v = f"{g['so_diem']} điểm"
    else:
        v = g.get("doi_tuong", "")
    dk = f" — điều kiện: {ct.dieu_kien}" if ct.dieu_kien else ""
    return f"{TEN_CHE_TAI.get(ct.loai, ct.loai)} {v}".strip() + f" [{TRANG_THAI_CHE_TAI.get(ct.trang_thai, ct.trang_thai)}" \
        f"{dk}] (căn cứ {ct.can_cu_id})"


def _rut_gon(s: str, n: int = 260) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def trinh_bay(kq: KetQuaLuot, chi_tiet: bool = False) -> str:
    """Văn bản trả lời cho một lượt."""
    if kq.trang_thai == "can_hoi":
        dong = ["Mình cần thêm thông tin:"] + [f"  {i}. {q.cau_hoi}" for i, q in enumerate(kq.cau_hoi, 1)]
        if chi_tiet:
            dong += [f"     (lý do: {q.ly_do})" for q in kq.cau_hoi]
        return "\n".join(dong)

    sl, qd, dl = kq.suy_luan, kq.quyet_dinh, kq.du_lieu
    out = [f"Phiên bản pháp lý: {sl.ghi_chu_phien_ban}"]
    if kq.trang_thai == "khong_phat_hien":
        out.append("Không phát hiện hành vi vi phạm nào trong phạm vi hệ thống (MVP: xe mô tô/gắn máy, ô tô; "
                   "~60 hành vi phổ biến) với các sự kiện đã nêu.")
    rule_of = {k.ma_hanh_vi: k for k in sl.ket_luan}
    for i, d in enumerate(qd.hanh_vi, 1):
        out.append(f"\n{i}. {d.ten}")
        out.append(f"   Căn cứ: {d.dieu_khoan} ({d.dieu_khoan_id})")
        if d.can_cu:
            out.append(f"   Nguyên văn: “{_rut_gon(d.can_cu[0]['nguyen_van'].split(chr(10))[-1])}”")
        if d.hinh_thuc_chinh == "khong_xu_phat":
            out.append("   Hình thức: không xử phạt")
        elif d.khung_phat:
            out.append(f"   Khung phạt: {_tien(d.khung_phat[0])} – {_tien(d.khung_phat[1])}")
            out.append(f"   Mức đề xuất: {_tien(d.muc_de_xuat)}" if d.hinh_thuc_chinh == "phat_tien"
                       else f"   Hình thức: {d.hinh_thuc_chinh.replace('_', ' ')}")
        elif d.hinh_thuc_chinh == "canh_cao":
            out.append("   Hình thức: cảnh cáo")
        for ly in d.ly_do:
            out.append(f"   - {ly}")
        for ct in d.che_tai:
            if ct.trang_thai != "khong_ap_dung" or chi_tiet:
                out.append(f"   + {_che_tai(ct)}")
        if k := rule_of.get(d.ma_hanh_vi):
            out.append(f"   Quy tắc suy luận: {', '.join(k.quy_tac)} → {', '.join(k.dieu_khoan)}")

    if len(qd.hanh_vi) > 1:
        out.append(f"\nTổng tiền phạt đề xuất: {_tien(qd.tong_tien_de_xuat)}")
    if qd.tru_diem_ap_dung:
        out.append(f"Trừ điểm GPLX: {qd.tru_diem_ap_dung} điểm")
    loai_tru = [k for k in sl.ket_luan if k.bi_loai_tru_boi]
    for k in loai_tru:
        ld = k.ly_do_loai_tru or {}
        can_cu = f"“{ld['nguyen_van']}”" if ld.get("nguyen_van") else ""
        if ld.get("id"):
            can_cu += f" ({ld['id']})"
        out.append(f"(Không áp {k.ma_hanh_vi} vì đã áp {k.bi_loai_tru_boi} cho cùng hành vi"
                   + (f" — {can_cu}" if can_cu else "") + ")")
    for p in sl.nguoi_khong_du_dieu_kien:
        out.append(f"Người không đủ điều kiện điều khiển xe: {p['nguoi']} (quy tắc {', '.join(p['quy_tac'])})")

    # Chuỗi suy luận (tracer): sự kiện → điều kiện → quy tắc → hành vi → điều khoản
    if kq.trace is not None and (dong := kq.trace.dong_suy_luan()):
        out.append("\nChuỗi suy luận:")
        out += [f"  - {d}" for d in dong]
    out.append("\nSự kiện dùng để suy luận:")
    if kq.trace is not None:
        for n in kq.trace.su_kien:
            nguon = NGUON.get(n.nguon or "", "")
            out.append(f"  - {n.mo_ta}" + (f" ({nguon})" if nguon else ""))
    else:
        case = dl.case
        out.append(f"  - Phương tiện: {case['xe']}" + (f" {case['xe_tt']}" if case.get("xe_tt") else ""))
        for k, v in case["su_kien"].items():
            nguon = NGUON.get(dl.nguon_su_kien.get(k, "truc_tiep"), "")
            out.append(f"  - {k} = {v}" + (f" ({nguon})" if nguon else ""))
    suy_ra = [s for s in kq.ho_so.su_kien_suy_ra if s.dang_ap_dung]
    if suy_ra:
        out.append("Sự kiện suy ra (LLM nêu, hệ thống kiểm tra bằng chứng):")
        for s in suy_ra:
            out.append(f"  - {s.mo_ta()} — “{s.bang_chung}” (tin cậy {s.do_tin_cay:.2f}"
                       + (", bạn đã xác nhận" if s.trang_thai == "xac_nhan" else "") + ")")
            if s.giai_thich and (chi_tiet or "căn cứ:" in s.giai_thich):
                out.append(f"      {s.giai_thich}")

    notes = kq.trace.ghi_chu if kq.trace is not None else list(dict.fromkeys(kq.ghi_chu + qd.ghi_chu))
    if notes:
        out.append("\nLưu ý:")
        out += [f"  - {n}" for n in notes]
    if kq.ho_so.cum_tu_loai_bo and chi_tiet:
        out.append("  - Bỏ qua (không có trong lời bạn): " + "; ".join(kq.ho_so.cum_tu_loai_bo))
    out.append("  - Kết quả chỉ mang tính tham khảo, không thay thế quyết định của người có thẩm quyền.")
    if kq.lien_quan:
        out.append("\n" + goi_y_lien_quan(kq.lien_quan))
    return "\n".join(out)


def goi_y_lien_quan(ds: list) -> str:
    """Khối gợi ý tra cứu (RAG) — ghi rõ không phải kết luận."""
    dong = ["Quy định có thể liên quan (gợi ý tra cứu theo nội dung, hệ thống CHƯA mô hình hóa nên không kết luận):"]
    for b, s in ds:
        dong.append(f"  - {b.trich_dan}: “{_rut_gon(b.text, 200)}”")
    return "\n".join(dong)
