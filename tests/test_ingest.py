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
    for key, meta in list(cfg["documents"].items()) + list(cfg["supporting_documents"].items()):
        text = "\n".join(read_paragraphs(RAW_DIR / meta["file"]))
        quotes = [meta["evidence"]] + [o["evidence"] for o in meta.get("element_effectivity") or []]
        for q in quotes:
            body = re.sub(r"^[^:]+:\s*", "", q)
            assert body in text, f"{key}: không thấy trích dẫn: {body[:80]}"


def test_v3_element_override(records):
    v3 = records["V3"]
    assert v3["ND168-D6-K3-m"]["effective_from"] == "2026-01-01"
    assert v3["ND168-D6-K3-a"]["effective_from"] == "2025-01-01"
    assert v3["ND168-D32-K1-b"]["effective_from"] is None
    assert "bảo vệ môi trường" in v3["ND168-D32-K1-b"]["hieu_luc_dieu_kien"]


# ---------------- V4 (NĐ 238 sửa NĐ 168) ----------------

def test_v4_consolidation(records, builder):
    v3, v4 = records["V3"], records["V4"]
    results = builder.build("V4").consolidation[-1][1]
    # không dùng quyết định duyệt tay: còn 4 lệnh (2 lệnh ghép, 2 lệnh cụm từ nhiều lần/khác hoa thường)
    assert sum(r.status == "review" for r in results) == 4
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
    r4 = records["V4"]["ND168-D20-K5-l"]
    assert r4["hieu_luc_mot_phan"] and r4["effective_from"] == "2026-08-15"
    assert [x["tu"] for x in r4["hieu_luc_chi_tiet"]] == ["2026-08-15", "2028-01-01"]
    assert not records["V3"]["ND168-D20-K5-l"]["hieu_luc_mot_phan"]
    assert records["V3"]["ND168-D20-K5-l"]["effective_from"] == "2025-01-01"
    assert records["V4"]["ND168-D6-K1a"]["effective_from"] == "2026-08-15"



def test_overrides_resolve_all_reviews(cfg):
    """Với quyết định duyệt tay trong config/consolidation_overrides.yaml, không còn lệnh nào treo."""
    import yaml

    from src.ingest.build_articles import OVERRIDES_FILE

    ov = yaml.safe_load(OVERRIDES_FILE.read_text(encoding="utf-8"))["overrides"]
    b = Builder(cfg, overrides=ov)
    for v in ("V2", "V4"):
        results = b.build(v).consolidation[-1][1]
        assert [r.instr.ref for r in results if r.status == "review"] == []
    v2 = {r["id"]: r for r in flatten(b.build("V2"), cfg)}
    assert "tháo dỡ" not in v2["ND100-D4-K3-l"]["text"]          # NĐ 123 thay cả 3 lần, chỉ ở V2
    v4 = {r["id"]: r for r in flatten(b.build("V4"), cfg)}
    assert "trực thuộc Trung ương" not in v4["ND168-D55"]["text"]
    assert "Điều 20 (điểm l khoản 5, điểm đ khoản 6)" in v4["ND168-D47-K3-h"]["text"]
    assert v4["ND168-D50-K3-a"]["text"].split("\n")[1].startswith("Trường hợp Chủ tịch Ủy ban nhân dân cấp xã")


# ---------------- văn bản hợp nhất (chú thích) ----------------

def test_consolidated_law_footnotes():
    doc = parse_file("LXLVPHC", RAW_DIR / "VPHC.docx")
    assert len(doc.footnotes) == 278
    k = doc.find_dieu("23").find_khoan("4")
    assert k.notes == [30] and "[30]" not in k.text
    assert doc.find_dieu("2").find_khoan("5").text.startswith("Tái phạm")   # "5.[5] Tái phạm" nhận đúng khoản


def test_footnote_effectivity():
    import json

    from src.config import PROCESSED_DIR

    with (PROCESSED_DIR / "support_lxlvphc.jsonl").open(encoding="utf-8") as f:
        recs = {r["id"]: r for r in map(json.loads, f)}
    assert recs["LXLVPHC-D23-K4"]["effective_from"] == "2022-01-01"     # sửa bởi Luật 67/2020
    assert recs["LXLVPHC-D9-K1"]["effective_from"] == "2013-07-01"      # chưa sửa đổi
    assert recs["LXLVPHC-D134-K3"]["chu_thich"][0]["van_ban"].startswith("Luật số 67/2020/QH14")


def test_docx_tables_read_in_order():
    doc = parse_file("TT38", RAW_DIR / "TT_38.docx")
    k2 = doc.find_dieu("6").find_khoan("2").text
    assert "Bảng 2" in k2 and "| Xe ô tô chở người đến 28 chỗ" in k2



def test_supporting_evidence_quotes(cfg):
    """Căn cứ hiệu lực của văn bản bổ trợ: ngày kết thúc (trích từ văn bản thay thế), căn cứ ở cấp phiên bản."""
    texts = {}

    def text_of(key):
        if key not in texts:
            meta = cfg["documents"].get(key) or cfg["supporting_documents"][key]
            texts[key] = "\n".join(read_paragraphs(RAW_DIR / meta["file"]))
        return texts[key]

    for key, meta in cfg["supporting_documents"].items():
        if e := meta.get("effective_to_evidence"):
            assert e["quote"] in text_of(e["doc"]), key
        if meta.get("evidence_khac"):
            assert meta["evidence_khac"] in text_of(key), key
        for v, vm in (meta.get("versions") or {}).items():
            for o in vm.get("element_effectivity") or []:
                assert o["evidence"] in text_of(o.get("evidence_doc", key)), v


def test_luat_118_consolidation(cfg, builder):
    results = builder.build("LTTATGT_2026B").consolidation[-1][1]
    assert sum(r.status == "applied" for r in results) == 31
    assert not [r for r in results if r.status == "review"]
    only = builder.build("LTTATGT_2026A").consolidation[-1][1]
    assert [r.instr.ref for r in only] == ["điểm a khoản 20 Điều 7 Luật 118/2025/QH15"]
