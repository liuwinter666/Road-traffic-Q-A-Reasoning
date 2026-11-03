"""Truy xuất nguyên văn điều khoản (RAG).

Hai chức năng:
  1. ``lay(id, phien_ban, ngay)`` — TẤT ĐỊNH: nguyên văn một phần tử theo id, đúng phiên bản pháp lý (nghị định
     theo V1–V4; văn bản bổ trợ theo ngày vi phạm). Đây là đường chính để dẫn chứng trong câu trả lời.
  2. ``tim(cau, phien_ban, k)`` — NGỮ NGHĨA (FAISS + embedding đa ngữ, mặc định BAAI/bge-m3) trên khoản/điểm của
     nghị định ở phiên bản đó. Chỉ dùng để GỢI Ý "quy định có thể liên quan" khi hệ thống không kết luận được
     (hành vi ngoài phạm vi MVP) — không bao giờ là căn cứ kết luận.

Chỉ mục: vector của từng đoạn văn được cache theo hash nội dung ở ``data/index/`` (đoạn giống nhau giữa các phiên
bản chỉ tính một lần); chỉ mục FAISS (IndexFlatIP, cosine) dựng trong bộ nhớ từ cache. Dựng trước:
``python -m src.explanation.retriever --build`` (lần đầu vài phút trên CPU).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from loguru import logger

from src.config import PROCESSED_DIR, ROOT_DIR, get_settings

INDEX_DIR = ROOT_DIR / "data" / "index"
CAP_TIM = ("khoan", "diem")


@dataclass
class BanGhi:
    id: str
    nguon: str                 # articles_v4 | support_lttatgt_2026b ...
    van_ban: str               # ND168 | LXLVPHC ...
    so_hieu: str
    trich_dan: str             # "điểm b khoản 8 Điều 7 NĐ 168/2024/NĐ-CP"
    text: str
    full_text: str             # kèm tiêu đề điều + câu dẫn của khoản
    hieu_luc_tu: str | None
    hieu_luc_den: str | None


def trich_dan(rec: dict) -> str:
    """Cách viết căn cứ tiếng Việt từ bản ghi."""
    parts = []
    if rec.get("diem"):
        parts.append(f"điểm {rec['diem']}")
    if rec.get("khoan"):
        parts.append(f"khoản {rec['khoan']}")
    if rec.get("dieu"):
        parts.append(f"Điều {rec['dieu']}")
    doc = rec.get("so_hieu") or rec.get("doc", "")
    prefix = "NĐ " if "NĐ-CP" in doc else ("Luật số " if "QH" in doc else ("TT " if "TT-" in doc else ""))
    return (" ".join(parts) + f" {prefix}{doc}").strip()


def _ban_ghi(rec: dict, nguon: str) -> BanGhi:
    return BanGhi(rec["id"], nguon, rec.get("doc", ""), rec.get("so_hieu", ""), trich_dan(rec), rec.get("text", ""),
                  rec.get("full_text") or rec.get("text", ""), rec.get("effective_from"), rec.get("effective_to"))


@lru_cache(maxsize=None)
def _doc_file(nguon: str) -> dict[str, dict]:
    with (PROCESSED_DIR / f"{nguon}.jsonl").open(encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f)}


@lru_cache(maxsize=1)
def _support() -> dict[str, dict]:
    from src.ingest.build_articles import support_outputs
    from src.kb.temporal import load_sources

    return support_outputs(load_sources())


def _nguon_bo_tro(doc: str, ngay: date | None) -> list[str]:
    """Các file support_* của văn bản ``doc``: bản có hiệu lực tại ``ngay`` trước, sau đó bản mới nhất."""
    outs = [(k, v) for k, v in _support().items() if v["doc"] == doc]
    outs.sort(key=lambda kv: kv[1]["effective_from"], reverse=True)
    if ngay:
        def hl(v):
            tu, den = date.fromisoformat(str(v["effective_from"])[:10]), v.get("effective_to")
            return tu <= ngay and (den is None or ngay <= date.fromisoformat(str(den)[:10]))
        outs.sort(key=lambda kv: not hl(kv[1]))
    return [f"support_{k.lower()}" for k, _ in outs]


def lay(id_: str, phien_ban: str | None = None, ngay: date | None = None) -> BanGhi | None:
    """Nguyên văn phần tử ``id_`` (vd. ND168-D7-K8-b, LXLVPHC-D23-K4, TT38-D6-K1)."""
    doc = id_.split("-", 1)[0]
    if doc.startswith("ND"):
        nguon_ds = [f"articles_{phien_ban.lower()}"] if phien_ban else [f"articles_v{i}" for i in (4, 3, 2, 1)]
    else:
        nguon_ds = _nguon_bo_tro(doc, ngay)
    for nguon in nguon_ds:
        if (PROCESSED_DIR / f"{nguon}.jsonl").exists() and (rec := _doc_file(nguon).get(id_)):
            return _ban_ghi(rec, nguon)
    return None


# ---------------------------------------------------------------------------
# Tìm kiếm ngữ nghĩa
# ---------------------------------------------------------------------------

def _doan(rec: dict) -> str:
    """Đoạn văn dùng để nhúng: chỉ nội dung của chính khoản/điểm (cắt 400 ký tự). Bỏ tiêu đề Điều và câu dẫn của
    khoản — giống nhau cho mọi điểm cùng khoản nên làm các đoạn khó phân biệt và tốn thời gian nhúng."""
    return " ".join((rec.get("text") or "").split())[:400]


class Retriever:
    """Tìm kiếm ngữ nghĩa trên khoản/điểm của nghị định theo phiên bản."""

    def __init__(self, embedder=None, thu_muc: Path | None = None):
        self._embedder = embedder
        self.thu_muc = thu_muc or INDEX_DIR
        self._index: dict[str, tuple] = {}

    @property
    def embedder(self):
        if self._embedder is None:
            from src.extraction.entity_linker import embedder_mac_dinh

            self._embedder = embedder_mac_dinh()
        return self._embedder

    def _cache_file(self) -> Path:
        name = getattr(self.embedder, "model_name", None) or type(self.embedder).__name__
        return self.thu_muc / f"emb_{hashlib.sha1(str(name).encode()).hexdigest()[:10]}.npz"

    def _vectors(self, texts: list[str]):
        """Vector (đã chuẩn hóa L2) cho ``texts`` — đọc/ghi cache theo hash nội dung."""
        import numpy as np

        f = self._cache_file()
        cache: dict[str, np.ndarray] = {}
        if f.exists():
            z = np.load(f)
            cache = dict(zip(z["keys"].tolist(), z["vecs"]))
        keys = [hashlib.sha1(t.encode("utf-8")).hexdigest() for t in texts]
        thieu = [i for i, k in enumerate(keys) if k not in cache]
        if thieu:
            logger.info("Nhúng {} đoạn văn mới (đã cache {})", len(thieu), len(cache))
            f.parent.mkdir(parents=True, exist_ok=True)

            def luu():
                np.savez(f, keys=np.array(list(cache)), vecs=np.stack(list(cache.values())))
            for j in range(0, len(thieu), 32):
                part = thieu[j:j + 32]
                vecs = np.asarray(self.embedder.encode([texts[i] for i in part]), dtype="float32")
                for i, v in zip(part, vecs):
                    cache[keys[i]] = v
                logger.info("  nhúng {}/{}", min(j + 32, len(thieu)), len(thieu))
                if (j // 32) % 8 == 7:
                    luu()                                    # lưu dần — bị ngắt không mất phần đã nhúng
            luu()
        return np.stack([cache[k] for k in keys]).astype("float32")

    def chi_muc(self, phien_ban: str):
        if phien_ban not in self._index:
            import faiss

            recs = [r for r in _doc_file(f"articles_{phien_ban.lower()}").values()
                    if r.get("level") in CAP_TIM and r.get("status", "active") == "active"]
            vecs = self._vectors([_doan(r) for r in recs])
            idx = faiss.IndexFlatIP(vecs.shape[1])
            idx.add(vecs)
            self._index[phien_ban] = (idx, recs)
        return self._index[phien_ban]

    def tim(self, cau: str, phien_ban: str, k: int = 5, nguong: float | None = None,
            cach_dau: float | None = None) -> list[tuple[BanGhi, float]]:
        """Các khoản/điểm gần nghĩa nhất với ``cau`` trong phiên bản ``phien_ban`` (điểm cosine giảm dần).

        Giữ kết quả có điểm ≥ ``nguong`` VÀ không kém kết quả tốt nhất quá ``cach_dau`` (bỏ kết quả lạc đề đứng sau)."""
        import numpy as np

        idx, recs = self.chi_muc(phien_ban)
        q = np.asarray(self.embedder.encode([cau]), dtype="float32")
        scores, ids = idx.search(q, k)
        s = get_settings()
        nguong = s.rag_nguong if nguong is None else nguong
        cach_dau = s.rag_cach_dau if cach_dau is None else cach_dau
        top = float(scores[0][0]) if len(scores[0]) else 0.0
        return [(_ban_ghi(recs[i], f"articles_{phien_ban.lower()}"), float(sc))
                for sc, i in zip(scores[0], ids[0]) if i >= 0 and sc >= nguong and sc >= top - cach_dau]


@lru_cache(maxsize=1)
def retriever_mac_dinh() -> Retriever:
    return Retriever()


def main() -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Dựng chỉ mục RAG / tra nguyên văn")
    ap.add_argument("--build", nargs="*", metavar="V", help="dựng chỉ mục cho các phiên bản (mặc định: tất cả)")
    ap.add_argument("--id", help="in nguyên văn một phần tử")
    ap.add_argument("--phien-ban", default=None)
    ap.add_argument("--tim", help="câu truy vấn ngữ nghĩa")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.id:
        b = lay(a.id, a.phien_ban)
        print(b.trich_dan + "\n" + b.full_text if b else "Không tìm thấy")
    r = retriever_mac_dinh()
    if a.build is not None:
        from src.kb.temporal import load_sources

        for v in a.build or list(load_sources()["versions"]):
            idx, recs = r.chi_muc(v)
            print(f"{v}: {len(recs)} khoản/điểm")
    if a.tim:
        for b, s in r.tim(a.tim, a.phien_ban or "V4", nguong=0.0):
            print(f"{s:.3f} {b.trich_dan}: {b.text[:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
