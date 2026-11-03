"""Sinh ``data/processed/articles_v*.jsonl`` và ``consolidation_review.md`` từ cấu hình phiên bản.

Chạy:  python -m src.ingest.build_articles

Mọi thông tin về văn bản/phiên bản lấy từ ``config/legal_sources.yaml``; thêm phiên bản mới
(V4...) chỉ cần sửa file cấu hình đó, không sửa code.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from loguru import logger

from src.config import PROCESSED_DIR, RAW_DIR, ROOT_DIR
from src.ingest.consolidate import ApplyResult, Consolidator, extract_instructions
from src.ingest.parser import ParsedDoc, make_id, parse_file

CONFIG_DIR = ROOT_DIR / "config"
SOURCES_FILE = CONFIG_DIR / "legal_sources.yaml"
OVERRIDES_FILE = CONFIG_DIR / "consolidation_overrides.yaml"

RE_FINE = re.compile(r"[Pp]hạt tiền từ ([\d.]+) đồng đến ([\d.]+) đồng")
RE_FINE_ORG = re.compile(
    r"từ ([\d.]+) đồng đến ([\d.]+) đồng đối với cá nhân,\s*từ ([\d.]+) đồng đến ([\d.]+) đồng đối với tổ chức")


def load_sources(path: Path = SOURCES_FILE) -> dict:
    """Đọc cấu hình văn bản/phiên bản."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _money(s: str) -> int:
    return int(s.replace(".", ""))


def extract_fine(lead: str) -> dict | None:
    """Trích khung phạt tiền từ đoạn mở đầu của khoản (giá trị lấy nguyên từ văn bản)."""
    if m := RE_FINE_ORG.search(lead):
        return {"ca_nhan": [_money(m.group(1)), _money(m.group(2))],
                "to_chuc": [_money(m.group(3)), _money(m.group(4))],
                "don_vi": "VND", "trich": m.group(0), "canh_cao": "cảnh cáo" in lead}
    if m := RE_FINE.search(lead):
        return {"ca_nhan": [_money(m.group(1)), _money(m.group(2))], "to_chuc": None,
                "don_vi": "VND", "trich": m.group(0), "canh_cao": "cảnh cáo" in lead}
    return None


@dataclass
class VersionBuild:
    """Kết quả dựng một phiên bản."""

    name: str
    doc: ParsedDoc
    sources: list[str]
    consolidation: list[tuple[str, list[ApplyResult]]] = field(default_factory=list)


class Builder:
    """Dựng các phiên bản pháp lý theo cấu hình."""

    def __init__(self, cfg: dict, overrides: list[dict] | None = None):
        self.cfg = cfg
        self.overrides = overrides or []
        self._parsed: dict[str, ParsedDoc] = {}
        self._built: dict[str, VersionBuild] = {}

    def parsed(self, doc_key: str) -> ParsedDoc:
        if doc_key not in self._parsed:
            meta = self.cfg["documents"][doc_key]
            self._parsed[doc_key] = parse_file(doc_key, RAW_DIR / meta["file"])
        return self._parsed[doc_key]

    def build(self, vname: str) -> VersionBuild:
        if vname in self._built:
            return self._built[vname]
        spec = self.cfg["versions"][vname]["build"]
        if "base" in spec:
            vb = VersionBuild(vname, self.parsed(spec["base"]), [spec["base"]])
        else:
            prev = self.build(spec["base_version"])
            vb = VersionBuild(vname, copy.deepcopy(prev.doc), list(prev.sources),
                              list(prev.consolidation))
        for am_key in spec.get("amendments", []):
            meta = self.cfg["documents"][am_key]
            if meta.get("amends") != vb.doc.doc:
                raise ValueError(f"{am_key} sửa {meta.get('amends')}, không phải {vb.doc.doc}")
            label = f"NĐ {meta['so_hieu']}".replace("/NĐ-CP", "")
            ad = meta["amend_dieu"]
            ad = [str(x) for x in ad] if isinstance(ad, list) else str(ad)
            instrs = extract_instructions(self.parsed(am_key), ad, label)
            c = Consolidator(vb.doc, label, self.overrides)
            vb.doc = c.run(instrs)
            vb.sources.append(am_key)
            vb.consolidation.append((am_key, c.results))
        self._built[vname] = vb
        return vb


