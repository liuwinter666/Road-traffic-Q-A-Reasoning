"""Trích bảng tốc độ khai thác tối đa (Thông tư 38/2024) thành ``data/processed/speed_limits.json``.

Chạy:  python -m src.ingest.speed_limits

Mỗi giá trị kèm id phần tử, hàng bảng/câu nguyên văn và khoảng hiệu lực của văn bản nguồn, để
``fact_builder`` suy ra ``tocDoToiDaChoPhep`` khi người dùng không biết biển báo và để giải thích.
"""

from __future__ import annotations

import json
import re
import sys

import yaml
from loguru import logger

from src.config import PROCESSED_DIR, ROOT_DIR

MAPPING_FILE = ROOT_DIR / "config" / "speed_limits.yaml"
OUT_FILE = PROCESSED_DIR / "speed_limits.json"
RE_SPEED = re.compile(r"là (\d+) km/h")


def _records(key: str) -> dict[str, dict]:
    with (PROCESSED_DIR / f"support_{key.lower()}.jsonl").open(encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f)}


def _table_rows(text: str) -> list[list[str]]:
    return [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in text.split("\n") if ln.startswith("|")]


def resolve(spec: dict, recs: dict[str, dict]) -> dict:
    """Đọc giá trị theo đặc tả ``table`` hoặc ``text``; ném lỗi nếu không tìm thấy đúng một kết quả."""
    if "table" in spec:
        t = spec["table"]
        rows = [r for r in _table_rows(recs[t["id"]]["text"]) if t["row_phrase"] in r[0]]
        if len(rows) != 1:
            raise ValueError(f"{t}: tìm thấy {len(rows)} hàng")
        row = rows[0]
        return {"duong_doi": int(row[1]), "duong_hai_chieu": int(row[2]),
                "can_cu": {"id": t["id"], "nguyen_van": " | ".join(row)}}
    t = spec["text"]
    text = recs[t["id"]]["text"]
    sentences = [s for s in re.split(r"(?<=\.)\s", text) if t["phrase"].lower() in s.lower()]
    if len(sentences) != 1 or not (m := RE_SPEED.search(sentences[0])):
        raise ValueError(f"{t}: không trích được tốc độ")
    return {"gia_tri": int(m.group(1)), "can_cu": {"id": t["id"], "nguyen_van": sentences[0].strip()}}


def build() -> dict:
    cfg = yaml.safe_load(MAPPING_FILE.read_text(encoding="utf-8"))
    from src.ingest.build_articles import load_sources

    src_meta = load_sources()["supporting_documents"][cfg["source"]]
    recs = _records(cfg["source"])
    out = {"nguon": cfg["source"], "so_hieu": src_meta["so_hieu"],
           "hieu_luc_tu": str(src_meta["effective_from"]), "hieu_luc_den": src_meta.get("effective_to"),
           "nhom": [], "cao_toc": {}}
    for g in cfg["nhom"]:
        item = {"ten": g["ten"], "classes": g["classes"], "ghi_chu": g.get("ghi_chu")}
        for key in ("trong_khu_dong_dan_cu", "ngoai_khu_dong_dan_cu", "moi_loai_duong"):
            if key in g:
                item[key] = resolve(g[key], recs)
        out["nhom"].append(item)
    for key in ("toi_da", "toi_thieu"):
        out["cao_toc"][key] = resolve(cfg["cao_toc"][key], recs)
    out["cao_toc"]["ghi_chu"] = cfg["cao_toc"].get("ghi_chu")
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Ghi bảng tốc độ ({} nhóm xe) -> {}", len(out["nhom"]), OUT_FILE.relative_to(ROOT_DIR))
    return out


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    build()
