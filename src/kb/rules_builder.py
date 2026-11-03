"""Sinh luật SWRL và sổ đăng ký luật từ đặc tả.

Chạy:  python -m src.kb.rules_builder

Đầu vào: config/rule_specs.yaml (điều kiện), config/mvp_behaviors.yaml (điều khoản theo phiên bản),
config/ontology_concepts.yaml (tình tiết), data/processed/*.jsonl (nguyên văn, khung phạt, chế tài).
Đầu ra:  ontology/rules/{alcohol,speed,signal,resistance,documents,penalty_decision}.swrl
         ontology/rule_registry.yaml

Mỗi luật có mã R001...; mã đó xuất hiện trong kết luận `duocSuyRaBoi(?h, Rxxx)` và lớp đánh dấu `QT_Rxxx(?h)`
(reasoner đọc lớp đánh dấu để truy vết — rẻ hơn suy luận mọi giá trị thuộc tính), và trong sổ đăng ký kèm
nghị định, điều, khoản, điểm, trích nguyên văn, ngày hiệu lực. Không có số liệu pháp lý nào nhập tay ở đây.
"""

from __future__ import annotations

import itertools
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml
from loguru import logger

from src.config import ONTOLOGY_DIR, PROCESSED_DIR, ROOT_DIR, RULES_DIR
from src.kb.sanctions import applies_to, extract_all

SPECS_FILE = ROOT_DIR / "config" / "rule_specs.yaml"
BEHAVIORS_FILE = ROOT_DIR / "config" / "mvp_behaviors.yaml"
CONCEPTS_FILE = ROOT_DIR / "config" / "ontology_concepts.yaml"
REGISTRY_FILE = ONTOLOGY_DIR / "rule_registry.yaml"
FILE_ORDER = ["alcohol", "speed", "signal", "resistance", "documents", "penalty_decision"]
DOC_LABEL = {"ND100": "NĐ 100/2019/NĐ-CP", "ND168": "NĐ 168/2024/NĐ-CP"}
VPHC_ONE_ACT = "LXLVPHC-D3-K1-d"   # "Một hành vi vi phạm hành chính chỉ bị xử phạt một lần."


def _load_jsonl(name: str) -> dict[str, dict]:
    with (PROCESSED_DIR / f"{name}.jsonl").open(encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f)}


def _alts(x) -> list[list[str]]:
    """Chuẩn hóa danh sách phương án: 'A' → [['A']]; ['A', ['B','C']] → [['A'], ['B','C']]."""
    if not x:
        return [[]]
    return [[a] if isinstance(a, str) else list(a) for a in x]


def _spec_for(spec: dict, version: str) -> dict:
    out = {k: v for k, v in spec.items() if k != "phien_ban"}
    for keys, ov in (spec.get("phien_ban") or {}).items():
        if version in [k.strip() for k in str(keys).split(",")]:
            out.update(ov)
    return out


def _cite(r: dict) -> str:
    bits = ([f"điểm {r['diem']}"] if r["diem"] else []) + ([f"khoản {r['khoan']}"] if r["khoan"] else [])
    return " ".join(bits + [f"Điều {r['dieu']}"])


def _provision_block(r: dict, version: str) -> dict:
    return {
        "id": r["id"], "iri": f"{version}_{r['id']}", "van_ban": DOC_LABEL.get(r["doc"], r["doc"]),
        "dieu": r["dieu"], "khoan": r["khoan"], "diem": r["diem"],
        "trich_dan": f"{_cite(r)} {DOC_LABEL.get(r['doc'], r['doc'])}",
        "nguyen_van": r["full_text"], "hieu_luc_tu": r["effective_from"], "hieu_luc_den": r["effective_to"],
        "duoc_sua_doi": bool(r["history"] or r["history_inherited"]),
    }


def _fine(r: dict, recs: dict[str, dict]) -> tuple[dict | None, bool]:
    """(khung phạt cá nhân, có phải phạt cảnh cáo) của phần tử — lấy từ khoản chứa nó."""
    k = r if r["level"] == "khoan" else recs.get(r["parent_id"] or "")
    lead = (k or {}).get("text", "")
    kp = (k or {}).get("khung_phat")
    return ({"min": kp["ca_nhan"][0], "max": kp["ca_nhan"][1], "don_vi": "VND", "trich": kp["trich"]} if kp
            else None), "cảnh cáo" in lead.lower()


def _exclusion_reason(r: dict) -> dict:
    m = re.search(r"trừ (?:các )?hành vi vi phạm quy định tại [^;.]+", r["text"])
    if m:
        return {"loai": "trich_dan", "nguyen_van": m.group(0)}
    return {"loai": "nguyen_tac", "id": VPHC_ONE_ACT,
            "nguyen_van": "Một hành vi vi phạm hành chính chỉ bị xử phạt một lần."}


