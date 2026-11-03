"""Test môi trường: Pellet chạy được OWL + SWRL + mẹo truy vết `duocSuyRaBoi`."""

from __future__ import annotations

import pytest

from src.kb.java_env import find_java

pytestmark = pytest.mark.skipif(find_java() is None, reason="Chưa cài Java")


@pytest.fixture(scope="module")
def reasoned_toy():
    from owlready2 import sync_reasoner_pellet

    from src.kb.java_env import configure_owlready
    from src.kb.toy_ontology import build_toy_world

    configure_owlready()
    world, onto = build_toy_world()
    with onto:
        sync_reasoner_pellet(world, infer_property_values=True,
                             infer_data_property_values=True, debug=0)
    return onto


def test_owl_defined_class(reasoned_toy):
    onto = reasoned_toy
    assert onto.NguoiDieuKhienOTo in onto.nguoi_A.is_a
    assert onto.NguoiDieuKhienOTo not in onto.nguoi_B.is_a


def test_swrl_builtin_rule(reasoned_toy):
    onto = reasoned_toy
    assert onto.ViPhamToyNongDoCon in onto.nguoi_A.is_a
    assert onto.ViPhamToyNongDoCon not in onto.nguoi_B.is_a


def test_trace_property(reasoned_toy):
    onto = reasoned_toy
    assert onto.R_TOY in onto.nguoi_A.duocSuyRaBoi
    assert onto.nguoi_B.duocSuyRaBoi == []
