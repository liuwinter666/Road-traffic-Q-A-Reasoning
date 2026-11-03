"""Sinh ontology suy luận gọn theo từng phiên bản: ``ontology/reasoning/traffic_law_<V>.owl``.

Chạy:  python -m src.kb.reasoning_kb

Mỗi file gồm: toàn bộ TBox; các phiên bản pháp lý; điều khoản được luật của phiên bản dẫn tới cùng khoản
chứa nó và khung phạt (để chuỗi thuộc tính chiuKhungPhat vẫn suy ra được); cá thể tình tiết; cá thể QuyTac
của phiên bản; và chính các luật SWRL của phiên bản + luật tình tiết. Bỏ các cá thể không tham gia suy
luận (điều khoản phiên bản khác, văn bản bổ trợ, chế tài...) giúp HermiT nhanh hơn ~2,5 lần.
Ontology đầy đủ (traffic_law.owl) vẫn dùng cho tra cứu, giải thích và Protégé.
"""

from __future__ import annotations

import sys

from loguru import logger
from owlready2 import Imp, destroy_entity

from src.config import ONTOLOGY_DIR, ROOT_DIR
from src.kb.loader import load_world
from src.kb.rules_builder import load_registry, read_swrl_files

OUT_DIR = ONTOLOGY_DIR / "reasoning"
DROP_CLASSES = {"TuocGPLX", "TichThuPhuongTien", "TichThuTangVat", "TruDiemGPLX", "BienPhapKhacPhucHauQua",
                "PhanNoiDung", "Luat", "ThongTu", "NghiDinh"}


def path_for(version: str):
    return OUT_DIR / f"traffic_law_{version}.owl"


def build_version(version: str, registry: dict, swrl: dict[str, str]) -> dict:
    world, onto = load_world()
    rules = [q for q, info in registry["quy_tac"].items()
             if info.get("phien_ban") == version or info["loai"] == "tinh_tiet"]
    need_prov = {registry["quy_tac"][q]["can_cu"]["iri"] for q in rules
                 if registry["quy_tac"][q]["loai"] == "hanh_vi"}
    keep = set(need_prov)
    for iri in list(need_prov):                       # khoản chứa điểm + khung phạt của khoản
        ind = onto[iri]
        parent = ind.thuocDieuKhoanCha
        if parent is not None:
            keep.add(parent.name)
            ind = parent
        keep.update(k.name for k in ind.coKhungPhat)
    keep.update(rules)
    dropped = 0
    for i in list(onto.individuals()):
        cls = i.is_a[0].name if i.is_a else ""
        if cls in ("PhienBanPhapLy", "TinhTietTangNang", "TinhTietGiamNhe"):
            continue
        if cls in DROP_CLASSES or (cls in ("Dieu", "Khoan", "Diem", "KhungPhat", "QuyTac") and i.name not in keep):
            destroy_entity(i)
            dropped += 1
    for c in list(onto.classes()):                    # lớp đánh dấu của luật phiên bản khác
        if c.name.startswith("QT_") and c.name[3:] not in keep:
            destroy_entity(c)
    with onto:
        for q in rules:
            Imp().set_as_rule(swrl[q])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = path_for(version)
    onto.save(file=str(out), format="rdfxml")
    n = len(list(onto.individuals()))
    logger.info("{}: {} luật, giữ {} cá thể (bỏ {}) -> {}", version, len(rules), n, dropped,
                out.relative_to(ROOT_DIR))
    return {"luat": len(rules), "ca_the": n}


def build() -> dict:
    from src.ingest.build_articles import load_sources

    registry, swrl = load_registry(), read_swrl_files()
    return {v: build_version(v, registry, swrl) for v in load_sources()["versions"]}


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    build()
