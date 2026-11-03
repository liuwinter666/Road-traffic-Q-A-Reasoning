"""Sinh lại toàn bộ dữ liệu tri thức theo đúng thứ tự phụ thuộc.

Chạy:  python -m scripts.build_all

  1. build_articles  — parse + hợp nhất văn bản → articles_v*.jsonl, support_*.jsonl, consolidation_review.md
  2. speed_limits    — bảng tốc độ TT 31, TT 38 → speed_limits.json
  3. mvp_report      — kiểm chứng danh sách hành vi → docs/mvp_behaviors.md
  4. rules_builder   — luật SWRL + chế tài → ontology/rules/*.swrl, ontology/rule_registry.yaml
  5. build_ontology  — ontology đầy đủ → ontology/traffic_law.owl
  6. reasoning_kb    — ontology suy luận theo phiên bản → ontology/reasoning/traffic_law_<V>.owl
"""

from __future__ import annotations

import sys
import time

from loguru import logger


def main() -> int:
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    from src.ingest import build_articles, mvp_report, speed_limits
    from src.kb import build_ontology, reasoning_kb, rules_builder

    steps = [("build_articles", build_articles.main), ("speed_limits", speed_limits.build),
             ("mvp_report", mvp_report.main), ("rules_builder", rules_builder.build),
             ("build_ontology", build_ontology.build), ("reasoning_kb", reasoning_kb.build)]
    for name, fn in steps:
        t = time.perf_counter()
        rc = fn()
        logger.info("== {} xong ({:.1f}s)", name, time.perf_counter() - t)
        if name == "mvp_report" and rc:
            logger.error("Danh sách hành vi có lỗi kiểm chứng — dừng")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
