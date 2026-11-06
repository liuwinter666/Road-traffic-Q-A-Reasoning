"""Chạy toàn bộ đánh giá: hệ thống đầy đủ, các ablation, baseline LLM-only, rồi tổng hợp báo cáo.

    python -m evaluation.ablation                         # tất cả
    python -m evaluation.ablation --cau-hinh day_du,khong_fact_inducer --bo-baseline

Ablation (mục 10 đặc tả): bỏ normalizer, bỏ entity linker, bỏ fact_inducer (+ bỏ kiểm chứng cụm từ). Mỗi cấu hình
ghi evaluation/results/<cấu hình>/ket_qua.jsonl và chạy tiếp được nếu bị ngắt (vd. hết hạn mức Gemini trong ngày).
Phản hồi LLM được cache theo prompt nên các ablation dùng lại phần lớn lượt gọi của cấu hình đầy đủ.
"""

from __future__ import annotations

import argparse
import sys

from loguru import logger

from evaluation import baseline_llm_only, bao_cao, run_eval

THU_TU = ["day_du", "khong_fact_inducer", "khong_entity_linker", "khong_normalizer", "khong_kiem_chung"]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cau-hinh", help="danh sách cấu hình, cách nhau dấu phẩy (mặc định: tất cả)")
    ap.add_argument("--bo-baseline", action="store_true")
    a = ap.parse_args()
    logger.remove()
    logger.add(sys.stderr, level="INFO", filter=lambda r: r["name"].startswith("evaluation") or r["level"].no >= 40)
    for c in (a.cau_hinh.split(",") if a.cau_hinh else THU_TU):
        run_eval.chay(c)
    if not a.bo_baseline:
        baseline_llm_only.chay()
    return bao_cao.main()


if __name__ == "__main__":
    raise SystemExit(main())
