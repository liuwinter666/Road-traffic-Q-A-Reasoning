"""Quyết định mức xử phạt đề xuất từ kết quả suy luận.

Đầu vào: ``KetQuaSuyLuan`` (reasoner.py) + dict vụ việc + sổ đăng ký luật (khung phạt, chế tài theo điều khoản).
Quy tắc và căn cứ: ``config/penalty_decision.yaml`` (Luật XLVPHC; khoản 1 Điều 50 NĐ 168 cho trừ điểm).

Đầu ra là đề xuất THAM KHẢO: khung phạt, mức đề xuất và lý do, hình thức bổ sung (vô điều kiện / có điều
kiện đã thỏa / có điều kiện chưa xác định), trừ điểm GPLX, tổng tiền phạt, các lưu ý (kể cả hiệu lực của căn
cứ tại thời điểm vi phạm).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache

import yaml

from src.config import PROCESSED_DIR, ROOT_DIR
from src.kb.reasoner import KetQuaSuyLuan
from src.kb.rules_builder import load_registry
from src.kb.temporal import KHONG_CO_DU_LIEU, trang_thai_hieu_luc

CONFIG_FILE = ROOT_DIR / "config" / "penalty_decision.yaml"
COND_LABEL = {"tai_pham": "tái phạm", "nhieu_lan": "vi phạm nhiều lần",
              "tai_pham_hoac_nhieu_lan": "tái phạm hoặc vi phạm nhiều lần", "gay_tai_nan": "gây tai nạn giao thông"}


@lru_cache(maxsize=1)
def _cfg() -> dict:
    return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _records(name: str) -> dict[str, dict]:
    with (PROCESSED_DIR / f"{name}.jsonl").open(encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f)}


def _can_cu(item: dict) -> dict:
    return {"id": item["id"], "nguyen_van": item["trich"]}


@dataclass
class CheTai:
    loai: str
    gia_tri: dict
    dieu_kien: str | None
    trang_thai: str            # ap_dung | ap_dung_do_thoa_dieu_kien | neu_thoa_dieu_kien | khong_ap_dung
    can_cu_id: str
    nguyen_van: str


@dataclass
class DeXuatHanhVi:
    ma_hanh_vi: str
    ten: str
    dieu_khoan: str
    dieu_khoan_id: str
    khung_phat: tuple[int, int] | None
    canh_cao: bool
    hinh_thuc_chinh: str                        # phat_tien | canh_cao | khong_xu_phat
    muc_de_xuat: int | None
    tinh_tiet_tang: list[str] = field(default_factory=list)
    tinh_tiet_giam: list[str] = field(default_factory=list)
    ly_do: list[str] = field(default_factory=list)
    can_cu: list[dict] = field(default_factory=list)
    che_tai: list[CheTai] = field(default_factory=list)
    tru_diem: int | None = None


@dataclass
class QuyetDinh:
    phien_ban: str
    hanh_vi: list[DeXuatHanhVi]
    tong_tien_de_xuat: int
    tru_diem_ap_dung: int | None
    ghi_chu: list[str] = field(default_factory=list)
    can_cu_chung: list[dict] = field(default_factory=list)


def _phan(tu: int, mau: int) -> str:
    """1/2 → "một nửa", 2/2 → "toàn bộ", còn lại "tu/mau"."""
    return {(1, 2): "một nửa", (1, 1): "toàn bộ", (2, 2): "toàn bộ"}.get((tu, mau), f"{tu}/{mau}")


def _adjust(lo: int, hi: int, n_tang: int, n_giam: int) -> tuple[int, str]:
    """Mức đề xuất trong khung theo quy ước (TODO_VERIFY ở cấu hình)."""
    tb = (lo + hi) // 2
    so_buoc = _cfg()["muc_phat"]["quy_uoc_dieu_chinh"]["so_buoc"]
    net = max(-so_buoc, min(so_buoc, n_tang - n_giam))
    if net > 0:
        return tb + (hi - tb) * net // so_buoc, f"tăng {_phan(net, so_buoc)} khoảng cách từ mức trung bình lên mức tối đa"
    if net < 0:
        return tb - (tb - lo) * (-net) // so_buoc, f"giảm {_phan(-net, so_buoc)} khoảng cách từ mức trung bình xuống mức tối thiểu"
    return tb, "mức trung bình của khung"


def _tien_vn(s: str) -> str:
    """Dấu phân cách hàng nghìn kiểu Việt (5,000,000 → 5.000.000)."""
    return s.replace(",", ".")


def _ten_tinh_tiet(kq: KetQuaSuyLuan) -> dict[str, str]:
    """Mã tình tiết (TTGN_2) → tên theo luật + căn cứ, vd. "tự nguyện khai báo, thành thật hối lỗi (khoản 2 Điều 9
    Luật Xử lý vi phạm hành chính)". Tên lấy từ mô tả của chính quy tắc đã kích hoạt trong sổ đăng ký luật."""
    q = load_registry()["quy_tac"]
    out: dict[str, str] = {}
    for t in kq.tinh_tiet:
        ten = "; ".join(dict.fromkeys(q[r]["mo_ta"][0].lower() + q[r]["mo_ta"][1:] for r in t["quy_tac"] if r in q))
        ids = [q[r]["can_cu"]["id"] for r in t["quy_tac"] if r in q]
        cc = ""
        if ids and (m := re.match(r"LXLVPHC-D(\d+)(?:-K(\d+))?(?:-([a-z]+))?$", ids[0])):
            diem = f"điểm {m.group(3).replace('dd', 'đ')} " if m.group(3) else ""
            khoan = f"khoản {m.group(2)} " if m.group(2) else ""
            cc = f" ({diem}{khoan}Điều {m.group(1)} Luật Xử lý vi phạm hành chính)"
        out[t["tinh_tiet"]] = (ten or t["tinh_tiet"]) + cc
    return out


