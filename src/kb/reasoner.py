"""Chạy suy luận OWL + SWRL trên vụ việc và thu kết quả có truy vết.

Reasoner mặc định: **HermiT** (đi kèm owlready2). Lý do (đo được, xem tests/test_rules.py::test_pellet_limitation):
trên ontology suy luận có đủ luật của một phiên bản, Pellet 2.3.1 đi kèm owlready2 bỏ sót phần lớn kết luận của
luật SWRL có lớp ngưỡng (lớp định nghĩa bằng ràng buộc kiểu dữ liệu) trong thân luật và không trả về giá trị
thuộc tính do luật suy ra; HermiT cho kết quả đúng. Đổi bằng biến REASONER trong .env.

Truy vết: mỗi luật gán lớp đánh dấu QT_<mã luật> cho cá thể được kết luận; reasoner đọc lớp này thay vì bắt
HermiT suy luận mọi giá trị thuộc tính (tốn O(n²) theo số cá thể). Luật vẫn giữ các nguyên tử
apDungDieuKhoan/duocSuyRaBoi/viPhamHanhVi để ontology đầy đủ ngữ nghĩa (bật `infer_properties=True` nếu cần).

Quy trình:
  1. Nạp ontology suy luận của phiên bản (luật của phiên bản + luật tình tiết đã nhúng sẵn).
  2. Dựng cá thể vụ việc (abox.build_case) — có thể gộp nhiều vụ việc để chạy một lần.
  3. Chạy reasoner, đọc các lớp HV_* đã suy ra, quy tắc (duocSuyRaBoi), điều khoản (apDungDieuKhoan),
     người không đủ điều kiện, tình tiết (coTinhTiet).
  4. Áp quan hệ loại trừ ("trừ hành vi vi phạm quy định tại ...") từ sổ đăng ký luật.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date

from loguru import logger
from owlready2 import sync_reasoner_hermit, sync_reasoner_pellet

from src.config import get_settings
from src.kb.abox import CaseIndividuals, build_case, chon_phien_ban_cho
from src.kb.java_env import configure_owlready
from src.kb.loader import load_world
from src.kb.reasoning_kb import path_for as reasoning_path
from src.kb.rules_builder import load_registry


@dataclass
class KetLuanHanhVi:
    """Một hành vi vi phạm được kết luận cho một hành vi thực tế."""

    ma_hanh_vi: str
    quy_tac: list[str]
    dieu_khoan: list[str]           # IRI cá thể điều khoản (vd. V3_ND168-D6-K9-a)
    chu_the: str                    # tên cá thể người thực hiện
    hanh_vi_thuc_te: str            # tên cá thể hành vi (lái xe / giao xe)
    bi_loai_tru_boi: str | None = None
    ly_do_loai_tru: dict | None = None


@dataclass
class KetQuaSuyLuan:
    """Kết quả suy luận cho một vụ việc."""

    cid: str
    phien_ban: str
    ghi_chu_phien_ban: str
    mac_dinh_phien_ban: bool
    ket_luan: list[KetLuanHanhVi] = field(default_factory=list)
    nguoi_khong_du_dieu_kien: list[dict] = field(default_factory=list)
    tinh_tiet: list[dict] = field(default_factory=list)
    lop_suy_ra: dict[str, list[str]] = field(default_factory=dict)   # cá thể → lớp (dấu hiệu, ngưỡng...)
    thoi_gian_s: float = 0.0

    @property
    def hanh_vi(self) -> list[KetLuanHanhVi]:
        """Kết luận còn hiệu lực (đã bỏ các kết luận bị loại trừ)."""
        return [k for k in self.ket_luan if k.bi_loai_tru_boi is None]

    @property
    def ma_hanh_vi(self) -> set[str]:
        return {k.ma_hanh_vi for k in self.hanh_vi}


class TrafficReasoner:
    """Bộ suy luận dùng chung (đọc sổ đăng ký và file luật một lần)."""

    def __init__(self, engine: str | None = None, infer_properties: bool = False, batch_size: int = 10):
        self.engine = (engine or get_settings().reasoner).lower()
        self.infer_properties = infer_properties
        self.batch_size = batch_size
        self.registry = load_registry()
        configure_owlready()

    def run(self, cases: list[dict], hom_nay: date | None = None) -> list[KetQuaSuyLuan]:
        """Suy luận cho danh sách vụ việc: gom theo phiên bản, mỗi phiên bản một lần gọi reasoner trên
        ontology suy luận gọn của phiên bản đó (ontology/reasoning/traffic_law_<V>.owl, luật đã nhúng)."""
        pbs = [chon_phien_ban_cho(c, hom_nay) for c in cases]
        groups: dict[str, list[int]] = {}
        for i, pb in enumerate(pbs):
            groups.setdefault(pb.version, []).append(i)
        results: list[KetQuaSuyLuan | None] = [None] * len(cases)
        # HermiT tăng siêu tuyến tính theo số cá thể → chia lô (đo: lô 10 nhanh nhất)
        chunks = [(v, idxs[j:j + self.batch_size]) for v, idxs in groups.items()
                  for j in range(0, len(idxs), self.batch_size)]
        for v, idxs in chunks:
            t0 = time.perf_counter()
            world, onto = load_world(reasoning_path(v))
            built = [build_case(onto, cases[i], cid=f"c{i}", hom_nay=hom_nay, pb=pbs[i]) for i in idxs]
            t1 = time.perf_counter()
            if self.engine == "pellet":
                sync_reasoner_pellet(world, infer_property_values=True, infer_data_property_values=True, debug=0)
            else:
                # Không suy luận mọi giá trị thuộc tính (tốn O(n²)); truy vết qua lớp đánh dấu QT_<mã luật>
                sync_reasoner_hermit(world, infer_property_values=self.infer_properties, debug=0)
            dt = time.perf_counter() - t1
            logger.debug("{} {}: {} vụ việc, nạp {:.2f}s, suy luận {:.2f}s", self.engine, v, len(idxs), t1 - t0, dt)
            for i, b in zip(idxs, built):
                results[i] = self._collect(b, (time.perf_counter() - t0) / len(idxs))
        return results  # type: ignore[return-value]

    # ------------------------------------------------------------------
    def _collect(self, b: CaseIndividuals, dt: float) -> KetQuaSuyLuan:
        reg = self.registry
        res = KetQuaSuyLuan(b.cid, b.phien_ban.version, b.phien_ban.ghi_chu, b.phien_ban.mac_dinh, thoi_gian_s=dt)
        acts = [a for a in (b.hanh_vi_lai, b.hanh_vi_giao_xe) if a is not None]
        def fired_of(ind) -> list[str]:
            return sorted({c.name[3:] for c in ind.INDIRECT_is_a if getattr(c, "name", "").startswith("QT_")}
                          | {q.name for q in ind.duocSuyRaBoi})

        for a in acts:
            names = [getattr(c, "name", "") for c in a.INDIRECT_is_a]
            res.lop_suy_ra[a.name] = sorted(n for n in names if n and not n.startswith(("HV_", "QT_"))
                                            and n not in ("Thing", "DuocSuyRaBoiQuyTac"))
            fired = fired_of(a)
            for code in sorted(n[3:] for n in names if n.startswith("HV_")):
                qs = [q for q in fired if reg["quy_tac"].get(q, {}).get("ma_hanh_vi") == code]
                provs = sorted({reg["quy_tac"][q]["can_cu"]["iri"] for q in qs})
                res.ket_luan.append(KetLuanHanhVi(code, qs, provs, a.chuThe.name if a.chuThe else "", a.name))
            tts: dict[str, list[str]] = {}
            for q in fired:
                if t := reg["quy_tac"].get(q, {}).get("tinh_tiet"):
                    tts.setdefault(t, []).append(q)
            res.tinh_tiet += [{"hanh_vi_thuc_te": a.name, "tinh_tiet": t, "quy_tac": qs} for t, qs in sorted(tts.items())]
        for p in (b.nguoi_lai, b.chu_xe):
            if p is None:
                continue
            res.lop_suy_ra[p.name] = sorted(getattr(c, "name", "") for c in p.INDIRECT_is_a
                                            if getattr(c, "name", "") not in ("", "Thing", "DuocSuyRaBoiQuyTac")
                                            and not c.name.startswith("QT_"))
            if "NguoiKhongDuDieuKienDieuKhienXe" in res.lop_suy_ra[p.name]:
                res.nguoi_khong_du_dieu_kien.append({"nguoi": p.name, "quy_tac": fired_of(p)})
        res.lop_suy_ra[b.xe.name] = sorted(getattr(c, "name", "") for c in b.xe.INDIRECT_is_a
                                           if getattr(c, "name", "") not in ("", "Thing"))
        self._apply_exclusions(res)
        return res

    def _apply_exclusions(self, res: KetQuaSuyLuan) -> None:
        """Bỏ kết luận bị loại trừ bởi kết luận khác trên cùng hành vi thực tế."""
        hv = self.registry["hanh_vi"]
        for k in res.ket_luan:
            same_act = {x.ma_hanh_vi for x in res.ket_luan if x.hanh_vi_thuc_te == k.hanh_vi_thuc_te}
            info = hv.get(k.ma_hanh_vi, {}).get("phien_ban", {}).get(res.phien_ban, {})
            for ex in info.get("loai_tru_boi") or []:
                if ex["ma_hanh_vi"] in same_act:
                    k.bi_loai_tru_boi, k.ly_do_loai_tru = ex["ma_hanh_vi"], ex["can_cu"]
                    break


def suy_luan(case: dict, engine: str | None = None, hom_nay: date | None = None) -> KetQuaSuyLuan:
    """Tiện ích: suy luận một vụ việc."""
    return TrafficReasoner(engine).run([case], hom_nay=hom_nay)[0]
