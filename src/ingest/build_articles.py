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
            meta = self.cfg["documents"].get(doc_key) or self.cfg["supporting_documents"][doc_key]
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


def _effectivity_map(cfg: dict, sources: list[str], section: str = "documents") -> dict[str, list[dict]]:
    """id phần tử → danh sách mục ``element_effectivity`` (theo thứ tự văn bản trong ``sources``).

    Chỉ lấy hiệu lực riêng do các văn bản nằm trong ``sources`` đặt ra (vd. ngoại lệ của NĐ 238
    chỉ áp cho V4), nên phiên bản cũ không bị gán nhầm ngày của văn bản sau.
    """
    out: dict[str, list[dict]] = {}
    for doc_key in sources:
        meta = cfg.get(section, {}).get(doc_key) or cfg["documents"].get(doc_key) or {}
        for o in meta.get("element_effectivity", []) or []:
            for i in o["ids"]:
                out.setdefault(i, []).append(o)
    return out


def _iso(d) -> str | None:
    return d.isoformat() if isinstance(d, date) else d


def build_segments(v_from: str | None, v_to: str | None, entries: list[dict]) -> dict:
    """Dựng mô hình hiệu lực của một phần tử từ khoảng hiệu lực mặc định và các mục element_effectivity.

    Trả về dict gồm ``effective_from`` (ngày có hiệu lực của phần nội dung chính, None nếu chưa xác
    định), ``hieu_luc_dieu_kien`` (điều kiện phụ thuộc văn bản khác của toàn bộ phần tử) và
    ``hieu_luc_chi_tiet`` — danh sách đoạn hiệu lực, mỗi đoạn ứng với toàn bộ hoặc một phần nội dung.
    """
    segs = [{"pham_vi": "toan_bo", "mo_ta_pham_vi": None, "tu": v_from, "den": v_to,
             "hieu_luc_dieu_kien": None, "dieu_kien_da_dap_ung": None, "can_cu": None, "verified": True}]
    for o in entries:
        ef = _iso(o.get("effective_from"))
        tu = (max(v_from, ef) if v_from else ef) if ef else None
        seg = {"tu": tu, "den": v_to, "hieu_luc_dieu_kien": o.get("hieu_luc_dieu_kien"),
               "dieu_kien_da_dap_ung": o.get("dieu_kien_da_dap_ung") if o.get("hieu_luc_dieu_kien") else None,
               "can_cu": o["evidence"], "verified": o.get("verified", True)}
        if o.get("pham_vi", "toan_bo") == "toan_bo":
            segs = [{"pham_vi": "toan_bo", "mo_ta_pham_vi": None, **seg}]
        else:
            for x in segs:
                if x["pham_vi"] == "toan_bo":
                    x["pham_vi"] = "phan_con_lai"
                    x["mo_ta_pham_vi"] = "Phần nội dung còn lại"
            segs.append({"pham_vi": "mot_phan", "mo_ta_pham_vi": o.get("mo_ta_pham_vi"), **seg})
    main = next((x for x in segs if x["pham_vi"] in ("toan_bo", "phan_con_lai")), segs[0])
    return {
        "effective_from": main["tu"],
        "effective_to": v_to,
        "hieu_luc_dieu_kien": main["hieu_luc_dieu_kien"],
        "hieu_luc_mot_phan": any(x["pham_vi"] == "mot_phan" for x in segs),
        "hieu_luc_chi_tiet": segs,
        "effective_verified": all(x["verified"] for x in segs),
        "effective_note": "; ".join(x["can_cu"] for x in segs if x["can_cu"]) or None,
    }


# ---------------- Chú thích văn bản hợp nhất ----------------

RE_FN_DATE = re.compile(r"có hiệu lực (?:thi hành )?(?:kể )?từ ngày (\d{1,2}) tháng (\d{1,2}) năm (\d{4})")
RE_FN_LAW = re.compile(r"(Luật[^,;]*? số \d+/\d{4}/QH\d+)")


def classify_footnote(text: str) -> dict:
    """Phân loại chú thích của văn bản hợp nhất và trích văn bản sửa đổi, ngày hiệu lực."""
    first = text.split("\n")[0]
    if "được bãi bỏ" in first:
        loai = "bai_bo"
    elif re.match(r"^(Khoản|Điểm|Điều|Đoạn|Mục|Chương|Tên điều|Tên)\b", first) and "được bổ sung" in first \
            and "sửa đổi" not in first:
        loai = "bo_sung_don_vi"
    elif re.match(r"^(Khoản|Điểm|Điều|Đoạn|Mục|Chương|Tên điều|Tên)\b", first):
        loai = "sua_doi_don_vi"
    elif first.startswith(("Cụm từ", "Từ ")):
        loai = "cum_tu"
    else:
        loai = "khac"
    m = RE_FN_DATE.search(first)
    law = RE_FN_LAW.search(first)
    return {"loai": loai, "hieu_luc_tu": f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None,
            "van_ban": law.group(1) if law else None, "noi_dung": first}


STRUCTURAL = ("sua_doi_don_vi", "bo_sung_don_vi", "bai_bo")


# ---------------- Làm phẳng cây văn bản ----------------