def _overrides_map(cfg: dict, sources: list[str]) -> dict[str, dict]:
    """id phần tử → {effective_from, evidence, verified} từ element_effective_overrides.

    Chỉ lấy ngoại lệ của các văn bản nằm trong ``sources`` (nguồn hợp nhất của phiên bản);
    văn bản sau ghi đè văn bản trước.
    """
    out = {}
    for doc_key in sources:
        for o in cfg["documents"][doc_key].get("element_effective_overrides", []) or []:
            for i in o["ids"]:
                out[i] = o
    return out


def _iso(d) -> str | None:
    return d.isoformat() if isinstance(d, date) else d


def flatten(vb: VersionBuild, cfg: dict) -> list[dict]:
    """Chuyển cây văn bản của một phiên bản thành danh sách bản ghi JSONL."""
    vmeta = cfg["versions"][vb.name]
    docs = cfg["documents"]
    base_key = vb.doc.doc
    v_from, v_to = _iso(vmeta["effective_from"]), _iso(vmeta.get("effective_to"))
    eff_over = _overrides_map(cfg, vb.sources)
    records = []

    def rec(level, d, k=None, p=None) -> dict:
        uid = make_id(base_key, d.so, k.so if k else None, p.so if p else None)
        unit = p or k or d
        parent = (make_id(base_key, d.so, k.so) if p else make_id(base_key, d.so) if k else None)
        own = unit.text if level != "dieu" else (d.title + ("\n" + d.intro if d.intro else ""))
        full = [f"Điều {d.so}. {d.title}"]
        if k:
            full.append(f"{k.so}. {k.text}")
        if p:
            full.append(f"{p.so}) {p.text}")
        status = "bai_bo" if any(u.status == "bai_bo" for u in (d, k, p) if u) else "active"
        ef, note, verified = v_from, None, True
        if uid in eff_over:
            o = eff_over[uid]
            ef_o = _iso(o["effective_from"])
            ef = max(ef, ef_o) if ef_o else None
            note, verified = o["evidence"], o.get("verified", True)
            if o.get("partial"):
                note = "[Chỉ một phần nội dung] " + note
        fine = extract_fine(k.text) if k else None
        return {
            "id": uid,
            "version": vb.name,
            "doc": base_key,
            "so_hieu": docs[base_key]["so_hieu"],
            "nguon_hop_nhat": vb.sources,
            "level": level,
            "dieu": d.so,
            "khoan": k.so if k else None,
            "diem": p.so if p else None,
            "parent_id": parent,
            "chuong": d.chuong,
            "muc": d.muc,
            "dieu_title": d.title,
            "text": own,
            "full_text": "\n".join(full),
            "khung_phat": fine,
            "status": status,
            "history": unit.history,
            # Lịch sử sửa đổi cấu trúc của đơn vị cha (vd. cả khoản bị thay) áp cho đơn vị con
            "history_inherited": [h for u in (d, k) if u is not None and u is not unit
                                  for h in u.history if h.startswith(("Sửa đổi bởi", "Bổ sung bởi"))],
            "effective_from": ef,
            "effective_to": v_to,
            "effective_note": note,
            "effective_verified": verified,
        }

    for d in vb.doc.dieu:
        records.append(rec("dieu", d))
        for k in d.khoan:
            records.append(rec("khoan", d, k))
            for p in k.diem:
                records.append(rec("diem", d, k, p))
    return records


def write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    logger.info("Ghi {} bản ghi -> {}", len(records), path.relative_to(ROOT_DIR))


# ---------------------------------------------------------------------------
# Báo cáo duyệt tay
# ---------------------------------------------------------------------------


def _short(s: str, n: int = 300) -> str:
    s = s.replace("\n", " ⏎ ")
    return s if len(s) <= n else s[:n] + "…"


