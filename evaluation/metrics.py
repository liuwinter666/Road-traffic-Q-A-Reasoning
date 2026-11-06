"""Tính metric từ kết quả chạy (evaluation/results/<cấu hình>/ket_qua.jsonl) và nhãn (data/test/scenarios.jsonl).

Metric (mục 10 đặc tả):
  * hanh_vi_{p,r,f1}        — phát hiện hành vi, so theo MÃ hành vi (micro); baseline không có mã → không tính.
  * dieu_khoan_{p,r,f1}     — phát hiện hành vi so theo ID ĐIỀU KHOẢN khớp tới điểm (dùng được cho cả baseline).
  * khop_tron_ven           — tỉ lệ tình huống có tập điều khoản dự đoán TRÙNG KHÍT nhãn (kể cả rỗng).
  * khung_phat_acc          — trong các điều khoản đoán đúng, tỉ lệ khung phạt (min–max) đúng.
  * phien_ban_acc           — đúng phiên bản pháp lý (hệ thống); baseline: không áp dụng.
  * hoi_dung_luc            — lượt đầu hỏi đủ ``hoi_luot_dau`` (khi có) / không hỏi gì (khi rỗng); kèm hỏi thừa, bỏ sót.
  * dan_sai_luat, dan_het_hieu_luc — trên mọi căn cứ được dẫn: không thuộc nhãn / thuộc văn bản không áp dụng cho
    phiên bản của vụ việc (vd. NĐ 100 cho vụ năm 2025). Tính trên kết luận có cấu trúc + văn bản câu trả lời.
  * truong_f1[<trường>]     — trích xuất từng trường có nhãn; su_kien_acc — sự kiện then chốt (kể cả suy ra);
    node_recall — node dấu hiệu kỳ vọng có trong kết quả.
  * do_tre_tb_s, do_tre_p95_s — mỗi lượt; tg_tinh_huong_tb_s.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from src.config import ROOT_DIR

KICH_BAN = ROOT_DIR / "data" / "test" / "scenarios.jsonl"
VAN_BAN_PHIEN_BAN = {"V1": {"ND100"}, "V2": {"ND100", "ND123"}, "V3": {"ND168"}, "V4": {"ND168", "ND238"}}
TRUONG_SO = ("nong_do_con_khi_tho", "nong_do_con_mau", "toc_do_thuc_te", "toc_do_toi_da", "dung_tich_xi_lanh",
             "tuoi_nguoi_lai")


def doc(f: Path) -> list[dict]:
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else (1.0 if not fn else 0.0)
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 4), round(r, 4), round(f, 4)


def _p95(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    return round(s[min(len(s) - 1, math.ceil(0.95 * len(s)) - 1)], 3)


def _van_ban(id_: str) -> str:
    return id_.split("-", 1)[0]


def _van_ban_trong_chu(text: str) -> set[str]:
    from src.explanation.verbalizer import RE_VAN_BAN_TU_DO

    out = set()
    for rx, fmt in RE_VAN_BAN_TU_DO:
        if fmt.startswith("ND"):
            out |= {fmt.format(m.group(1)) for m in rx.finditer(text or "")}
    return out


def tinh(ket_qua: list[dict], kich_ban: list[dict] | None = None) -> dict:
    """Metric tổng hợp + theo nhóm + chi tiết từng tình huống (để phân tích lỗi)."""
    kb = {x["id"]: x for x in (kich_ban or doc(KICH_BAN))}
    dem = defaultdict(int)
    nhom_dem: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    truong = defaultdict(lambda: [0, 0, 0])                        # tp, fp, fn
    do_tre, tg_th, chi_tiet = [], [], []
    co_ma = any("ma" in h for r in ket_qua for h in r.get("hanh_vi", []))
    for r in ket_qua:
        k = kb.get(r["id"])
        if k is None:
            continue
        n = k["nhan"]
        dem["so_tinh_huong"] += 1
        g = nhom_dem[k["nhom"]]
        g["n"] += 1
        if r.get("loi"):
            dem["loi"] += 1
            g["loi"] += 1
            chi_tiet.append({"id": r["id"], "nhom": k["nhom"], "loi": r["loi"]})
            continue
        hv = r.get("hanh_vi", [])
        g_ma, p_ma = set(n["hanh_vi"]), {h["ma"] for h in hv if h.get("ma")}
        g_id = {d["id"] for d in n["dieu_khoan"]}
        p_id = {h["id"] for h in hv if h.get("id")}
        for a, b, khoa in ((g_ma, p_ma, "ma"), (g_id, p_id, "id")):
            dem[f"tp_{khoa}"] += len(a & b)
            dem[f"fp_{khoa}"] += len(b - a)
            dem[f"fn_{khoa}"] += len(a - b)
        g["tp"] += len(g_id & p_id)
        g["fp"] += len(p_id - g_id)
        g["fn"] += len(g_id - p_id)
        dung_het = g_id == p_id
        dem["khop_tron_ven"] += dung_het
        g["khop_tron_ven"] += dung_het
        # khung phạt
        khung_chuan = {d["id"]: d["khung_phat"] for d in n["dieu_khoan"]}
        for h in hv:
            if h.get("id") in khung_chuan:
                dem["khung_n"] += 1
                dem["khung_dung"] += list(h.get("khung_phat") or []) == list(khung_chuan[h["id"]] or [])
        # phiên bản
        if r.get("phien_ban") is not None:
            dem["phien_ban_n"] += 1
            dem["phien_ban_dung"] += r["phien_ban"] == n["phien_ban"]
        # hỏi lại đúng lúc (lượt đầu)
        luot = r.get("luot") or []
        hoi_dau = set(luot[0]["hoi"]) if luot else set()
        if "can_hoi_luot_dau" in r:                                     # baseline: chỉ biết có hỏi hay không
            hoi_dau = {"_"} if r["can_hoi_luot_dau"] else set()
        can = set(n.get("hoi_luot_dau") or [])
        if can:
            ok = bool(hoi_dau) and (can <= hoi_dau or hoi_dau == {"_"})
            dem["hoi_bo_sot"] += not ok
        else:
            ok = not hoi_dau
            dem["hoi_thua"] += not ok
        dem["hoi_dung_luc"] += ok
        # Bản không tính câu hỏi XÁC NHẬN (hệ thống hỏi lại khi ánh xạ/suy ra có độ tin cậy chưa đủ — thận trọng
        # theo thiết kế, khác với hỏi do thiếu thông tin)
        hoi_khong_xn = hoi_dau - {"xac_nhan"}
        ok2 = (bool(hoi_khong_xn) and (can <= hoi_khong_xn or hoi_khong_xn == {"_"})) if can else not hoi_khong_xn
        dem["hoi_dung_luc_tru_xac_nhan"] += ok2
        dem["hoi_xac_nhan_luot_dau"] += "xac_nhan" in hoi_dau
        g["hoi_dung_luc"] += ok
        # dẫn sai luật / hết hiệu lực
        vb_ok = VAN_BAN_PHIEN_BAN[n["phien_ban"]]
        for h in hv:
            if not h.get("id"):
                continue
            dem["dan_n"] += 1
            dem["dan_sai"] += h["id"] not in g_id
            dem["dan_het_hieu_luc"] += _van_ban(h["id"]) not in vb_ok
        vb_chu = _van_ban_trong_chu(r.get("tra_loi") or "")
        dem["tra_loi_n"] += bool(r.get("tra_loi"))
        dem["tra_loi_vb_het_hieu_luc"] += bool(vb_chu - vb_ok)
        # trích xuất
        hs = r.get("ho_so") or {}
        tr = (n.get("truong") or {}) if "ho_so" in r else {}       # baseline không có hồ sơ trích xuất → không tính
        sai_truong = []
        for f_, v in tr.items():
            if f_ == "loai_xe":
                pred = hs.get("loai_xe")
                dung = pred in v
            elif f_ == "ngay":
                pred = hs.get("ngay_tu") if hs.get("ngay_tu") == hs.get("ngay_den") else None
                dung = pred == v
            else:
                pred = hs.get(f_)
                dung = pred is not None and abs(float(pred) - float(v)) < 1e-6
            t = truong[f_]
            if dung:
                t[0] += 1
            elif pred is None:
                t[2] += 1
                sai_truong.append(f"{f_}: thiếu")
            else:
                t[1] += 1
                t[2] += 1
                sai_truong.append(f"{f_}: {pred} ≠ {v}")
        sai_sk, thieu_node = [], []
        if "ho_so" in r:                                               # baseline: không áp dụng
            sk = hs.get("su_kien") or {}
            sai_sk = [p for p, v in (n.get("su_kien") or {}).items() if sk.get(p) != v]
            dem["su_kien_n"] += len(n.get("su_kien") or {})
            dem["su_kien_dung"] += len(n.get("su_kien") or {}) - len(sai_sk)
            thieu_node = [x for x in n.get("nodes") or [] if x not in set(r.get("nodes") or [])]
            dem["node_n"] += len(n.get("nodes") or [])
            dem["node_dung"] += len(n.get("nodes") or []) - len(thieu_node)
        # độ trễ
        do_tre += [x["thoi_gian_s"] for x in luot]
        if r.get("tong_thoi_gian_s") is not None:
            tg_th.append(r["tong_thoi_gian_s"])
        chi_tiet.append({"id": r["id"], "nhom": k["nhom"], "dung_het": dung_het, "trang_thai": r.get("trang_thai"),
                         "chuan": sorted(g_id), "du_doan": sorted(p_id), "phien_ban": r.get("phien_ban"),
                         "phien_ban_chuan": n["phien_ban"], "hoi_dau": sorted(hoi_dau), "hoi_can": sorted(can),
                         "hoi_dung_luc": ok, "sai_truong": sai_truong, "sai_su_kien": sai_sk, "thieu_node": thieu_node,
                         "hoi_ngoai_du_kien": r.get("hoi_ngoai_du_kien", []), "so_luot": len(luot)})

    n_ok = dem["so_tinh_huong"] - dem["loi"]
    out = {"so_tinh_huong": dem["so_tinh_huong"], "loi": dem["loi"]}
    if co_ma:
        out["hanh_vi_p"], out["hanh_vi_r"], out["hanh_vi_f1"] = _prf(dem["tp_ma"], dem["fp_ma"], dem["fn_ma"])
    out["dieu_khoan_p"], out["dieu_khoan_r"], out["dieu_khoan_f1"] = _prf(dem["tp_id"], dem["fp_id"], dem["fn_id"])
    out["khop_tron_ven"] = round(dem["khop_tron_ven"] / n_ok, 4) if n_ok else None
    out["khung_phat_acc"] = round(dem["khung_dung"] / dem["khung_n"], 4) if dem["khung_n"] else None
    out["phien_ban_acc"] = round(dem["phien_ban_dung"] / dem["phien_ban_n"], 4) if dem["phien_ban_n"] else None
    out["hoi_dung_luc"] = round(dem["hoi_dung_luc"] / n_ok, 4) if n_ok else None
    out["hoi_thua"], out["hoi_bo_sot"] = dem["hoi_thua"], dem["hoi_bo_sot"]
    out["hoi_dung_luc_tru_xac_nhan"] = round(dem["hoi_dung_luc_tru_xac_nhan"] / n_ok, 4) if n_ok else None
    out["hoi_xac_nhan_luot_dau"] = dem["hoi_xac_nhan_luot_dau"]
    out["dan_sai_luat"] = round(dem["dan_sai"] / dem["dan_n"], 4) if dem["dan_n"] else 0.0
    out["dan_het_hieu_luc"] = round(dem["dan_het_hieu_luc"] / dem["dan_n"], 4) if dem["dan_n"] else 0.0
    out["tra_loi_nhac_van_ban_het_hieu_luc"] = dem["tra_loi_vb_het_hieu_luc"]
    out["truong_f1"] = {f_: _prf(*v)[2] for f_, v in sorted(truong.items())}
    out["su_kien_acc"] = round(dem["su_kien_dung"] / dem["su_kien_n"], 4) if dem["su_kien_n"] else None
    out["node_recall"] = round(dem["node_dung"] / dem["node_n"], 4) if dem["node_n"] else None
    out["do_tre_tb_s"] = round(sum(do_tre) / len(do_tre), 3) if do_tre else None
    out["do_tre_p95_s"] = _p95(do_tre)
    out["tg_tinh_huong_tb_s"] = round(sum(tg_th) / len(tg_th), 2) if tg_th else None
    out["theo_nhom"] = {k: {"n": v["n"], "loi": v["loi"], "dieu_khoan_f1": _prf(v["tp"], v["fp"], v["fn"])[2],
                            "khop_tron_ven": round(v["khop_tron_ven"] / max(1, v["n"] - v["loi"]), 4),
                            "hoi_dung_luc": round(v["hoi_dung_luc"] / max(1, v["n"] - v["loi"]), 4)}
                        for k, v in sorted(nhom_dem.items())}
    out["chi_tiet"] = chi_tiet
    return out


def phan_loai_loi(ct: dict) -> str | None:
    """Tầng gây lỗi đầu tiên của một tình huống sai (phân tích lỗi theo tầng)."""
    if ct.get("loi"):
        return "lỗi chạy (LLM/hạ tầng)"
    if ct["dung_het"] and ct["hoi_dung_luc"]:
        return None
    if ct["trang_thai"] == "can_hoi":
        return "hội thoại: hỏi lại không dứt (không kết luận)"
    if not ct["hoi_dung_luc"] and ct["dung_het"]:
        return "hội thoại: hỏi thừa / bỏ sót câu hỏi"
    if ct["phien_ban"] != ct["phien_ban_chuan"]:
        return "thời điểm: sai phiên bản pháp lý"
    if ct["sai_truong"]:
        return "trích xuất / chuẩn hóa: sai trường"
    if ct["sai_su_kien"] or ct["thieu_node"]:
        return "ánh xạ node / suy ra sự kiện"
    return "suy luận / luật (đầu vào đúng nhưng kết luận sai)"
