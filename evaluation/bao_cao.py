"""Tổng hợp kết quả đánh giá → bảng, biểu đồ, evaluation/results/results.md.

    python -m evaluation.bao_cao

Đọc mọi evaluation/results/<cấu hình>/ket_qua.jsonl có sẵn, tính metric (evaluation/metrics.py), ghi:
  metrics.json, chi_tiet_<cấu hình>.json, bang_tong_hop.csv, theo_nhom.csv,
  so_sanh_cau_hinh.png, theo_nhom.png, do_tre.png, results.md
Phần nhận xét viết tay (nếu có) đặt ở evaluation/results/nhan_xet.md — được chèn vào results.md.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter

from evaluation.metrics import doc, phan_loai_loi, tinh
from evaluation.run_eval import KET_QUA, KICH_BAN

THU_TU = ["day_du", "khong_normalizer", "khong_entity_linker", "khong_fact_inducer", "khong_kiem_chung", "baseline_llm"]
TEN = {"day_du": "Hệ thống đầy đủ", "khong_normalizer": "Bỏ normalizer", "khong_entity_linker": "Bỏ entity linker",
       "khong_fact_inducer": "Bỏ fact inducer", "khong_kiem_chung": "Bỏ kiểm chứng cụm từ",
       "baseline_llm": "Baseline: chỉ LLM"}
CHINH = [("dieu_khoan_f1", "F1 phát hiện hành vi (theo điều khoản)"), ("khop_tron_ven", "Đúng trọn vẹn tình huống"),
         ("khung_phat_acc", "Đúng khung phạt"), ("hoi_dung_luc", "Hỏi lại đúng lúc"),
         ("dan_sai_luat", "Tỉ lệ dẫn sai điều khoản"), ("dan_het_hieu_luc", "Tỉ lệ dẫn văn bản hết hiệu lực")]
NHOM = {"don_loi": "Đơn lỗi", "da_loi": "Đa lỗi", "gian_tiep": "Gián tiếp", "thieu_thong_tin": "Thiếu thông tin",
        "khac_thoi_diem": "Khác thời điểm", "khong_vi_pham": "Không vi phạm"}
XANH, CAM, XAM, CHU, CHU_PHU = "#2a78d6", "#eb6834", "#b8b7b0", "#0b0b0b", "#52514e"


def _pct(x) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def _ve(kq: dict) -> list[str]:
    """Ba biểu đồ PNG (matplotlib, nền sáng). Trả tên file đã ghi."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": XAM,
                         "axes.labelcolor": CHU_PHU, "xtick.color": CHU_PHU, "ytick.color": CHU, "text.color": CHU})
    cfg = [c for c in THU_TU if c in kq]
    files = []

    # 1. Small multiples: mỗi ô một metric, thanh = cấu hình; hệ thống đầy đủ tô xanh, còn lại xám
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.2), constrained_layout=True)
    for ax, (k, ten) in zip(axes.flat, CHINH):
        vals = [kq[c].get(k) or 0 for c in cfg]
        y = range(len(cfg))
        ax.barh(y, vals, height=0.62, color=[XANH if c == "day_du" else XAM for c in cfg])
        ax.set_yticks(list(y), [TEN[c] for c in cfg])
        ax.invert_yaxis()
        ax.set_xlim(0, 1.12)
        ax.set_title(ten, fontsize=10, loc="left", color=CHU)
        for i, v in enumerate(vals):
            ax.text(v + 0.015, i, f"{v * 100:.0f}%", va="center", fontsize=8, color=CHU_PHU)
        ax.grid(axis="x", color="#ecebe7", linewidth=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis="x", labelsize=7)
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    fig.suptitle("So sánh hệ thống đầy đủ, các ablation và baseline (hai ô cuối: càng thấp càng tốt)",
                 fontsize=11, x=0.01, ha="left")
    f = KET_QUA / "so_sanh_cau_hinh.png"
    fig.savefig(f, dpi=150)
    plt.close(fig)
    files.append(f.name)

    # 2. F1 theo nhóm: hệ thống đầy đủ vs baseline (2 chuỗi: xanh, cam; có chú giải + nhãn số)
    if "day_du" in kq and "baseline_llm" in kq:
        nhom = [g for g in NHOM if g in kq["day_du"]["theo_nhom"]]
        fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
        w = 0.38
        for j, (c, mau) in enumerate((("day_du", XANH), ("baseline_llm", CAM))):
            vals = [kq[c]["theo_nhom"].get(g, {}).get("khop_tron_ven", 0) for g in nhom]
            xs = [i + (j - 0.5) * (w + 0.02) for i in range(len(nhom))]
            ax.bar(xs, vals, width=w, color=mau, label=TEN[c])
            for x, v in zip(xs, vals):
                ax.text(x, v + 0.02, f"{v * 100:.0f}%", ha="center", fontsize=8, color=CHU_PHU)
        ax.set_xticks(range(len(nhom)), [NHOM[g] for g in nhom])
        ax.set_ylim(0, 1.15)
        ax.set_ylabel("Tỉ lệ tình huống đúng trọn vẹn")
        ax.legend(frameon=False, loc="upper right")
        ax.grid(axis="y", color="#ecebe7", linewidth=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.set_title("Đúng trọn vẹn theo nhóm tình huống", loc="left", fontsize=11)
        f = KET_QUA / "theo_nhom.png"
        fig.savefig(f, dpi=150)
        plt.close(fig)
        files.append(f.name)

    # 3. Độ trễ mỗi lượt: trung bình và p95 (hai ô)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4), constrained_layout=True)
    for ax, (k, ten) in zip(axes, (("do_tre_tb_s", "Độ trễ trung bình mỗi lượt (giây)"),
                                   ("do_tre_p95_s", "Độ trễ p95 mỗi lượt (giây)"))):
        vals = [kq[c].get(k) or 0 for c in cfg]
        y = range(len(cfg))
        ax.barh(y, vals, height=0.62, color=[XANH if c == "day_du" else XAM for c in cfg])
        ax.set_yticks(list(y), [TEN[c] for c in cfg])
        ax.invert_yaxis()
        ax.set_title(ten, loc="left", fontsize=10)
        m = max(vals) if vals else 1
        for i, v in enumerate(vals):
            ax.text(v + m * 0.02, i, f"{v:.1f}", va="center", fontsize=8, color=CHU_PHU)
        ax.set_xlim(0, m * 1.18 if m else 1)
        ax.grid(axis="x", color="#ecebe7", linewidth=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    f = KET_QUA / "do_tre.png"
    fig.savefig(f, dpi=150)
    plt.close(fig)
    files.append(f.name)
    return files


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    kb = doc(KICH_BAN)
    kq: dict[str, dict] = {}
    for c in THU_TU:
        f = KET_QUA / c / "ket_qua.jsonl"
        if f.exists():
            kq[c] = tinh(doc(f), kb)
    if not kq:
        print("Chưa có kết quả — chạy python -m evaluation.ablation trước")
        return 1

    tong = {c: {k: v for k, v in m.items() if k != "chi_tiet"} for c, m in kq.items()}
    (KET_QUA / "metrics.json").write_text(json.dumps(tong, ensure_ascii=False, indent=2), encoding="utf-8")
    for c, m in kq.items():
        (KET_QUA / f"chi_tiet_{c}.json").write_text(json.dumps(m["chi_tiet"], ensure_ascii=False, indent=1),
                                                    encoding="utf-8")
    cot = ["so_tinh_huong", "loi", "hanh_vi_f1", "dieu_khoan_p", "dieu_khoan_r", "dieu_khoan_f1", "khop_tron_ven",
           "khung_phat_acc", "phien_ban_acc", "hoi_dung_luc", "hoi_dung_luc_tru_xac_nhan", "hoi_xac_nhan_luot_dau", "hoi_thua", "hoi_bo_sot", "dan_sai_luat",
           "dan_het_hieu_luc", "su_kien_acc", "node_recall", "do_tre_tb_s", "do_tre_p95_s", "tg_tinh_huong_tb_s"]
    with (KET_QUA / "bang_tong_hop.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cau_hinh", *cot])
        for c, m in tong.items():
            w.writerow([c, *[m.get(k) for k in cot]])
    with (KET_QUA / "theo_nhom.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cau_hinh", "nhom", "n", "loi", "dieu_khoan_f1", "khop_tron_ven", "hoi_dung_luc"])
        for c, m in tong.items():
            for g, v in m["theo_nhom"].items():
                w.writerow([c, g, v["n"], v["loi"], v["dieu_khoan_f1"], v["khop_tron_ven"], v["hoi_dung_luc"]])
    hinh = _ve(tong)

    # ---------------- results.md ----------------
    L = ["# Kết quả đánh giá", "",
         f"_Sinh tự động bởi `python -m evaluation.bao_cao` từ {len(kb)} tình huống trong `data/test/scenarios.jsonl` "
         "(hướng dẫn gán nhãn: `data/test/annotation_guide.md`). LLM: Gemini (temperature 0, có cache)._", ""]
    nx = KET_QUA / "nhan_xet.md"
    if nx.exists():
        L += [nx.read_text(encoding="utf-8").strip(), ""]
    L += ["## 1. Bảng tổng hợp", "",
          "| Cấu hình | F1 hành vi | F1 điều khoản | Đúng trọn vẹn | Đúng khung phạt | Đúng phiên bản | Hỏi đúng lúc "
          "| Dẫn sai | Dẫn hết hiệu lực | Trễ TB / p95 (s) | Lỗi chạy |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in [c for c in THU_TU if c in tong]:
        m = tong[c]
        L.append(f"| {TEN[c]} | {_pct(m.get('hanh_vi_f1'))} | {_pct(m['dieu_khoan_f1'])} | {_pct(m['khop_tron_ven'])} "
                 f"| {_pct(m['khung_phat_acc'])} | {_pct(m['phien_ban_acc'])} | {_pct(m['hoi_dung_luc'])} "
                 f"| {_pct(m['dan_sai_luat'])} | {_pct(m['dan_het_hieu_luc'])} "
                 f"| {m['do_tre_tb_s']} / {m['do_tre_p95_s']} | {m['loi']}/{m['so_tinh_huong']} |")
    L += ["", "F1 hành vi: so theo mã hành vi (baseline không có mã nên để trống). F1 điều khoản: so theo id điều khoản "
          "khớp tới điểm. Đúng trọn vẹn: tập điều khoản dự đoán trùng khít nhãn (kể cả tình huống không vi phạm). "
          "Dẫn sai / hết hiệu lực: tính trên mọi căn cứ được dẫn.", ""]
    for h in hinh:
        L += [f"![{h}]({h})", ""]
    if "day_du" in tong:
        d = tong["day_du"]
        L += ["## 2. Trích xuất, ánh xạ, suy ra sự kiện (hệ thống đầy đủ)", "",
              "| Trường | F1 |", "|---|---|"]
        L += [f"| {k} | {_pct(v)} |" for k, v in d["truong_f1"].items()]
        L += ["", f"- Sự kiện then chốt đúng (kể cả sự kiện phải suy ra): {_pct(d['su_kien_acc'])}",
              f"- Node dấu hiệu kỳ vọng có trong kết quả (ánh xạ node): {_pct(d['node_recall'])}",
              f"- Hỏi thừa ở lượt đầu: {d['hoi_thua']} tình huống; bỏ sót câu hỏi cần thiết: {d['hoi_bo_sot']}",
              f"- Hỏi xác nhận ở lượt đầu: {d['hoi_xac_nhan_luot_dau']} tình huống; hỏi đúng lúc nếu không tính câu "
              f"xác nhận: {_pct(d['hoi_dung_luc_tru_xac_nhan'])} (so với {_pct(d['hoi_dung_luc'])} khi tính)", ""]
        L += ["## 3. Theo nhóm tình huống", "", "| Nhóm | n | " + " | ".join(TEN[c] for c in tong) + " |",
              "|---|---|" + "---|" * len(tong)]
        for g in [g for g in NHOM if g in d["theo_nhom"]]:
            v = d["theo_nhom"][g]
            L.append(f"| {NHOM[g]} | {v['n']} | " + " | ".join(_pct(tong[c]["theo_nhom"].get(g, {}).get("khop_tron_ven"))
                                                     for c in tong) + " |")
        L += ["", "(Giá trị: tỉ lệ tình huống đúng trọn vẹn.)", ""]
        L += ["## 4. Ablation — thay đổi so với hệ thống đầy đủ", "",
              "| Cấu hình | Δ F1 điều khoản | Δ Đúng trọn vẹn | Δ Hỏi đúng lúc | Δ Trường loai_xe F1 |", "|---|---|---|---|---|"]
        for c in [c for c in THU_TU if c in tong and c not in ("day_du", "baseline_llm")]:
            m = tong[c]
            dx = lambda k: f"{(m[k] - d[k]) * 100:+.1f} điểm" if m.get(k) is not None and d.get(k) is not None else "—"
            lx = (m["truong_f1"].get("loai_xe"), d["truong_f1"].get("loai_xe"))
            L.append(f"| {TEN[c]} | {dx('dieu_khoan_f1')} | {dx('khop_tron_ven')} | {dx('hoi_dung_luc')} | "
                     + (f"{(lx[0] - lx[1]) * 100:+.1f} điểm" if None not in lx else "—") + " |")
        L += ["", "## 5. Phân tích lỗi theo tầng (hệ thống đầy đủ)", ""]
        ct = kq["day_du"]["chi_tiet"]
        dem = Counter(t for x in ct if (t := phan_loai_loi(x)))
        L += ["| Tầng gây lỗi đầu tiên | Số tình huống |", "|---|---|"]
        L += [f"| {k} | {v} |" for k, v in dem.most_common()] or ["| (không có lỗi) | 0 |"]
        L += ["", "Chi tiết các tình huống chưa đúng:", ""]
        for x in ct:
            if not (t := phan_loai_loi(x)):
                continue
            if x.get("loi"):
                L.append(f"- **{x['id']}** ({x['nhom']}) — {t}: {x['loi'][:160]}")
                continue
            ly = []
            if x["chuan"] != x["du_doan"]:
                ly.append(f"chuẩn {x['chuan'] or '∅'} / dự đoán {x['du_doan'] or '∅'}")
            if not x["hoi_dung_luc"]:
                ly.append(f"lượt đầu hỏi {x['hoi_dau'] or '∅'}, cần {x['hoi_can'] or '∅'}")
            if x["sai_truong"]:
                ly.append("trường: " + "; ".join(x["sai_truong"]))
            if x["sai_su_kien"]:
                ly.append("sự kiện sai/thiếu: " + ", ".join(x["sai_su_kien"]))
            if x["hoi_ngoai_du_kien"]:
                ly.append("hỏi ngoài dự kiến: " + ", ".join(sorted(set(x["hoi_ngoai_du_kien"]))))
            L.append(f"- **{x['id']}** ({x['nhom']}, {x['so_luot']} lượt) — {t}: " + " · ".join(ly))
    if "baseline_llm" in kq:
        L += ["", "## 6. Baseline chỉ dùng LLM — các lỗi điển hình", ""]
        for x in kq["baseline_llm"]["chi_tiet"]:
            if x.get("loi") or x.get("dung_het"):
                continue
            L.append(f"- **{x['id']}** ({x['nhom']}, phiên bản đúng {x['phien_ban_chuan']}): chuẩn {x['chuan'] or '∅'} / "
                     f"LLM dẫn {x['du_doan'] or '∅'}")
    L += ["", "## 7. Tái lập", "", "```", "python -m evaluation.sinh_nhan      # nhãn → data/test/scenarios.jsonl",
          "python -m evaluation.ablation       # chạy mọi cấu hình + baseline (chạy tiếp được nếu bị ngắt)",
          "python -m evaluation.bao_cao        # bảng, biểu đồ, results.md", "```", ""]
    (KET_QUA / "results.md").write_text("\n".join(L), encoding="utf-8")
    print("Đã ghi evaluation/results/results.md,", ", ".join(hinh))
    for c in tong:
        m = tong[c]
        print(f"  {c:22s} F1đk={_pct(m['dieu_khoan_f1'])} trọn vẹn={_pct(m['khop_tron_ven'])} "
              f"hỏi đúng lúc={_pct(m['hoi_dung_luc'])} dẫn hết hiệu lực={_pct(m['dan_het_hieu_luc'])} lỗi={m['loi']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