def write_review(builder: Builder, cfg: dict, path: Path) -> None:
    """Sinh consolidation_review.md."""
    L: list[str] = ["# Báo cáo hợp nhất văn bản — cần duyệt tay", "",
                    f"_Sinh tự động bởi `python -m src.ingest.build_articles` ngày {date.today()}. "
                    "Không sửa tay file này; ghi quyết định vào `config/consolidation_overrides.yaml`._", ""]

    # Cảnh báo parser
    L += ["## 1. Cảnh báo khi đọc văn bản nguồn", ""]
    any_w = False
    for key, pd in builder._parsed.items():
        for w in pd.warnings:
            L.append(f"- **{key}**: {w}")
            any_w = True
    if not any_w:
        L.append("- Không có.")
    L.append("")

    seen = set()
    for vname in cfg["versions"]:
        vb = builder.build(vname)
        for am_key, results in vb.consolidation:
            if am_key in seen:
                continue
            seen.add(am_key)
            meta = cfg["documents"][am_key]
            n = {s: sum(r.status == s for r in results) for s in ("applied", "header", "review", "skipped")}
            L += [f"## 2. Hợp nhất {am_key} ({meta['so_hieu']}) vào {meta['amends']} → {vname}", "",
                  f"- Tổng số dòng lệnh: {len(results)}",
                  f"- Đã tự áp: **{n['applied']}**",
                  f"- Tiêu đề nhóm (không cần áp): {n['header']}",
                  f"- Bỏ qua theo duyệt tay: {n['skipped']}",
                  f"- **Cần duyệt tay: {n['review']}**", ""]

            L += ["### 2.1. Lệnh CHƯA áp — cần duyệt tay", ""]
            reviews = [r for r in results if r.status == "review"]
            if not reviews:
                L.append("Không có.")
            for i, r in enumerate(reviews, 1):
                L += [f"**{i}. Lệnh:** `{r.instr.ref}` (đoạn {r.instr.para} trong file nguồn)", "",
                      f"> {r.instr.text}", ""]
                if r.instr.content:
                    L += [f"Nội dung trích dẫn ({len(r.instr.content)} đoạn): "
                          f"{_short(' '.join(r.instr.content))}", ""]
                L += [f"- **Lý do:** {r.detail}",
                      "- **Cách xử lý:** thêm vào `config/consolidation_overrides.yaml`:",
                      "", "```yaml",
                      f'- ref: "{r.instr.ref}"',
                      "  action: replace_all   # hoặc skip / set_text (kèm id, text)",
                      '  reviewer: ""', '  note: ""', "```", ""]

            L += ["### 2.2. Đã áp nhưng nên kiểm tra lại", "",
                  "Các lệnh *bổ sung cụm từ* được ghép tự động (có xử lý dấu câu); nên đối chiếu với nguyên văn.", ""]
            checks = [r for r in results if r.status == "applied" and r.detail.startswith("Bổ sung cụm từ")]
            for r in checks:
                L.append(f"- `{r.instr.ref}`: {r.detail} → {', '.join(r.changed_ids)}")
            if not checks:
                L.append("- Không có.")
            L.append("")

            L += ["### 2.3. Nhật ký áp đầy đủ", "", "| # | Lệnh | Thao tác | Đơn vị bị ảnh hưởng |",
                  "|---|---|---|---|"]
            for i, r in enumerate([r for r in results if r.status in ("applied", "skipped")], 1):
                L.append(f"| {i} | {r.instr.ref} | {_short(r.detail, 90).replace('|', '/')} | "
                         f"{', '.join(r.changed_ids)} |")
            L.append("")

    L += ["## 3. Hiệu lực theo từng phần tử và văn bản chưa có", ""]
    for key, meta in cfg["documents"].items():
        for o in meta.get("element_effective_overrides", []) or []:
            flag = "" if o.get("verified", True) else " **TODO_VERIFY**"
            L.append(f"- {key} {', '.join(o['ids'])}: hiệu lực từ `{o['effective_from']}`{flag} "
                     f"— _{o['evidence']}_")
    for p in cfg.get("pending_documents", []) or []:
        L.append(f"- Văn bản **{p['so_hieu']}** (sửa {p['amends']}, hiệu lực {p['effective_from']}) "
                 f"chưa có trong data/raw/. Nguồn: {p['source']}. **TODO_VERIFY**")
    L.append("")
    path.write_text("\n".join(L), encoding="utf-8")
    logger.info("Ghi báo cáo duyệt -> {}", path.relative_to(ROOT_DIR))


def main() -> None:
    import sys

    from src.config import get_settings

    logger.remove()
    logger.add(sys.stderr, level=get_settings().log_level)
    cfg = load_sources()
    ov = yaml.safe_load(OVERRIDES_FILE.read_text(encoding="utf-8")) if OVERRIDES_FILE.exists() else {}
    builder = Builder(cfg, (ov or {}).get("overrides") or [])
    for vname in cfg["versions"]:
        vb = builder.build(vname)
        write_jsonl(flatten(vb, cfg), PROCESSED_DIR / f"articles_{vname.lower()}.jsonl")
    write_review(builder, cfg, PROCESSED_DIR / "consolidation_review.md")


if __name__ == "__main__":
    main()