def _note_effect(sid: str, ngay: date, notes: list[str]) -> None:
    """Ghi chú nếu căn cứ (văn bản hợp nhất) chưa có câu chữ tại ngày vi phạm."""
    rec = _records("support_lxlvphc").get(sid)
    if rec is None:
        return
    t = trang_thai_hieu_luc(rec, ngay)
    if t.ma == KHONG_CO_DU_LIEU:
        notes.append(f"{sid}: {t.giai_thich}")


def quyet_dinh(kq: KetQuaSuyLuan, case: dict, ngay: date | None = None) -> QuyetDinh:
    """Đề xuất xử phạt cho vụ việc."""
    cfg, reg = _cfg(), load_registry()
    v = kq.phien_ban
    ngay = ngay or date.today()
    tuoi = (case.get("nguoi") or {}).get("tuoi")
    sk = dict(case.get("su_kien") or {})
    notes: list[str] = []
    if kq.mac_dinh_phien_ban:
        notes.append(kq.ghi_chu_phien_ban)
    chung = [_can_cu(cfg["muc_phat"]["can_cu"])]
    _note_effect("LXLVPHC-D23-K4", ngay, notes)

    tinh_tiet = {t["tinh_tiet"] for t in kq.tinh_tiet}
    out: list[DeXuatHanhVi] = []
    for k in kq.hanh_vi:
        hv = reg["hanh_vi"][k.ma_hanh_vi]
        info = hv["phien_ban"][v]
        fine = info["khung_phat"]
        nguoi_lai = k.chu_the.endswith("nguoi_lai")
        d = DeXuatHanhVi(k.ma_hanh_vi, hv["ten"], info["can_cu"]["trich_dan"], info["can_cu"]["id"],
                         (fine["min"], fine["max"]) if fine else None, info["canh_cao"],
                         "canh_cao" if (info["canh_cao"] and not fine) else "phat_tien", None)
        d.can_cu.append({"id": info["can_cu"]["id"], "nguyen_van": info["can_cu"]["nguyen_van"]})
        # Tình tiết (bỏ tình tiết đã là dấu hiệu của chính hành vi — khoản 2 Điều 10). "Tái phạm"/"vi phạm nhiều
        # lần" đã làm phát sinh chế tài có điều kiện của chính hành vi (vd. tịch thu phương tiện khi tái phạm
        # lạng lách) thì cũng không tính lại là tình tiết tăng nặng.
        trung = cfg["tinh_tiet_trung_hanh_vi"]["bang"]
        dk_da_dung = {f for s in info["che_tai"] if s["dieu_kien"] in cfg["dieu_kien_che_tai"]
                      for f in cfg["dieu_kien_che_tai"][s["dieu_kien"]] if sk.get(f)}
        for t in sorted(tinh_tiet):
            if t == "TTTN_b" and dk_da_dung & {"taiPham", "viPhamNhieuLan"}:
                d.ly_do.append("Không tính tái phạm/vi phạm nhiều lần là tình tiết tăng nặng vì đã là điều kiện "
                               "của chế tài quy định cho chính hành vi")
                d.can_cu.append(_can_cu(cfg["tinh_tiet_trung_hanh_vi"]))
                continue
            if k.ma_hanh_vi in trung.get(t, []):
                d.ly_do.append(f"Không tính {t} là tình tiết tăng nặng vì đã là dấu hiệu của hành vi")
                d.can_cu.append(_can_cu(cfg["tinh_tiet_trung_hanh_vi"]))
                continue
            (d.tinh_tiet_tang if t.startswith("TTTN") else d.tinh_tiet_giam).append(t)
        # Mức phạt tiền
        if d.khung_phat:
            lo, hi = d.khung_phat
            muc, why = _adjust(lo, hi, len(d.tinh_tiet_tang), len(d.tinh_tiet_giam))
            d.muc_de_xuat = muc
            if not (d.tinh_tiet_tang or d.tinh_tiet_giam):
                d.ly_do.append(_tien_vn(f"Khung {lo:,}–{hi:,} đồng; {why}"))
            else:
                ten = _ten_tinh_tiet(kq)
                for nhom, ds in (("tăng nặng", d.tinh_tiet_tang), ("giảm nhẹ", d.tinh_tiet_giam)):
                    for t in ds:
                        d.ly_do.append(f"Tình tiết {nhom}: {ten.get(t, t)}")
                tb = (lo + hi) // 2
                d.ly_do.append(_tien_vn(f"Khung {lo:,}–{hi:,} đồng; mức trung bình {tb:,} đồng."))
                if muc != tb:
                    huong = ("giảm, nhưng không thấp hơn mức tối thiểu" if muc < tb else
                             "tăng, nhưng không vượt quá mức tối đa")
                    nhom = "giảm nhẹ" if muc < tb else "tăng nặng"
                    d.ly_do.append(f"Có tình tiết {nhom} nên mức phạt được {huong} của khung "
                                   "(khoản 4 Điều 23 Luật Xử lý vi phạm hành chính).")
                    d.ly_do.append(_tien_vn(
                        f"Mức đề xuất {muc:,} đồng: {why} (mức tham khảo của hệ thống — chưa có văn bản hướng dẫn "
                        "mức điều chỉnh cụ thể)."))
                else:
                    d.ly_do.append("Tình tiết tăng nặng và giảm nhẹ bù trừ nhau nên giữ mức trung bình của khung.")
                d.can_cu.append(_can_cu(cfg["muc_phat"]["can_cu_gioi_han"]))
        # Người chưa thành niên (chỉ áp cho người điều khiển)
        if nguoi_lai and tuoi is not None:
            nc = cfg["nguoi_chua_thanh_nien"]
            if tuoi < 14:
                d.hinh_thuc_chinh, d.muc_de_xuat = "khong_xu_phat", None
                d.ly_do.append(f"Người chưa đủ 14 tuổi không bị xử phạt VPHC ({nc['duoi_14']['suy_ra']})")
                d.can_cu.append(_can_cu(nc["duoi_14"]))
            elif tuoi < 16:
                d.hinh_thuc_chinh, d.muc_de_xuat = "canh_cao", None
                d.ly_do.append("Người từ đủ 14 đến dưới 16 tuổi: chỉ xử phạt khi vi phạm do cố ý và không áp dụng "
                               "phạt tiền — hình thức có thể áp dụng: cảnh cáo")
                d.can_cu += [_can_cu(nc["tu_14_den_16"][x]) for x in ("chi_khi_co_y", "khong_phat_tien")]
                _note_effect("LXLVPHC-D134-K3", ngay, notes)
            elif tuoi < 18 and d.muc_de_xuat is not None:
                d.muc_de_xuat = int(d.muc_de_xuat * nc["tu_16_den_18"]["he_so_toi_da"])
                d.ly_do.append("Người từ đủ 16 đến dưới 18 tuổi: mức phạt không quá 1/2 mức áp dụng với người thành niên")
                d.can_cu.append(_can_cu(nc["tu_16_den_18"]))
                _note_effect("LXLVPHC-D134-K3", ngay, notes)
        # Chế tài bổ sung, trừ điểm
        for s in info["che_tai"]:
            cond = s["dieu_kien"]
            if cond is None:
                st = "ap_dung"
            elif cond in cfg["dieu_kien_che_tai"]:
                st = ("ap_dung_do_thoa_dieu_kien" if any(sk.get(f) for f in cfg["dieu_kien_che_tai"][cond])
                      else "khong_ap_dung")
            else:
                st = "neu_thoa_dieu_kien"
            if d.hinh_thuc_chinh == "khong_xu_phat":
                st = "khong_ap_dung"
            # Thu hồi giấy phép lái xe (không hợp lệ, bị tẩy xóa...) chỉ có đối tượng khi người lái CÓ giấy phép:
            # đã biết không có GPLX (coGPLX = false) thì không có gì để thu hồi
            if s["loai"] == "thu_hoi" and "giấy phép lái xe" in (s["gia_tri"].get("doi_tuong") or "") \
                    and sk.get("coGPLX") is False:
                st = "khong_ap_dung"
            ct = CheTai(s["loai"], s["gia_tri"], COND_LABEL.get(cond, cond), st, s["can_cu_id"], s["nguyen_van"])
            if s["loai"] == "tru_diem":
                if st in ("ap_dung", "ap_dung_do_thoa_dieu_kien"):
                    d.tru_diem = max(d.tru_diem or 0, s["gia_tri"]["so_diem"])
            d.che_tai.append(ct)
        out.append(d)

    # Trừ điểm GPLX (khoản 1 Điều 50 NĐ 168)
    tru = None
    td = cfg["tru_diem"]
    if v in td["ap_dung_phien_ban"]:
        diem = [d.tru_diem for d in out if d.tru_diem]
        if diem:
            tru = max(diem)
            if len(diem) > 1:
                notes.append(f"Nhiều hành vi bị trừ điểm: chỉ trừ theo hành vi bị trừ nhiều điểm nhất ({tru} điểm)")
                chung.append(_can_cu(td["nhieu_hanh_vi"]))
            con = sk.get("diemConLai")
            if con is not None and con < tru:
                tru = con
                notes.append(f"Số điểm còn lại ({con}) ít hơn số điểm bị trừ: trừ hết số điểm còn lại")
                chung.append(_can_cu(td["khong_qua_diem_con_lai"]))
            if sk.get("gplxDangBiTuoc"):
                tru = 0
                notes.append("GPLX đang trong thời hạn bị tước quyền sử dụng: không trừ điểm")
                chung.append(_can_cu(td["dang_bi_tuoc"]))
    tong = sum(d.muc_de_xuat or 0 for d in out)
    if len(out) > 1:
        notes.append("Xử phạt về từng hành vi vi phạm; tổng tiền phạt là tổng các mức đề xuất")
        chung.append(_can_cu(cfg["nhieu_hanh_vi"]))
    return QuyetDinh(v, out, tong, tru, list(dict.fromkeys(notes)),
                     list({c["id"] + c["nguyen_van"]: c for c in chung}.values()))
