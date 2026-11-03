"""Kiểm chứng danh sách hành vi MVP và sinh bảng đề xuất ``docs/mvp_behaviors.md``.

Chạy:  python -m src.ingest.mvp_report

Với mỗi hành vi trong ``config/mvp_behaviors.yaml`` và mỗi phiên bản:
  * id phải tồn tại trong ``articles_v*.jsonl`` và còn hiệu lực (status = active);
  * nội dung phải chứa cụm từ kiểm chứng (``check``/``check_v3``, không phân biệt hoa thường);
  * khung phạt được TRÍCH TỪ VĂN BẢN (không nhập tay).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import yaml
from loguru import logger

from src.config import PROCESSED_DIR, ROOT_DIR

BEHAVIORS_FILE = ROOT_DIR / "config" / "mvp_behaviors.yaml"
OUT_FILE = ROOT_DIR / "docs" / "mvp_behaviors.md"
DOC_LABEL = {"ND100": "NĐ 100/2019", "ND168": "NĐ 168/2024"}


def load_articles(v: str) -> dict[str, dict]:
    path = PROCESSED_DIR / f"articles_{v.lower()}.jsonl"
    with path.open(encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f)}


def cite(r: dict) -> str:
    """Trích dẫn dạng 'điểm c khoản 6 Điều 5 NĐ 100/2019'."""
    bits = []
    if r["diem"]:
        bits.append(f"điểm {r['diem']}")
    if r["khoan"]:
        bits.append(f"khoản {r['khoan']}")
    bits.append(f"Điều {r['dieu']}")
    return " ".join(bits) + " " + DOC_LABEL.get(r["doc"], r["doc"])


def fmt_money(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def fine_str(r: dict, arts: dict[str, dict]) -> str:
    kp = r["khung_phat"]
    if kp is None and r["parent_id"] and r["level"] == "khoan":
        kp = None
    if kp:
        return f"{fmt_money(kp['ca_nhan'][0])}–{fmt_money(kp['ca_nhan'][1])}đ"
    lead = r["text"] if r["level"] == "khoan" else arts.get(r["parent_id"] or "", {}).get("text", "")
    return "Cảnh cáo" if "cảnh cáo" in lead.lower() else "TODO_VERIFY (không trích được)"


def main() -> int:
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    from src.ingest.build_articles import load_sources

    vcfg = load_sources()["versions"]
    versions = list(vcfg)
    cfg = yaml.safe_load(BEHAVIORS_FILE.read_text(encoding="utf-8"))
    arts = {v: load_articles(v) for v in versions}
    errors: list[str] = []
    rows = []
    for b in cfg["behaviors"]:
        cells = []
        fines = []
        # refs ngắn hơn số phiên bản: phiên bản sau kế thừa id của phiên bản trước (vẫn kiểm chứng)
        refs = list(b["refs"]) + [b["refs"][-1]] * (len(versions) - len(b["refs"]))
        for v, rid in zip(versions, refs):
            if rid is None:
                cells.append("— _không có_")
                fines.append(None)
                continue
            r = arts[v].get(rid)
            if r is None:
                errors.append(f"{b['code']} {v}: không tồn tại id {rid}")
                cells.append(f"**LỖI** `{rid}`")
                fines.append(None)
                continue
            if r["status"] != "active":
                errors.append(f"{b['code']} {v}: {rid} có trạng thái {r['status']}")
            phrase = b.get(f"check_{v.lower()}") or (b.get("check_v3") if versions.index(v) >= versions.index("V3") else None) or b["check"]
            if phrase.lower() not in r["full_text"].lower():
                errors.append(f"{b['code']} {v}: {rid} không chứa cụm '{phrase}'")
            f = fine_str(r, arts[v])
            fines.append(f)
            flag = "" if r["history"] or r["history_inherited"] else ""
            if v != versions[0] and v != "V3" and (r["history"] or r["history_inherited"]):
                flag = " ✎"
            cells.append(f"{cite(r)}{flag}<br>`{rid}`<br>**{f}**")
        changes = []
        for (va, fa, ca), (vb_, fb, cb) in zip(zip(versions, fines, cells), zip(versions[1:], fines[1:], cells[1:])):
            if fa and fb and fa != fb:
                changes.append(f"{va}→{vb_} đổi mức")
            elif (fa is None) != (fb is None):
                changes.append(f"{va}/{vb_} khác phạm vi")
            elif fa and fb and "✎" in cb and va != "V2":
                changes.append(f"{vb_} sửa nội dung")
        note = "; ".join(changes + ([b["note"]] if b.get("note") else []))
        rows.append((b, cells, note))

    L = ["# Đề xuất danh sách hành vi MVP (chờ duyệt)", "",
         f"_Sinh tự động bởi `python -m src.ingest.mvp_report` ngày {date.today()} từ "
         "`config/mvp_behaviors.yaml` + `data/processed/articles_v*.jsonl`. "
         "Mức phạt được trích tự động từ đoạn mở đầu của khoản; ✎ = phần tử bị văn bản sửa đổi "
         "(NĐ 123 ở V2, NĐ 238 ở V4) thay đổi._", "",
         f"Tổng số hành vi: **{len(rows)}**. Lỗi kiểm chứng: **{len(errors)}**.", ""]
    if errors:
        L += ["## Lỗi kiểm chứng", ""] + [f"- {e}" for e in errors] + [""]
    groups: dict[str, list] = {}
    for row in rows:
        groups.setdefault(row[0]["nhom"], []).append(row)
    for g, items in groups.items():
        heads = [f"{v} ({vcfg[v]['effective_from']} → {vcfg[v].get('effective_to') or 'nay'})" for v in versions]
        L += [f"## Nhóm `{g}`", "", "| Mã | Hành vi | " + " | ".join(heads) + " | Ghi chú |",
              "|" + "---|" * (len(versions) + 3)]
        for b, cells, note in items:
            L.append(f"| `{b['code']}` | {b['ten']} | " + " | ".join(cells) + f" | {note} |")
        L.append("")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text("\n".join(L), encoding="utf-8")
    logger.info("{} hành vi, {} lỗi -> {}", len(rows), len(errors), OUT_FILE.relative_to(ROOT_DIR))
    for e in errors:
        logger.error(e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
