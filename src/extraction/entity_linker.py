"""Ánh xạ cụm từ người dùng vào node ontology.

Thứ tự: (1) từ điển đồng nghĩa ``data/processed/synonyms.json`` — so khớp nguyên cụm, có dấu hoặc không dấu,
ưu tiên cụm dài nhất, cho phép nhiều node không chồng lấn trong một câu; (2) nếu từ điển không khớp: độ tương
đồng embedding (mặc định ``BAAI/bge-m3``) với các cụm đồng nghĩa, chỉ nhận khi ≥ ``ENTITY_LINK_THRESHOLD``.

Giá trị boolean kéo theo của node dấu hiệu lấy từ ``config/ontology_concepts.yaml`` (observations,
tinh_tiet_facts) — từ điển chỉ chứa ngôn ngữ, không chứa nội dung pháp lý.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import yaml
from loguru import logger

from src.config import PROCESSED_DIR, ROOT_DIR, get_settings
from src.extraction.normalizer import bo_dau, chuan_hoa_chu

SYNONYMS_FILE = PROCESSED_DIR / "synonyms.json"
CONCEPTS_FILE = ROOT_DIR / "config" / "ontology_concepts.yaml"


class Embedder(Protocol):
    def encode(self, texts: list[str]):  # -> np.ndarray (n, d), đã chuẩn hóa L2
        ...


class SentenceTransformerEmbedder:
    """Embedding đa ngữ (nạp lười ở lần dùng đầu — lần đầu sẽ tải model)."""

    def __init__(self, model_name: str | None = None, device: str | None = None):
        s = get_settings()
        self.model_name = model_name or s.embedding_model
        self.device = device or s.embedding_device
        self._model = None

    def encode(self, texts: list[str]):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Nạp embedding model {} ({})", self.model_name, self.device)
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model.encode(texts, normalize_embeddings=True)


# Hư từ, số, lượng từ bỏ qua ở lượt khớp thứ hai ("uống 3 lon bia" ~ "uống bia",
# "gây tai nạn rồi bỏ chạy" ~ "gây tai nạn bỏ chạy", "đi chiếc SH" ~ "đi sh")
FILLERS = {"rồi", "thì", "và", "mà", "xong", "liền", "luôn", "cái", "chiếc", "đã", "vẫn", "cứ",
           "lon", "chai", "ly", "cốc", "chén", "két", "vài", "mấy", "nhiều", "ít", "khoảng", "tầm", "hơn"}


def _rut_gon(s: str) -> str:
    return " ".join(w for w in s.split() if w not in FILLERS and not re.fullmatch(r"[\d.,]+", w))


@dataclass
class LienKet:
    node: str
    kieu: str
    goc: str              # cụm khớp trong câu
    diem: float
    phuong_phap: str      # tu_dien | embedding
    su_kien: dict[str, bool] = field(default_factory=dict)


@lru_cache(maxsize=1)
def _node_facts() -> dict[str, dict[str, bool]]:
    cfg = yaml.safe_load(CONCEPTS_FILE.read_text(encoding="utf-8"))
    facts = {o["name"]: dict(o.get("values") or {}) for o in cfg["observations"]}
    facts.update({tf["fact"]: {tf["fact"]: True} for tf in cfg.get("tinh_tiet_facts") or []})
    return facts


class EntityLinker:
    def __init__(self, synonyms_path: Path = SYNONYMS_FILE, embedder: Embedder | None | str = "auto",
                 threshold: float | None = None):
        data = json.loads(synonyms_path.read_text(encoding="utf-8"))
        self.entries: list[tuple[str, str, str, str]] = []     # (kiểu, node, cụm chuẩn hóa, cụm không dấu)
        for kieu, nodes in data.items():
            if kieu.startswith("_"):
                continue
            for node, phrases in nodes.items():
                for p in set(phrases) | {node}:
                    n = chuan_hoa_chu(p)
                    self.entries.append((kieu, node, n, bo_dau(n)))
        # cụm rút gọn chỉ dùng khi còn ≥ 2 từ (tránh "con tôi" → "tôi")
        self.entries_rg = [(k, nd, r) for k, nd, p, _ in self.entries
                           if (r := _rut_gon(p)) and (r == p or len(r.split()) >= 2)]
        self.facts = _node_facts()
        unknown = {n for k, n, _, _ in self.entries if k == "dau_hieu" and n not in self.facts}
        if unknown:
            raise ValueError(f"synonyms.json có node dấu hiệu không có trong ontology_concepts: {unknown}")
        s = get_settings()
        self.threshold = s.entity_link_threshold if threshold is None else threshold
        self.embedder = SentenceTransformerEmbedder() if embedder == "auto" and s.entity_link_embedding else \
            (None if embedder == "auto" else embedder)
        self._emb_cache: dict[str, object] = {}

    def _facts_for(self, kieu: str, node: str) -> dict[str, bool]:
        return dict(self.facts.get(node, {})) if kieu in ("dau_hieu", "tinh_tiet") else {}

    def link(self, mention: str, kieu: str | list[str], nhieu: bool = True) -> list[LienKet]:
        """Các node khớp trong ``mention`` thuộc (các) kiểu ``kieu``. ``nhieu=False``: chỉ node tốt nhất."""
        kinds = [kieu] if isinstance(kieu, str) else list(kieu)
        m = chuan_hoa_chu(mention)
        m_nd = bo_dau(m)
        found: list[tuple[int, int, LienKet]] = []
        for k, node, p, p_nd in self.entries:
            if k not in kinds or not p:
                continue
            for hay, needle in ((m, p), (m_nd, p_nd)):
                if mt := re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", hay):
                    score = 1.0 if needle == hay else 0.9
                    found.append((mt.start(), mt.end(), LienKet(node, k, mention[mt.start():mt.end()], score,
                                                                 "tu_dien", self._facts_for(k, node))))
                    break
        # lượt 2: bỏ hư từ/số/lượng từ ở cả hai phía, chỉ cho node chưa khớp ở lượt 1
        m_rg = _rut_gon(m)
        have = {lk.node for _, _, lk in found}
        for k, node, p in self.entries_rg:
            if k not in kinds or not p or node in have:
                continue
            for hay, needle in ((m_rg, p), (bo_dau(m_rg), bo_dau(p))):
                if mt := re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", hay):
                    # vị trí quy về chuỗi rút gọn: dịch ra sau các khớp lượt 1 để không coi là chồng lấn
                    off = 10_000 + mt.start()
                    found.append((off, off + len(needle), LienKet(node, k, needle, 0.85, "tu_dien",
                                                                  self._facts_for(k, node))))
                    have.add(node)
                    break
        # chọn các khớp dài nhất, không chồng lấn
        found.sort(key=lambda x: (-(x[1] - x[0]), x[0]))
        chosen: list[tuple[int, int, LienKet]] = []
        for s, e, lk in found:
            if all(e <= s2 or s >= e2 for s2, e2, _ in chosen) and all(lk.node != c.node for _, _, c in chosen):
                chosen.append((s, e, lk))
        out = [lk for _, _, lk in sorted(chosen, key=lambda x: x[0])]
        if not out and self.embedder is not None:
            out = self._embed_link(mention, kinds)
        return out if nhieu else out[:1]

    def link_one(self, mention: str, kieu: str | list[str]) -> LienKet | None:
        r = self.link(mention, kieu, nhieu=False)
        return r[0] if r else None

    def _embed_link(self, mention: str, kinds: list[str]) -> list[LienKet]:
        import numpy as np

        cands = [(k, n, p) for k, n, p, _ in self.entries if k in kinds]
        if not cands:
            return []
        key = "|".join(kinds)
        if key not in self._emb_cache:
            self._emb_cache[key] = np.asarray(self.embedder.encode([p for _, _, p in cands]))
        mat = self._emb_cache[key]
        q = np.asarray(self.embedder.encode([chuan_hoa_chu(mention)]))[0]
        sims = mat @ q
        i = int(np.argmax(sims))
        if float(sims[i]) < self.threshold:
            return []
        k, n, p = cands[i]
        return [LienKet(n, k, mention, float(sims[i]), "embedding", self._facts_for(k, n))]
