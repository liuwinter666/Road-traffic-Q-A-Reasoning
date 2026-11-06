"""Baseline: LLM trả lời trực tiếp, không ontology / luật SWRL / văn bản đính kèm (mục 10 đặc tả).

    python -m evaluation.baseline_llm_only [--chi S01,S02] [--lam-lai]

Mỗi tình huống: lượt 1 chỉ có lời kể đầu (đo "hỏi lại đúng lúc"); nếu tình huống có câu trả lời bổ sung thì lượt 2
gửi lời kể + mọi câu trả lời (như thể người dùng đã kể đủ) để lấy kết luận. Đầu ra có cấu trúc (văn bản, điều, khoản,
điểm, khung phạt) được quy về id điều khoản (vd. ND168-D7-K8-b) để chấm cùng bộ metric với hệ thống.
Kết quả: evaluation/results/baseline_llm/ket_qua.jsonl.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from datetime import date

from loguru import logger
from pydantic import BaseModel, Field

from evaluation.run_eval import KET_QUA, doc_kich_ban

TEN = "baseline_llm"


class HanhViBaseline(BaseModel):
    mo_ta: str = Field(description="Tên hành vi vi phạm")
    van_ban: str = Field(description="Số hiệu nghị định áp dụng, vd. 'Nghị định 168/2024/NĐ-CP'")
    dieu: int
    khoan: int | None = None
    diem: str | None = Field(None, description="Chữ cái của điểm, vd. 'a', 'đ'")
    phat_tien_tu: int | None = Field(None, description="Mức phạt tiền tối thiểu (đồng)")
    phat_tien_den: int | None = Field(None, description="Mức phạt tiền tối đa (đồng)")
    hinh_thuc_bo_sung: list[str] = Field(default_factory=list)


class TraLoiBaseline(BaseModel):
    can_hoi_them: bool = False
    cau_hoi: list[str] = Field(default_factory=list)
    hanh_vi: list[HanhViBaseline] = Field(default_factory=list)
    tra_loi: str = ""


def id_dieu_khoan(h: HanhViBaseline) -> str | None:
    """'Nghị định 168/2024/NĐ-CP', Điều 7, khoản 8, điểm b → ND168-D7-K8-b."""
    m = re.search(r"(\d{2,3})\s*/\s*\d{4}", h.van_ban) or re.search(r"(\d{2,3})", h.van_ban)
    if not m:
        return None
    s = f"ND{m.group(1)}-D{h.dieu}"
    if h.khoan:
        s += f"-K{h.khoan}"
    if h.diem:
        d = h.diem.strip().lower().replace("điểm", "").strip().rstrip(")")
        s += "-" + d.replace("đ", "dd")
    return s


def chay(chi: set[str] | None = None, lam_lai: bool = False):
    from src.llm.client import RateLimitError, get_llm_client
    from src.llm.prompts import load_prompt

    client = get_llm_client()
    pr = load_prompt("baseline")
    thu_muc = KET_QUA / TEN
    thu_muc.mkdir(parents=True, exist_ok=True)
    f = thu_muc / "ket_qua.jsonl"
    xong: dict[str, dict] = {}
    if f.exists() and not lam_lai:
        for x in f.read_text(encoding="utf-8").splitlines():
            if x.strip() and not (r := json.loads(x)).get("loi"):
                xong[r["id"]] = r
    ds = [kb for kb in doc_kich_ban(chi) if kb["id"] not in xong]
    logger.info("[{}] cần chạy {} tình huống (đã có {})", TEN, len(ds), len(xong))
    het = 0
    for i, kb in enumerate(ds, 1):
        hom_nay = date.fromisoformat(kb["hom_nay"]).strftime("%d/%m/%Y")
        t_tong = time.perf_counter()
        try:
            luot = []

            def goi(loi_ke: str) -> TraLoiBaseline:
                t0 = time.perf_counter()
                out = client.generate_structured(pr.render(loi_ke=loi_ke), TraLoiBaseline,
                                                 system=pr.system.format(hom_nay=hom_nay))
                luot.append({"hoi": ["_"] if out.can_hoi_them else [], "thoi_gian_s": round(time.perf_counter() - t0, 3)})
                return out
            dau = goi(kb["luot"][0])
            cuoi = dau
            if kb["tra_loi"]:
                cuoi = goi("\n".join([kb["luot"][0], *dict.fromkeys(kb["tra_loi"].values())]))
            hv = []
            for h in cuoi.hanh_vi:
                hv.append({"id": id_dieu_khoan(h), "trich_dan": f"{h.diem or ''} {h.khoan or ''} Điều {h.dieu} {h.van_ban}",
                           "khung_phat": [h.phat_tien_tu, h.phat_tien_den] if h.phat_tien_tu is not None else None,
                           "mo_ta": h.mo_ta})
            r = {"can_hoi_luot_dau": dau.can_hoi_them, "luot": luot, "phien_ban": None,
                 "trang_thai": "ket_luan" if hv else "khong_phat_hien", "hanh_vi": hv, "tra_loi": cuoi.tra_loi}
            het = 0
        except RateLimitError as e:
            het += 1
            r = {"loi": f"RateLimitError: {e}"}
        except Exception as e:  # noqa: BLE001
            r = {"loi": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc(limit=3)}
        xong[kb["id"]] = {"id": kb["id"], "nhom": kb["nhom"], "cau_hinh": TEN,
                          "tong_thoi_gian_s": round(time.perf_counter() - t_tong, 2), **r}
        f.write_text("".join(json.dumps(xong[k], ensure_ascii=False) + "\n"
                             for k in [x["id"] for x in doc_kich_ban()] if k in xong), encoding="utf-8")
        logger.info("[{}] {}/{} {} → {}", TEN, i, len(ds), kb["id"],
                    [h["id"] for h in r.get("hanh_vi", [])] if not r.get("loi") else r["loi"][:120])
        if het >= 3:
            logger.error("[{}] hết hạn mức LLM — dừng; chạy lại sau để tiếp tục", TEN)
            break
    return f


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--chi")
    ap.add_argument("--lam-lai", action="store_true")
    a = ap.parse_args()
    logger.remove()
    logger.add(sys.stderr, level="INFO", filter=lambda r: r["name"].startswith("evaluation") or r["level"].no >= 30)
    chay(set(a.chi.split(",")) if a.chi else None, a.lam_lai)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
