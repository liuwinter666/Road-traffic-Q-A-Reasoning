"""Đối chiếu độc lập: kết quả hợp nhất V4 phải khớp bản vá thủ công của người dùng
(data/processed/manual_patches_ND238.yaml, cột `sau`), bỏ qua ký hiệu đánh số đầu dòng."""

from __future__ import annotations

import json
import re

import pytest
import yaml

from src.config import PROCESSED_DIR

PATCH_FILE = PROCESSED_DIR / "manual_patches_ND238.yaml"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


@pytest.mark.skipif(not PATCH_FILE.exists(), reason="Chưa có file bản vá thủ công")
def test_v4_matches_manual_patches():
    patches = yaml.safe_load(PATCH_FILE.read_text(encoding="utf-8"))
    with (PROCESSED_DIR / "articles_v4.jsonl").open(encoding="utf-8") as f:
        v4 = {r["id"]: r for r in map(json.loads, f)}
    mismatches = []
    for p in patches:
        rid = p["vi_tri"].split(" ")[0].replace("đ", "dd")
        text = v4[rid]["text"]
        if m := re.search(r"\(đoạn (\d+)\)", p["vi_tri"]):
            text = text.split("\n")[int(m.group(1)) - 1]
        sau = re.sub(r"^(\d+[a-zđ]?\.|[a-zđ]\d?\))\s*", "", _norm(p["sau"]))
        if sau not in _norm(text):
            mismatches.append(p["id"])
    assert mismatches == []
