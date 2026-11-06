"""Chạy hệ thống trên bộ tình huống, ghi kết quả từng tình huống để tính metric.

    python -m evaluation.run_eval --cau-hinh day_du                # hệ thống đầy đủ (kể cả verbalizer)
    python -m evaluation.run_eval --cau-hinh khong_fact_inducer    # ablation
    python -m evaluation.run_eval --cau-hinh day_du --chi S01,S23 --lam-lai

Cấu hình: day_du | khong_normalizer | khong_entity_linker | khong_fact_inducer | khong_kiem_chung.
Ablation tắt verbalizer (không ảnh hưởng kết luận) để tiết kiệm lượt gọi LLM.

Người dùng mô phỏng: hệ thống hỏi trường nào thì trả lời bằng ``tra_loi[trường]`` của tình huống (gộp các câu vào
một tin nhắn); câu xác nhận thì trả lời "đúng" khi mọi mục được hỏi khớp nhãn (``su_kien``, ``loai_xe``, ``nodes``),
ngược lại "không"; câu hỏi không có trong ``tra_loi`` → "Tôi không rõ." (ghi nhận là hỏi ngoài dự kiến). Tối đa 5 lượt.

Kết quả: evaluation/results/<cấu hình>/ket_qua.jsonl (một dòng mỗi tình huống; chạy tiếp được nếu bị ngắt).
LLM hết hạn mức (429 liên tiếp) → dừng sớm, chạy lại sau sẽ tiếp tục các tình huống còn thiếu.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import date
from pathlib import Path

from loguru import logger

from src.config import ROOT_DIR

KICH_BAN = ROOT_DIR / "data" / "test" / "scenarios.jsonl"
KET_QUA = ROOT_DIR / "evaluation" / "results"
CAU_HINH = {
    "day_du": {"dien_dat": True},
    "khong_normalizer": {"normalizer": True},
    "khong_entity_linker": {"linker": True},
    "khong_fact_inducer": {"fact_inducer": False},
    "khong_kiem_chung": {"kiem_chung": False},
}
SO_LUOT_TOI_DA = 5


def doc_kich_ban(chi: set[str] | None = None) -> list[dict]:
    ds = [json.loads(x) for x in KICH_BAN.read_text(encoding="utf-8").splitlines() if x.strip()]
    return [x for x in ds if not chi or x["id"] in chi]


def tao_pipeline(ten: str, reasoner, hom_nay: date):
    from src.extraction.entity_linker import EntityLinker
    from src.extraction.llm_extractor import LLMExtractor
    from src.inference.pipeline import Pipeline
    from src.llm.client import get_llm_client

    from evaluation.thanh_phan_ablation import NormalizerDonGian, linker_nhan_ontology

    c = CAU_HINH[ten]
    client = get_llm_client()
    linker = linker_nhan_ontology() if c.get("linker") else EntityLinker()
    ex = LLMExtractor(client=client, linker=linker, kiem_chung_cum_tu=c.get("kiem_chung", True),
                      normalizer=NormalizerDonGian() if c.get("normalizer") else None)
    return Pipeline(client=client, extractor=ex, reasoner=reasoner, dung_fact_inducer=c.get("fact_inducer", True),
                    hom_nay=hom_nay, dung_dien_dat=c.get("dien_dat", False), dung_goi_y_lien_quan=False)


# ---------------------------------------------------------------------------
# Người dùng mô phỏng
# ---------------------------------------------------------------------------

def _khop_nhan(muc: str, hs, nhan: dict) -> bool:
    """Mục xác nhận có khớp nhãn chuẩn không (người dùng mô phỏng chỉ đồng ý điều đúng với nhãn)."""
    sk_chuan, nodes_chuan = nhan.get("su_kien") or {}, set(nhan.get("nodes") or [])
    if muc == "loai_xe":
        ds = (nhan.get("truong") or {}).get("loai_xe")
        return ds is not None and hs.loai_xe in ds
    if muc.startswith("su_kien:"):
        p = muc.split(":", 1)[1]
        s = next((x for x in hs.su_kien_suy_ra if x.thuoc_tinh == p), None)
        return s is not None and p in sk_chuan and sk_chuan[p] == s.gia_tri
    if muc.startswith("lien_ket:"):
        node = muc.split(":", 1)[1].split("|", 1)[0]
        d = next((x for x in hs.dau_hieu if x.node == node), None)
        return node in nodes_chuan or (d is not None and d.su_kien and all(sk_chuan.get(k) == v for k, v in d.su_kien.items()))
    return False


def tra_loi_mo_phong(kq, kb: dict) -> tuple[str, list[str]]:
    """(tin nhắn trả lời, các trường được hỏi nhưng không có trong tra_loi)."""
    xn = [q for q in kq.cau_hoi if q.truong == "xac_nhan"]
    if xn:
        dong_y = all(_khop_nhan(m, kq.ho_so, kb["nhan"]) for q in xn for m in q.muc_xac_nhan)
        return ("Đúng." if dong_y else "Không phải."), []
    phan, ngoai = [], []
    for q in kq.cau_hoi:
        if q.truong in kb["tra_loi"]:
            if kb["tra_loi"][q.truong] not in phan:
                phan.append(kb["tra_loi"][q.truong])
        else:
            ngoai.append(q.truong)
    return (" ".join(phan) if phan else "Tôi không rõ."), ngoai


# ---------------------------------------------------------------------------
# Một tình huống
# ---------------------------------------------------------------------------

def chay_mot(pl, kb: dict) -> dict:
    from src.extraction.slot_checker import nodes_hieu_luc
    from src.inference.pipeline import PhienLamViec

    phien = PhienLamViec()
    luot, hoi_ngoai = [], []
    tin = kb["luot"][0]
    kq = None
    for i in range(SO_LUOT_TOI_DA):
        t0 = time.perf_counter()
        kq = pl.xu_ly(phien, tin)
        luot.append({"tin_nhan": tin, "trang_thai": kq.trang_thai, "hoi": [q.truong for q in kq.cau_hoi],
                     "thoi_gian_s": round(time.perf_counter() - t0, 3), "chi_tiet_s": kq.thoi_gian_s})
        if kq.trang_thai != "can_hoi":
            break
        tin, ngoai = tra_loi_mo_phong(kq, kb)
        hoi_ngoai += ngoai
    hs = kq.ho_so
    nodes = set(nodes_hieu_luc(hs))
    if kq.suy_luan is not None:
        for ten, lop in kq.suy_luan.lop_suy_ra.items():
            if ten.endswith("hanh_vi_lai"):
                nodes |= set(lop)
    hv = []
    if kq.quyet_dinh is not None:
        for d in kq.quyet_dinh.hanh_vi:
            hv.append({"ma": d.ma_hanh_vi, "id": d.dieu_khoan_id, "trich_dan": d.dieu_khoan,
                       "khung_phat": list(d.khung_phat) if d.khung_phat else None, "muc_de_xuat": d.muc_de_xuat})
    dd = kq.dien_dat
    return {
        "trang_thai": kq.trang_thai, "so_luot": len(luot), "luot": luot, "hoi_ngoai_du_kien": hoi_ngoai,
        "phien_ban": kq.suy_luan.phien_ban if kq.suy_luan else None, "hanh_vi": hv,
        "ho_so": {"loai_xe": hs.loai_xe, "ngay_tu": hs.ngay_tu.isoformat() if hs.ngay_tu else None,
                  "ngay_den": hs.ngay_den.isoformat() if hs.ngay_den else None,
                  **{k: getattr(hs, k) for k in ("nong_do_con_khi_tho", "nong_do_con_mau", "toc_do_thuc_te",
                                                 "toc_do_toi_da", "dung_tich_xi_lanh", "tuoi_nguoi_lai")},
                  "su_kien": hs.su_kien, "cum_tu_loai_bo": hs.cum_tu_loai_bo},
        "nodes": sorted(nodes),
        "tra_loi": kq.tra_loi,
        "dien_dat": {"nguon": dd.nguon, "so_lan_goi": dd.so_lan_goi,
                     "hop_le": dd.kiem_tra.hop_le if dd.kiem_tra else None,
                     "loi": dd.kiem_tra.loi if dd.kiem_tra else []} if dd else None,
    }


def khoi_dong(pl) -> None:
    """Nạp trước model embedding, ontology, Java/HermiT — để độ trễ đo được là của lượt xử lý, không gồm khởi động."""
    from src.explanation.tracer import _nhan_ontology
    from src.inference.fact_inducer import danh_muc

    t0 = time.perf_counter()
    lk = pl.extractor.linker
    if getattr(lk, "embedder", None) is not None:
        lk.embedder.encode(["xe máy"])
    pl.reasoner.run([{"version": "V4", "xe": "OTo", "su_kien": {"khongChapHanhDenTinHieu": True}}])
    danh_muc()
    _nhan_ontology()
    logger.info("Khởi động xong ({:.1f}s) — bắt đầu đo", time.perf_counter() - t0)


def chay(ten: str, chi: set[str] | None = None, lam_lai: bool = False) -> Path:
    from src.kb.reasoner import TrafficReasoner
    from src.llm.client import RateLimitError

    ds = doc_kich_ban(chi)
    thu_muc = KET_QUA / ten
    thu_muc.mkdir(parents=True, exist_ok=True)
    f = thu_muc / "ket_qua.jsonl"
    xong: dict[str, dict] = {}
    if f.exists() and not lam_lai:
        for x in f.read_text(encoding="utf-8").splitlines():
            if x.strip():
                r = json.loads(x)
                if not r.get("loi"):
                    xong[r["id"]] = r
    con = [kb for kb in ds if kb["id"] not in xong]
    logger.info("[{}] {} tình huống, đã có {}, cần chạy {}", ten, len(ds), len(xong), len(con))
    if not con:
        return f
    reasoner = TrafficReasoner()
    pl = tao_pipeline(ten, reasoner, date.fromisoformat(con[0]["hom_nay"]))
    khoi_dong(pl)
    het_han_muc = 0
    for i, kb in enumerate(con, 1):
        t0 = time.perf_counter()
        try:
            r = chay_mot(pl, kb)
            het_han_muc = 0
        except RateLimitError as e:
            het_han_muc += 1
            r = {"loi": f"RateLimitError: {e}"}
        except Exception as e:  # noqa: BLE001 — ghi lỗi, chạy tiếp tình huống khác
            r = {"loi": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc(limit=3)}
        r = {"id": kb["id"], "nhom": kb["nhom"], "cau_hinh": ten, "tong_thoi_gian_s": round(time.perf_counter() - t0, 2), **r}
        xong[kb["id"]] = r
        f.write_text("".join(json.dumps(xong[k], ensure_ascii=False) + "\n"
                             for k in [x["id"] for x in doc_kich_ban()] if k in xong), encoding="utf-8")
        logger.info("[{}] {}/{} {} → {} {}", ten, i, len(con), kb["id"], r.get("trang_thai", "LỖI"),
                    [h["ma"] for h in r.get("hanh_vi", [])] if not r.get("loi") else r["loi"][:120])
        if het_han_muc >= 3:
            logger.error("[{}] LLM báo hết hạn mức 3 lần liên tiếp — dừng; chạy lại sau để tiếp tục", ten)
            break
    return f


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cau-hinh", default="day_du", choices=list(CAU_HINH))
    ap.add_argument("--chi", help="chỉ chạy các id, cách nhau dấu phẩy")
    ap.add_argument("--lam-lai", action="store_true", help="chạy lại cả tình huống đã có kết quả")
    a = ap.parse_args()
    logger.remove()
    logger.add(sys.stderr, level="INFO", filter=lambda r: r["name"].startswith("evaluation") or r["level"].no >= 30)
    chay(a.cau_hinh, set(a.chi.split(",")) if a.chi else None, a.lam_lai)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
