"""CLI chạy pipeline đầu-cuối.

Hội thoại (gõ /moi để bắt đầu vụ việc mới, /hoso xem hồ sơ, /thoat để thoát):
    python -m scripts.chat

Một hoặc nhiều lượt không tương tác (mỗi -m là một tin nhắn, theo thứ tự):
    python -m scripts.chat -m "Thấy CSGT vẫy thì em rồ ga chạy luôn" -m "xe máy" -m "đúng"

Tùy chọn: --ngay 2025-03-10 (ngày vi phạm, như ô chọn ngày trên giao diện), --hom-nay (cố định "hôm nay" để chạy
lại cho kết quả giống nhau), --khong-suy-ra (tắt fact_inducer — ablation), --json (in hồ sơ + kết quả dạng JSON),
--chi-tiet (in cả lý do câu hỏi, chế tài không áp dụng, cụm từ bị loại).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import date

from loguru import logger


def _json(kq) -> dict:
    def conv(x):
        if dataclasses.is_dataclass(x):
            return {k: conv(v) for k, v in dataclasses.asdict(x).items()}
        if hasattr(x, "model_dump"):
            return x.model_dump(mode="json")
        if isinstance(x, dict):
            return {k: conv(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [conv(v) for v in x]
        if isinstance(x, date):
            return x.isoformat()
        return x
    return {"trang_thai": kq.trang_thai, "cau_hoi": [q.cau_hoi for q in kq.cau_hoi],
            "ho_so": kq.ho_so.model_dump(mode="json"), "case": conv(kq.du_lieu.case) if kq.du_lieu else None,
            "suy_luan": conv(kq.suy_luan), "quyet_dinh": conv(kq.quyet_dinh), "ghi_chu": kq.ghi_chu,
            "thoi_gian_s": kq.thoi_gian_s, "tra_loi": kq.tra_loi,
            "dien_dat": conv(kq.dien_dat), "trace": kq.trace.to_dict() if kq.trace else None}


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Tư vấn vi phạm luật giao thông (pipeline đầu-cuối)")
    ap.add_argument("-m", "--tin-nhan", action="append", help="tin nhắn (lặp lại cho nhiều lượt)")
    ap.add_argument("--ngay", type=date.fromisoformat, help="ngày vi phạm YYYY-MM-DD")
    ap.add_argument("--hom-nay", type=date.fromisoformat, help="cố định ngày hôm nay YYYY-MM-DD")
    ap.add_argument("--khong-suy-ra", action="store_true", help="tắt fact_inducer")
    ap.add_argument("--khong-dien-dat", action="store_true", help="không dùng LLM viết câu trả lời (bản tất định)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--chi-tiet", action="store_true")
    ap.add_argument("--log", default="WARNING", help="mức log (DEBUG/INFO/WARNING)")
    a = ap.parse_args()
    logger.remove()
    logger.add(sys.stderr, level=a.log.upper())

    from src.inference.pipeline import PhienLamViec, Pipeline
    from src.inference.report import trinh_bay

    pl = Pipeline(dung_fact_inducer=not a.khong_suy_ra, hom_nay=a.hom_nay, dung_dien_dat=not a.khong_dien_dat)
    phien = PhienLamViec()

    def mot_luot(msg: str) -> None:
        kq = pl.xu_ly(phien, msg, a.ngay)
        if a.json:
            print(json.dumps(_json(kq), ensure_ascii=False, indent=2))
        elif a.chi_tiet:
            print(trinh_bay(kq, chi_tiet=True))
            if kq.dien_dat is not None:
                print(f"\n[Diễn đạt: {kq.dien_dat.nguon}, {kq.dien_dat.so_lan_goi} lần gọi LLM"
                      + (f"; dự phòng vì {kq.dien_dat.ly_do_du_phong}" if kq.dien_dat.ly_do_du_phong else "") + "]")
                if kq.dien_dat.kiem_tra and kq.dien_dat.kiem_tra.loi:
                    print("  Lỗi kiểm tra: " + "; ".join(kq.dien_dat.kiem_tra.loi))
                if kq.dien_dat.nguon == "llm":
                    print("\n" + kq.tra_loi)
        else:
            print(kq.tra_loi)

    if a.tin_nhan:
        for msg in a.tin_nhan:
            print(f"\n» Bạn: {msg}", file=sys.stderr if a.json else sys.stdout)
            mot_luot(msg)
        return 0

    print("Tư vấn vi phạm giao thông — mô tả tình huống của bạn. (/moi: vụ mới, /hoso: xem hồ sơ, /thoat)")
    while True:
        try:
            msg = input("\nBạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not msg:
            continue
        if msg in ("/thoat", "/exit", "/quit"):
            return 0
        if msg == "/moi":
            phien = PhienLamViec()
            print("Đã bắt đầu vụ việc mới.")
            continue
        if msg == "/hoso":
            print(json.dumps(phien.ho_so.model_dump(mode="json", exclude_defaults=True), ensure_ascii=False, indent=2))
            continue
        try:
            mot_luot(msg)
        except Exception as e:  # noqa: BLE001 — CLI: báo lỗi rồi tiếp tục hội thoại
            logger.exception(e)
            print(f"Lỗi: {e}")


if __name__ == "__main__":
    raise SystemExit(main())
