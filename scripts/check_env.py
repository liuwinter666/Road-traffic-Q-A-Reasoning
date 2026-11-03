"""Kiểm tra môi trường Phase 0: Python, thư viện, Java, Pellet, HermiT, dữ liệu thô.

Chạy:  python -m scripts.check_env
"""

from __future__ import annotations

import importlib
import sys
import time

from loguru import logger

from src.config import RAW_DIR

REQUIRED_MODULES = [
    "pydantic", "pydantic_settings", "yaml", "docx", "pdfplumber", "owlready2",
    "google.genai", "sentence_transformers", "faiss", "fastapi", "streamlit",
    "graphviz", "pandas", "pytest",
]


def check_python() -> bool:
    ok = sys.version_info >= (3, 11)
    logger.info("Python {} -> {}", sys.version.split()[0], "OK" if ok else "CẦN >= 3.11")
    return ok


def check_modules() -> bool:
    ok = True
    for name in REQUIRED_MODULES:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001
            ok = False
            logger.error("Thiếu module {}: {}", name, exc)
    if ok:
        logger.info("Đủ {} thư viện bắt buộc", len(REQUIRED_MODULES))
    return ok


def check_raw_data() -> bool:
    import docx

    files = sorted(RAW_DIR.glob("*.docx")) + sorted(RAW_DIR.glob("*.pdf"))
    if not files:
        logger.error("data/raw/ trống")
        return False
    for f in files:
        if f.suffix == ".docx":
            d = docx.Document(str(f))
            paras = [p.text for p in d.paragraphs if p.text.strip()]
            dieu = sum(1 for p in paras if p.strip().startswith("Điều "))
            logger.info("{}: {} đoạn, ~{} dòng bắt đầu bằng 'Điều '", f.name, len(paras), dieu)
        else:
            logger.info("{}: PDF (sẽ xử lý ở Phase 1)", f.name)
    return True


def check_reasoners() -> bool:
    from owlready2 import sync_reasoner_hermit, sync_reasoner_pellet

    from src.kb.java_env import JavaNotFoundError, configure_owlready, java_version
    from src.kb.toy_ontology import build_toy_world

    try:
        java = configure_owlready()
    except JavaNotFoundError as exc:
        logger.error(str(exc))
        return False
    logger.info("Java: {} ({})", java, java_version(java))

    ok = True
    # Pellet: OWL + SWRL built-in
    world, onto = build_toy_world()
    t0 = time.perf_counter()
    with onto:
        sync_reasoner_pellet(world, infer_property_values=True,
                             infer_data_property_values=True, debug=0)
    dt = time.perf_counter() - t0
    a, b = onto.nguoi_A, onto.nguoi_B
    checks = {
        "OWL: nguoi_A ∈ NguoiDieuKhienOTo": onto.NguoiDieuKhienOTo in a.is_a,
        "OWL: nguoi_B ∉ NguoiDieuKhienOTo": onto.NguoiDieuKhienOTo not in b.is_a,
        "SWRL: nguoi_A ∈ ViPhamToyNongDoCon": onto.ViPhamToyNongDoCon in a.is_a,
        "SWRL: nguoi_B ∉ ViPhamToyNongDoCon": onto.ViPhamToyNongDoCon not in b.is_a,
        "Trace: duocSuyRaBoi(nguoi_A, R_TOY)": onto.R_TOY in a.duocSuyRaBoi,
    }
    for name, passed in checks.items():
        logger.info("[Pellet {:.2f}s] {} -> {}", dt, name, "OK" if passed else "FAIL")
        ok &= passed

    # HermiT: chỉ OWL (HermiT không hỗ trợ SWRL built-in)
    world2, onto2 = build_toy_world()
    for r in list(onto2.rules()):
        from owlready2 import destroy_entity
        destroy_entity(r)
    with onto2:
        sync_reasoner_hermit(world2, infer_property_values=True, debug=0)
    passed = onto2.NguoiDieuKhienOTo in onto2.nguoi_A.is_a
    logger.info("[HermiT] OWL: nguoi_A ∈ NguoiDieuKhienOTo -> {}", "OK" if passed else "FAIL")
    ok &= passed
    return ok


def main() -> int:
    results = {
        "python": check_python(),
        "modules": check_modules(),
        "raw_data": check_raw_data(),
        "reasoners": check_reasoners(),
    }
    logger.info("Tổng kết: {}", results)
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
