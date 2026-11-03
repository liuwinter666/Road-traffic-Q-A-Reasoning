"""Test parser, hợp nhất NĐ 123 → V2 và cấu hình phiên bản."""

from __future__ import annotations

import re

import pytest

from src.config import RAW_DIR
from src.ingest.build_articles import Builder, extract_fine, flatten, load_sources
from src.ingest.consolidate import _apply_phrase, parse_targets
from src.ingest.parser import make_id, parse_file, read_paragraphs


@pytest.fixture(scope="module")
def cfg():
    return load_sources()


@pytest.fixture(scope="module")
def builder(cfg):
    return Builder(cfg, overrides=[])


@pytest.fixture(scope="module")
def records(builder, cfg):
    return {v: {r["id"]: r for r in flatten(builder.build(v), cfg)} for v in cfg["versions"]}


# ---------------- parser ----------------

def test_make_id():
    assert make_id("ND168", "7", "10", "a") == "ND168-D7-K10-a"
    assert make_id("ND168", "6", "1", "đ") == "ND168-D6-K1-dd"
    assert make_id("ND100", "4a") == "ND100-D4a"


def test_parse_nd168_structure():
    doc = parse_file("ND168", RAW_DIR / "ND_168.docx")
    assert len(doc.dieu) == 55
    d6 = doc.find_dieu("6")
    assert [k.so for k in d6.khoan] == [str(i) for i in range(1, 17)]
    assert "0,25 miligam đến 0,4 miligam/1 lít khí thở" in d6.find_khoan("9").find_diem("a").text
    # nội dung trích dẫn trong Điều 52 (sửa NĐ 100) không được tách thành Điều mới
    assert [d.so for d in doc.dieu][-4:] == ["52", "53", "54", "55"]


def test_parse_nd100_structure():
    doc = parse_file("ND100", RAW_DIR / "ND_100.docx")
    assert len(doc.dieu) == 86
    assert doc.find_dieu("84").title.startswith("Hiệu lực thi hành")


# ---------------- consolidate helpers ----------------

def test_parse_targets_mixed():
    ts = parse_targets("điểm b khoản 1, điểm a khoản 2, điểm l khoản 3 Điều 4; điểm a khoản 12 Điều 11")
    assert [(t.dieu, t.khoan, t.diem) for t in ts] == [
        ("4", "1", "b"), ("4", "2", "a"), ("4", "3", "l"), ("11", "12", "a")]


def test_parse_targets_lead_and_multi_diem():
    ts = parse_targets("tên khoản 4 Điều 5, khoản 5 Điều 7")
    assert [(t.dieu, t.khoan, t.part) for t in ts] == [("5", "4", "lead"), ("7", "5", "all")]
    ts = parse_targets("điểm d, điểm đ, điểm e, điểm g khoản 5 Điều 53")
    assert [t.diem for t in ts] == ["d", "đ", "e", "g"] and {t.dieu for t in ts} == {"53"}


def test_apply_phrase_punctuation():
    assert _apply_phrase("điểm c khoản 6; điểm c khoản 8;", "khoản 6", ("sau", "điểm d khoản 7;")) \
        == "điểm c khoản 6; điểm d khoản 7; điểm c khoản 8;"
    assert _apply_phrase("khoản 4, khoản 5", "khoản 5", ("trước", "khoản 4a,")) == "khoản 4, khoản 4a, khoản 5"
    assert _apply_phrase("Đơn vị sự nghiệp công lập;", "công lập", "") == "Đơn vị sự nghiệp;"


def test_extract_fine():
    f = extract_fine("Phạt tiền từ 18.000.000 đồng đến 20.000.000 đồng đối với người điều khiển xe")
    assert f["ca_nhan"] == [18_000_000, 20_000_000] and f["to_chuc"] is None
    f = extract_fine("Phạt tiền từ 2.000.000 đồng đến 4.000.000 đồng đối với cá nhân, "
                     "từ 4.000.000 đồng đến 8.000.000 đồng đối với tổ chức là chủ xe")
    assert f["to_chuc"] == [4_000_000, 8_000_000]


# ---------------- V2 consolidation ----------------

