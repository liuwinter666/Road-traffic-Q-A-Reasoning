"""Sinh data/test/scenarios.jsonl từ data/test/scenarios_src.yaml (nguồn do người gán nhãn).

    python -m evaluation.sinh_nhan

Người gán nhãn chỉ ghi: mã hành vi vi phạm + phiên bản pháp lý (+ trường trích xuất, sự kiện, câu hỏi kỳ vọng).
Script bổ sung, KHÔNG gõ tay số liệu pháp lý:
  * ``dieu_khoan``: id điều/khoản/điểm, cách viết căn cứ, khung phạt của từng hành vi ở đúng phiên bản — tra từ
    ontology/rule_registry.yaml (bảng hành vi ↔ điều khoản đã kiểm chứng với văn bản trong data/raw ở Phase 1/3).
  * ``nodes``: lớp dấu hiệu kỳ vọng (từ điều kiện của luật trong config/rule_specs.yaml) — để đo ánh xạ node.
và kiểm tra: mã hành vi có ở phiên bản đó, khóa câu hỏi có trong config/slots.yaml, sự kiện có trong ontology.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from src.config import ROOT_DIR

NGUON = ROOT_DIR / "data" / "test" / "scenarios_src.yaml"
DICH = ROOT_DIR / "data" / "test" / "scenarios.jsonl"
NHOM = {"don_loi", "da_loi", "gian_tiep", "thieu_thong_tin", "khac_thoi_diem", "khong_vi_pham"}


def _dk_luat(spec: dict, v: str) -> list:
    """Điều kiện (danh sách phương án) của luật ở phiên bản ``v`` (áp ghi đè ``phien_ban``)."""
    dk = spec.get("dk") or []
    for khoa, ghi_de in (spec.get("phien_ban") or {}).items():
        if v in [x.strip() for x in str(khoa).split(",")] and "dk" in ghi_de:
            dk = ghi_de["dk"]
    return dk


def nodes_ky_vong(ma: str, v: str, specs: dict, quan_sat: set[str]) -> list[str]:
    """Lớp dấu hiệu (observation) bắt buộc — chỉ khi luật có MỘT phương án điều kiện (không mơ hồ)."""
    dk = _dk_luat(specs.get(ma, {}), v)
    if len(dk) != 1:
        return []
    pa = dk[0] if isinstance(dk[0], list) else [dk[0]]
    return [c for c in pa if c in quan_sat]


def main() -> int:
    from src.inference.fact_inducer import danh_muc
    from src.kb.rules_builder import load_registry

    src = yaml.safe_load(NGUON.read_text(encoding="utf-8"))
    reg = load_registry()["hanh_vi"]
    specs = yaml.safe_load((ROOT_DIR / "config" / "rule_specs.yaml").read_text(encoding="utf-8"))["specs"]
    cc = yaml.safe_load((ROOT_DIR / "config" / "ontology_concepts.yaml").read_text(encoding="utf-8"))
    quan_sat = {o["name"] for o in cc["observations"]}
    slot_keys = set(yaml.safe_load((ROOT_DIR / "config" / "slots.yaml").read_text(encoding="utf-8"))["cau_hoi"])
    su_kien_ok = set(danh_muc()) | {"gplxDangBiTuoc"}
    alias = src["loai_xe"]
    loi: list[str] = []
    out = []
    ids = set()
    for t in src["tinh_huong"]:
        sid = t["id"]
        if sid in ids:
            loi.append(f"{sid}: trùng id")
        ids.add(sid)
        if t["nhom"] not in NHOM:
            loi.append(f"{sid}: nhóm '{t['nhom']}' không hợp lệ")
        n = dict(t["nhan"])
        v = n["phien_ban"]
        dk = []
        nodes: list[str] = []
        for ma in n.get("hanh_vi") or []:
            info = reg.get(ma, {}).get("phien_ban", {}).get(v)
            if info is None:
                loi.append(f"{sid}: hành vi {ma} không có ở phiên bản {v}")
                continue
            kp = info.get("khung_phat")
            dk.append({"ma": ma, "id": info["can_cu"]["id"], "trich_dan": info["can_cu"]["trich_dan"],
                       "khung_phat": [kp["min"], kp["max"]] if kp else None})
            nodes += nodes_ky_vong(ma, v, specs, quan_sat)
        n["dieu_khoan"] = dk
        n["nodes"] = sorted(set(nodes))
        tr = dict(n.get("truong") or {})
        if isinstance(tr.get("loai_xe"), str):
            tr["loai_xe"] = alias[tr["loai_xe"]]
        n["truong"] = tr
        n.setdefault("hoi_luot_dau", [])
        n.setdefault("su_kien", {})
        for k in list(n["hoi_luot_dau"]) + list((t.get("tra_loi") or {})):
            if k not in slot_keys:
                loi.append(f"{sid}: trường câu hỏi '{k}' không có trong config/slots.yaml")
        for k in n["su_kien"]:
            if k not in su_kien_ok:
                loi.append(f"{sid}: sự kiện '{k}' không có trong ontology")
        out.append({"id": sid, "nhom": t["nhom"], "hom_nay": src["hom_nay"], "luot": t["luot"],
                    "tra_loi": t.get("tra_loi") or {}, "nhan": n, "ghi_chu": t.get("ghi_chu", "")})
    if loi:
        print("LỖI NHÃN:\n  " + "\n  ".join(loi), file=sys.stderr)
        return 1
    DICH.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out), encoding="utf-8")
    from collections import Counter

    print(f"{len(out)} tình huống → {DICH.relative_to(ROOT_DIR)}; theo nhóm: {dict(Counter(x['nhom'] for x in out))}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
