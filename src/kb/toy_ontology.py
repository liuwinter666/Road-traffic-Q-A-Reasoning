"""Ontology "đồ chơi" dùng để kiểm tra môi trường ở Phase 0.

Mục đích: xác nhận owlready2 + Java + Pellet/HermiT chạy được, gồm:
  1. Suy luận OWL thuần (lớp định nghĩa bằng `equivalent_to`).
  2. Luật SWRL có built-in so sánh số (`swrlb:greaterThan`).
  3. Mẹo truy vết: luật gán thêm `duocSuyRaBoi(?x, R_TOY)` trỏ tới cá thể `QuyTac`.

LƯU Ý: ngưỡng trong file này là giá trị GIẢ để thử kỹ thuật, KHÔNG phải ngưỡng pháp lý.
"""

from __future__ import annotations

from owlready2 import (
    DataProperty,
    FunctionalProperty,
    Imp,
    ObjectProperty,
    Thing,
    World,
)

TOY_IRI = "http://example.org/toy_traffic.owl#"
TOY_THRESHOLD = 0.0  # giá trị giả, chỉ để thử built-in


def build_toy_world() -> tuple[World, object]:
    """Tạo World riêng chứa ontology đồ chơi; trả về (world, onto)."""
    world = World()
    onto = world.get_ontology(TOY_IRI)

    with onto:

        class PhuongTien(Thing):
            pass

        class OTo(PhuongTien):
            pass

        class XeMoTo(PhuongTien):
            pass

        class NguoiDieuKhien(Thing):
            pass

        class QuyTac(Thing):
            pass

        class HanhViViPham(Thing):
            pass

        class dieuKhien(ObjectProperty):
            domain = [NguoiDieuKhien]
            range = [PhuongTien]

        class duocSuyRaBoi(ObjectProperty):
            range = [QuyTac]

        class nongDoConKhiTho(DataProperty, FunctionalProperty):
            domain = [NguoiDieuKhien]
            range = [float]

        # Lớp định nghĩa: suy ra bằng OWL reasoner, không cần SWRL
        class NguoiDieuKhienOTo(NguoiDieuKhien):
            equivalent_to = [NguoiDieuKhien & dieuKhien.some(OTo)]

        class ViPhamToyNongDoCon(HanhViViPham):
            pass

        r_toy = QuyTac("R_TOY")

        rule = Imp()
        rule.set_as_rule(
            "NguoiDieuKhien(?x), nongDoConKhiTho(?x, ?c), greaterThan(?c, "
            f"{TOY_THRESHOLD}) -> ViPhamToyNongDoCon(?x), duocSuyRaBoi(?x, R_TOY)"
        )

        # Dữ liệu thử
        xe1 = OTo("xe_oto_1")
        xe2 = XeMoTo("xe_moto_1")
        a = NguoiDieuKhien("nguoi_A")
        a.dieuKhien = [xe1]
        a.nongDoConKhiTho = 0.3
        b = NguoiDieuKhien("nguoi_B")
        b.dieuKhien = [xe2]
        b.nongDoConKhiTho = 0.0

        _ = r_toy  # giữ tham chiếu cho rõ ý
    return world, onto