def test_v2_review_count(builder):
    vb = builder.build("V2")
    results = vb.consolidation[0][1]
    reviews = [r for r in results if r.status == "review"]
    # Hiện chỉ còn lệnh "tháo dỡ" → "phá dỡ" (xuất hiện nhiều lần) cần duyệt tay
    assert len(reviews) == 1 and "tháo dỡ" in reviews[0].instr.text


def test_v2_fine_changes(records):
    v1, v2 = records["V1"], records["V2"]
    assert v1["ND100-D5-K4"]["khung_phat"]["ca_nhan"] == [1_000_000, 2_000_000]
    assert v2["ND100-D5-K4"]["khung_phat"]["ca_nhan"] == [2_000_000, 3_000_000]
    assert v2["ND100-D6-K2"]["khung_phat"]["ca_nhan"] == [300_000, 400_000]


def test_v2_structural_changes(records):
    v1, v2 = records["V1"], records["V2"]
    assert "ND100-D6-K3-n" not in v1 and "mũ bảo hiểm" in v2["ND100-D6-K3-n"]["text"]
    assert v1["ND100-D6-K2-i"]["status"] == "active" and v2["ND100-D6-K2-i"]["status"] == "bai_bo"
    assert v2["ND100-D83"]["status"] == "bai_bo"
    assert "ND100-D4a" in v2
    assert v2["ND100-D30-K13-c"]["history_inherited"]


# ---------------- cấu hình phiên bản ----------------

def test_versions_contiguous(cfg):
    from datetime import timedelta

    vs = list(cfg["versions"].values())
    for a, b in zip(vs, vs[1:]):
        assert a["effective_to"] + timedelta(days=1) == b["effective_from"]


def test_evidence_quotes_exist_in_source(cfg):
    """Mọi câu trích `evidence` phải có trong văn bản gốc (bỏ tiền tố 'Điều X khoản Y: ')."""
    for key, meta in cfg["documents"].items():
        text = "\n".join(read_paragraphs(RAW_DIR / meta["file"]))
        quotes = [meta["evidence"]] + [o["evidence"] for o in meta.get("element_effective_overrides") or []]
        for q in quotes:
            body = re.sub(r"^[^:]+:\s*", "", q)
            assert body in text, f"{key}: không thấy trích dẫn: {body[:80]}"


def test_v3_element_override(records):
    v3 = records["V3"]
    assert v3["ND168-D6-K3-m"]["effective_from"] == "2026-01-01"
    assert v3["ND168-D6-K3-a"]["effective_from"] == "2025-01-01"
    assert v3["ND168-D32-K1-b"]["effective_from"] is None
    assert v3["ND168-D32-K1-b"]["effective_verified"] is False


# ---------------- V4 (NĐ 238 sửa NĐ 168) ----------------

def test_v4_consolidation(records, builder):
    v3, v4 = records["V3"], records["V4"]
    results = builder.build("V4").consolidation[-1][1]
    assert sum(r.status == "review" for r in results) == 5
    # bổ sung khoản 1a vào TRƯỚC khoản 1
    ids = [i for i in v4 if i.startswith("ND168-D6-K") and i.count("-") == 2]
    assert ids[:2] == ["ND168-D6-K1a", "ND168-D6-K1"]
    # lệnh nằm ở tiêu đề Điều ("Điều 6. Sửa đổi bổ sung điểm a khoản 4 Điều 18")
    assert "50 cm3" in v3["ND168-D18-K4-a"]["text"] and "50 cm3" not in v4["ND168-D18-K4-a"]["text"]
    # điểm "k1"
    assert "ND168-D41-K4-k1" in v4
    assert v4["ND168-D32-K17-d"]["status"] == "bai_bo"


def test_v4_element_override_scoped(records):
    # ngoại lệ hiệu lực do NĐ 238 đặt ra chỉ áp cho V4, không áp cho V3
    assert records["V4"]["ND168-D20-K5-l"]["effective_from"] == "2028-01-01"
    assert records["V3"]["ND168-D20-K5-l"]["effective_from"] == "2025-01-01"
    assert records["V4"]["ND168-D6-K1a"]["effective_from"] == "2026-08-15"