def flatten_doc(doc: ParsedDoc, *, version: str | None, so_hieu: str, sources: list[str],
                v_from: str | None, v_to: str | None, eff_map: dict[str, list[dict]]) -> list[dict]:
    """Chuyển cây văn bản thành danh sách bản ghi JSONL (dùng chung cho phiên bản và văn bản bổ trợ)."""
    base_key = doc.doc
    fn = {n: classify_footnote(t) for n, t in doc.footnotes.items()}
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
        eff = build_segments(v_from, v_to, eff_map.get(uid, []))
        # Chú thích của văn bản hợp nhất: câu chữ hiện hành có hiệu lực từ ngày của văn bản sửa đổi
        notes = [dict(chu_thich=n, **fn[n]) for n in unit.notes if n in fn]
        notes += [dict(chu_thich=n, ke_thua=True, **fn[n]) for u in (d, k) if u is not None and u is not unit
                  for n in u.notes if n in fn and fn[n]["loai"] in STRUCTURAL]
        dated = [x for x in notes if x["hieu_luc_tu"] and x["loai"] != "khac"]
        if dated:
            last = max(dated, key=lambda x: x["hieu_luc_tu"])
            if any(x["loai"] == "bai_bo" for x in dated):
                status = "bai_bo"
                eff["bai_bo_tu"] = max(x["hieu_luc_tu"] for x in dated if x["loai"] == "bai_bo")
                eff["noi_dung_truoc_do"] = ("Không có trong dữ liệu — văn bản hợp nhất chỉ ghi '(được bãi bỏ)'; "
                                           f"nội dung áp dụng trước {eff['bai_bo_tu']} không có.")
            elif eff["effective_from"] and last["hieu_luc_tu"] > eff["effective_from"]:
                eff["effective_from"] = last["hieu_luc_tu"]
                eff["hieu_luc_chi_tiet"][0]["tu"] = last["hieu_luc_tu"]
                eff["hieu_luc_chi_tiet"][0]["can_cu"] = (
                    f"Chú thích [{last['chu_thich']}] văn bản hợp nhất: {last['noi_dung']}")
                eff["noi_dung_truoc_do"] = ("Không có trong dữ liệu — văn bản hợp nhất chỉ chứa câu chữ hiện hành; "
                                           f"câu chữ áp dụng trước {last['hieu_luc_tu']} có thể khác.")
        fine = extract_fine(k.text) if k else None
        return {
            "id": uid,
            "version": version,
            "doc": base_key,
            "so_hieu": so_hieu,
            "nguon_hop_nhat": sources,
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
            "chu_thich": notes,
            **eff,
        }

    for d in doc.dieu:
        records.append(rec("dieu", d))
        for k in d.khoan:
            records.append(rec("khoan", d, k))
            for p in k.diem:
                records.append(rec("diem", d, k, p))
    return records


def flatten(vb: VersionBuild, cfg: dict) -> list[dict]:
    """Bản ghi JSONL của một phiên bản nghị định."""
    vmeta = cfg["versions"][vb.name]
    return flatten_doc(vb.doc, version=vb.name, so_hieu=cfg["documents"][vb.doc.doc]["so_hieu"],
                       sources=vb.sources, v_from=_iso(vmeta["effective_from"]),
                       v_to=_iso(vmeta.get("effective_to")), eff_map=_effectivity_map(cfg, vb.sources))


def flatten_support(key: str, cfg: dict, doc: ParsedDoc) -> list[dict]:
    """Bản ghi JSONL của một văn bản bổ trợ (luật, thông tư)."""
    meta = cfg["supporting_documents"][key]
    return flatten_doc(doc, version=None, so_hieu=meta["so_hieu"], sources=[key],
                       v_from=_iso(meta["effective_from"]), v_to=_iso(meta.get("effective_to")),
                       eff_map=_effectivity_map(cfg, [key], "supporting_documents"))


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

    L += ["## 3. Hiệu lực riêng theo phần tử / phần nội dung", ""]
    for sec in ("documents", "supporting_documents"):
        for key, meta in (cfg.get(sec) or {}).items():
            for o in meta.get("element_effectivity", []) or []:
                flag = "" if o.get("verified", True) else " **TODO_VERIFY**"
                pv = "một phần nội dung" if o.get("pham_vi") == "mot_phan" else "toàn bộ"
                cond = f"; **có điều kiện**: {o['hieu_luc_dieu_kien']}" if o.get("hieu_luc_dieu_kien") else ""
                L.append(f"- {key} {', '.join(o['ids'])} ({pv}): từ `{o['effective_from'] or 'chưa xác định'}`{cond}{flag}")
    L.append("")
    L += ["## 4. Văn bản bổ trợ và văn bản được thay thế nhưng chưa có", ""]
    for key, meta in (cfg.get("supporting_documents") or {}).items():
        L.append(f"- **{key}** ({meta['so_hieu']}): hiệu lực từ {meta['effective_from']}. {meta.get('vai_tro', '')}")
        if meta.get("thay_the"):
            L.append(f"  - Thay thế: {meta['thay_the']}")
        for x in meta.get("sua_doi_chua_co") or []:
            L.append(f"  - Sửa đổi chưa có: {x} **TODO_VERIFY**")
    for p in cfg.get("pending_documents", []) or []:
        L.append(f"- Văn bản **{p['so_hieu']}** chưa có trong data/raw/. **TODO_VERIFY**")
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
    for key in cfg.get("supporting_documents") or {}:
        write_jsonl(flatten_support(key, cfg, builder.parsed(key)),
                    PROCESSED_DIR / f"support_{key.lower()}.jsonl")
    write_review(builder, cfg, PROCESSED_DIR / "consolidation_review.md")


if __name__ == "__main__":
    main()