def build() -> dict:
    from src.ingest.build_articles import load_sources
    from src.kb.temporal import chon_van_ban_bo_tro

    sources = load_sources()
    versions = list(sources["versions"])
    specs = yaml.safe_load(SPECS_FILE.read_text(encoding="utf-8"))
    behaviors = yaml.safe_load(BEHAVIORS_FILE.read_text(encoding="utf-8"))["behaviors"]
    concepts = yaml.safe_load(CONCEPTS_FILE.read_text(encoding="utf-8"))
    recs = {v: _load_jsonl(f"articles_{v.lower()}") for v in versions}

    # Chế tài theo phiên bản (chỉ các Điều được hành vi MVP dẫn tới)
    sanctions = {}
    for i, v in enumerate(versions):
        dieus = set()
        for b in behaviors:
            refs = list(b["refs"]) + [b["refs"][-1]] * (len(versions) - len(b["refs"]))
            if refs[i]:
                dieus.add(recs[v][refs[i]]["dieu"])
        sanctions[v] = extract_all(recs[v], dieus)

    rules: dict[str, dict] = {}
    lines: dict[str, list[str]] = {f: [] for f in FILE_ORDER}
    hanh_vi: dict[str, dict] = {}
    counter = itertools.count(1)

    def new_id(prefix="R"):
        return f"{prefix}{next(counter):03d}"

    for f in FILE_ORDER[:-1]:
        for b in behaviors:
            if specs["files"][b["nhom"]] != f:
                continue
            code, spec0 = b["code"], specs["specs"][b["code"]]
            refs = list(b["refs"]) + [b["refs"][-1]] * (len(versions) - len(b["refs"]))
            for v, rid in zip(versions, refs):
                if not rid:
                    continue
                spec = _spec_for(spec0, v)
                r = recs[v][rid]
                prov = _provision_block(r, v)
                fine, canh_cao = _fine(r, recs[v])
                parts = (r["dieu"], r["khoan"], r["diem"])
                hv_sanctions = [s.to_dict() for s in sanctions[v] if applies_to(s, parts)]
                act = spec.get("act", "HanhViDieuKhienXe")
                ids = []
                for xe, dk, ng in itertools.product(_alts(spec.get("xe")), _alts(spec.get("dk")), _alts(spec.get("nguoi"))):
                    qid = new_id()
                    body = [f"{act}(?h)", "thuocVuViec(?h, ?v)", f"apDungPhienBan(?v, {v})", "chuThe(?h, ?n)",
                            "suDungPhuongTien(?h, ?x)"]
                    body += [f"{c}(?x)" for c in xe] + [f"{c}(?h)" for c in dk] + [f"{c}(?n)" for c in ng]
                    body += list(spec.get("extra") or [])
                    head = [f"HV_{code}(?h)", f"QT_{qid}(?h)", f"apDungDieuKhoan(?h, {prov['iri']})",
                            f"duocSuyRaBoi(?h, {qid})", "viPhamHanhVi(?n, ?h)"]
                    swrl = ", ".join(body) + " -> " + ", ".join(head)
                    rules[qid] = {"loai": "hanh_vi", "ma_hanh_vi": code, "phien_ban": v, "tep": f,
                                  "mo_ta": b["ten"], "can_cu": prov, "swrl": swrl}
                    lines[f].append(f"# {qid} | {code} | {v} | {prov['trich_dan']}\n{qid}: {swrl}")
                    ids.append(qid)
                excl = [{"ma_hanh_vi": c, "can_cu": _exclusion_reason(r)} for c in spec.get("loai_tru_boi") or []]
                hanh_vi.setdefault(code, {"ten": b["ten"], "nhom": b["nhom"], "phien_ban": {}})
                hanh_vi[code]["phien_ban"][v] = {
                    "quy_tac": ids, "can_cu": prov, "khung_phat": fine, "canh_cao": canh_cao,
                    "che_tai": hv_sanctions, "loai_tru_boi": excl,
                }

    # Luật suy ra "người không đủ điều kiện điều khiển xe"
    dk = specs["dieu_kien_nguoi_lai"]
    for keys, ids in dk["can_cu"].items():
        for v in [k.strip() for k in keys.split(",")]:
            start = date.fromisoformat(str(sources["versions"][v]["effective_from"]))
            can_cu = []
            for sid in ids:
                doc = sid.split("-")[0]
                out_key = doc if doc != "LTTATGT" else chon_van_ban_bo_tro("dieu_kien_nguoi_lai", start).khoa
                sr = _load_jsonl(f"support_{out_key.lower()}")[sid]
                iri = sid if out_key == doc else f"{out_key}_{sid}"
                can_cu.append({"id": sid, "iri": iri, "van_ban": out_key, "nguyen_van": sr["full_text"],
                               "hieu_luc_tu": sr["effective_from"], "hieu_luc_den": sr["effective_to"]})
            heads = "NguoiKhongDuDieuKienDieuKhienXe(?n), QT_{q}(?n), duocSuyRaBoi(?n, {q})"
            bodies = [f"HanhViDieuKhienXe(?h), thuocVuViec(?h, ?v), apDungPhienBan(?v, {v}), chuThe(?h, ?n), HV_{c}(?h)"
                      for c in dk["tu_hanh_vi"]]
            bodies += [f"HanhViDieuKhienXe(?h), thuocVuViec(?h, ?v), apDungPhienBan(?v, {v}), chuThe(?h, ?n), "
                       f"{dk['chua_du_14_tuoi']['nguoi']}(?n), suDungPhuongTien(?h, ?x), {x}(?x)"
                       for x in dk["chua_du_14_tuoi"]["xe"]]
            for body in bodies:
                qid = new_id()
                swrl = f"{body} -> {heads.format(q=qid)}"
                rules[qid] = {"loai": "dieu_kien_nguoi_lai", "phien_ban": v, "tep": "documents",
                              "mo_ta": "Suy ra người không đủ điều kiện điều khiển xe", "can_cu": can_cu, "swrl": swrl}
                lines["documents"].append(f"# {qid} | ĐIỀU KIỆN NGƯỜI LÁI | {v} | {', '.join(ids)}\n{qid}: {swrl}")

    # Luật tình tiết (Luật XLVPHC, không phụ thuộc phiên bản nghị định)
    vphc = _load_jsonl("support_lxlvphc")
    for tf in concepts.get("tinh_tiet_facts") or []:
        qid = new_id()
        code = tf["tinh_tiet"]
        sid = "LXLVPHC-D9-K" + code.split("_")[1] if code.startswith("TTGN") else \
            "LXLVPHC-D10-K1-" + code.split("_")[1]
        swrl = f"HanhVi(?h), DH_{tf['fact']}(?h) -> QT_{qid}(?h), coTinhTiet(?h, {code}), duocSuyRaBoi(?h, {qid})"
        rules[qid] = {"loai": "tinh_tiet", "tinh_tiet": code, "su_kien": tf["fact"], "tep": "penalty_decision",
                      "mo_ta": tf["label"], "swrl": swrl,
                      "can_cu": {"id": sid, "nguyen_van": vphc[sid]["full_text"],
                                 "hieu_luc_tu": vphc[sid]["effective_from"]}}
        lines["penalty_decision"].append(f"# {qid} | TÌNH TIẾT {code} | {tf['label']}\n{qid}: {swrl}")

    RULES_DIR.mkdir(parents=True, exist_ok=True)
    header = ("# Sinh tự động bởi `python -m src.kb.rules_builder` từ config/rule_specs.yaml — không sửa tay.\n"
              "# Mỗi luật: dòng chú thích '# <mã> | <hành vi> | <phiên bản> | <căn cứ>' rồi '<mã>: <SWRL>'.\n"
              "# Căn cứ đầy đủ, nguyên văn, ngày hiệu lực: ontology/rule_registry.yaml.\n\n")
    for f in FILE_ORDER:
        (RULES_DIR / f"{f}.swrl").write_text(header + "\n\n".join(lines[f]) + "\n", encoding="utf-8")
    registry = {
        "meta": {"sinh_ngay": str(date.today()), "so_quy_tac": len(rules), "reasoner": "HermiT (xem docs)",
                 "ghi_chu": "Không sửa tay — sửa config/rule_specs.yaml hoặc config/mvp_behaviors.yaml rồi sinh lại."},
        "quy_tac": rules,
        "hanh_vi": hanh_vi,
    }
    REGISTRY_FILE.write_text(yaml.safe_dump(registry, allow_unicode=True, sort_keys=False, width=200),
                             encoding="utf-8")
    by_type = {}
    for q in rules.values():
        by_type[q["loai"]] = by_type.get(q["loai"], 0) + 1
    logger.info("Sinh {} luật {} -> {}", len(rules), by_type, REGISTRY_FILE.relative_to(ROOT_DIR))
    return registry


def load_registry(path: Path = REGISTRY_FILE) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_swrl_files(directory: Path = RULES_DIR) -> dict[str, str]:
    """{mã luật: SWRL} từ các file .swrl."""
    out = {}
    for p in sorted(directory.glob("*.swrl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if m := re.match(r"^(R\d+): (.+)$", line):
                out[m.group(1)] = m.group(2)
    return out


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    build()
