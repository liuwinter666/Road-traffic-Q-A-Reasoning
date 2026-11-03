"""Trích hình thức xử phạt bổ sung, trừ điểm GPLX, biện pháp khác từ câu chữ nghị định.

Các câu chữ dạng:
  * "Thực hiện hành vi quy định tại điểm a, điểm b khoản 6; khoản 7 Điều này bị tước quyền sử dụng giấy
    phép lái xe từ 02 tháng đến 04 tháng"
  * "... tái phạm hoặc vi phạm nhiều lần hành vi quy định tại ... bị ..., tịch thu phương tiện"
  * "Thực hiện hành vi quy định tại một trong các điểm, khoản sau của Điều này mà gây tai nạn giao thông thì
    bị tước ...: điểm a, ... khoản 1; ..."
  * Khoản dẫn "Tịch thu phương tiện đối với người điều khiển xe thực hiện một trong các hành vi vi phạm sau
    đây:" kèm các điểm con mô tả hành vi (thường là "Tái phạm hành vi ... quy định tại ...").

Mỗi mệnh đề cho ra một ``Sanction`` gồm loại, giá trị, đích (điều/khoản/điểm được dẫn), điều kiện (nếu
có) và câu nguyên văn làm căn cứ. Không suy đoán: mệnh đề không nhận dạng được bị bỏ qua và ghi log.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from loguru import logger

from src.ingest.consolidate import Target, parse_targets

RE_TUOC = re.compile(r"tước quyền sử dụng [Gg]iấy phép lái xe.*?từ (\d+) tháng đến (\d+) tháng")
RE_TRU_DIEM = re.compile(r"trừ điểm giấy phép lái xe.*?(\d+) điểm")
RE_TICH_THU_PT = re.compile(r"[Tt]ịch thu phương tiện")
RE_TICH_THU = re.compile(r"[Tt]ịch thu (?!phương tiện)([^;.,]+)")
RE_THU_HOI = re.compile(r"thu hồi ([^;.]+)")
SANCTION_HINT = re.compile(r"tước quyền sử dụng [Gg]iấy phép lái xe|trừ điểm giấy phép lái xe|[Tt]ịch thu|thu hồi")
RE_VERB = re.compile(r"\s(?:thì |còn )?bị (?=tước|trừ|tịch thu|thu hồi|áp dụng)")
RE_DIEU_KIEN_TRUONG_HOP = re.compile(r"trong trường hợp (.+)$")


@dataclass
class Sanction:
    """Một hình thức/biện pháp áp cho một nhóm hành vi."""

    loai: str                      # tuoc_gplx | tru_diem | tich_thu_phuong_tien | tich_thu | thu_hoi
    gia_tri: dict
    targets: list[tuple[str, str | None, str | None]]   # (điều, khoản, điểm)
    dieu_kien: str | None          # tai_pham | nhieu_lan | tai_pham_hoac_nhieu_lan | gay_tai_nan | text
    can_cu_id: str                 # phần tử chứa câu chữ
    nguyen_van: str
    ghi_chu: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["targets"] = [list(t) for t in self.targets]
        return d


def _parse_value(after: str) -> list[tuple[str, dict]]:
    """Các hình thức trong phần sau động từ 'bị'."""
    out = []
    if m := RE_TUOC.search(after):
        out.append(("tuoc_gplx", {"tu_thang": int(m.group(1)), "den_thang": int(m.group(2))}))
    if m := RE_TRU_DIEM.search(after):
        out.append(("tru_diem", {"so_diem": int(m.group(1))}))
    if RE_TICH_THU_PT.search(after):
        out.append(("tich_thu_phuong_tien", {}))
    for m in RE_TICH_THU.finditer(after):
        obj = m.group(1).strip()
        if not obj.startswith(("phương tiện",)):
            out.append(("tich_thu", {"doi_tuong": obj}))
    if m := RE_THU_HOI.search(after):
        out.append(("thu_hoi", {"doi_tuong": m.group(1).strip()}))
    return out


def _condition(before: str) -> str | None:
    b = before.lower()
    if "tái phạm" in b and "nhiều lần" in b:
        return "tai_pham_hoac_nhieu_lan"
    if "tái phạm" in b:
        return "tai_pham"
    if "vi phạm nhiều lần" in b:
        return "nhieu_lan"
    if "gây tai nạn" in b:
        return "gay_tai_nan"
    if m := RE_DIEU_KIEN_TRUONG_HOP.search(before):
        return "trong trường hợp " + m.group(1).strip()
    return None


def _targets(s: str, dieu: str) -> list[tuple[str, str | None, str | None]]:
    ts: list[Target] = parse_targets(s)
    out = []
    for t in ts:
        d = t.dieu or dieu
        if t.khoan is None and t.diem is None:
            continue
        out.append((d, t.khoan, t.diem))
    return out


def _has_verb(s: str) -> bool:
    """Có động từ 'bị' của chế tài nằm sau cụm 'quy định tại' (đích đã được nêu xong)."""
    return "quy định tại" in s and RE_VERB.search(s, s.index("quy định tại")) is not None


def split_clauses(text: str) -> list[str]:
    """Tách câu chữ thành các mệnh đề có một động từ 'bị'. Dấu ';' trong danh sách đích (đứng trước 'bị')
    không làm tách; danh sách sau dấu ':' của mẫu 'một trong các điểm, khoản sau' giữ nguyên tới hết câu."""
    clauses, cur = [], ""
    i = 0
    while i < len(text):
        ch = text[i]
        cur += ch
        at_sep = ch in ";." and (i + 1 == len(text) or text[i + 1] == " ")
        if at_sep and _has_verb(cur) and "một trong các điểm, khoản sau" not in cur:
            clauses.append(cur.strip(" ;."))
            cur = ""
        elif at_sep and "một trong các điểm, khoản sau" in cur and ch == ".":
            clauses.append(cur.strip(" ;."))
            cur = ""
        i += 1
    if cur.strip(" ;."):
        clauses.append(cur.strip(" ;."))
    return clauses


def extract_from_record(rec: dict, children: list[dict]) -> list[Sanction]:
    """Trích chế tài từ một bản ghi khoản/điểm."""
    text = rec["text"].replace("\n", " ")
    dieu = rec["dieu"]
    out: list[Sanction] = []
    # Dạng khoản dẫn: "Tịch thu phương tiện đối với ... một trong các hành vi vi phạm sau đây:" + điểm con
    if re.match(r"^Tịch thu phương tiện đối với", text) and text.rstrip().endswith("sau đây:"):
        for c in children:
            ctext = c["text"].replace("\n", " ")
            tg = _targets(ctext, dieu)
            if not tg:
                logger.debug("Bỏ qua (không có đích) {}: {}", c["id"], ctext[:80])
                continue
            out.append(Sanction("tich_thu_phuong_tien", {}, tg, _condition(ctext), c["id"],
                                f"{text} {ctext}"))
        return out
    if re.match(r"^Tịch thu phương tiện đối với", text):
        tg = _targets(text, dieu)
        if tg:
            out.append(Sanction("tich_thu_phuong_tien", {}, tg, _condition(text), rec["id"], text))
        return out
    for clause in split_clauses(text):
        if not SANCTION_HINT.search(clause) or "quy định tại" not in clause:
            continue
        # động từ "bị" của chế tài nằm sau "quy định tại" (bỏ qua "Ngoài việc bị áp dụng hình thức xử phạt")
        m = RE_VERB.search(clause, clause.index("quy định tại"))
        if not m:
            continue
        before, after = clause[:m.start()], clause[m.end():]
        if "một trong các điểm, khoản sau" in before and ":" in after:
            after, target_part = after.split(":", 1)
        elif "quy định tại" in before:
            target_part = before.split("quy định tại", 1)[1]
        else:
            logger.debug("Bỏ qua mệnh đề không có đích trước 'bị' ({}): {}", rec["id"], clause[:100])
            continue
        values = _parse_value(after)
        if not values:
            continue
        # "khoản 9 Điều này hoặc tái phạm hành vi quy định tại điểm b khoản 7" → 2 nhóm đích
        groups = [(target_part, _condition(before))]
        if " hoặc tái phạm hành vi quy định tại " in target_part:
            a, b = target_part.split(" hoặc tái phạm hành vi quy định tại ", 1)
            groups = [(a, None), (b, "tai_pham")]
        for part, cond in groups:
            if m2 := RE_DIEU_KIEN_TRUONG_HOP.search(part):
                part, cond = part[:m2.start()], "trong trường hợp " + m2.group(1).strip()
            tg = _targets(part, dieu)
            if not tg:
                continue
            note = ["Áp dụng nếu là người điều khiển phương tiện"] if "nếu là người điều khiển" in before else []
            for loai, val in values:
                out.append(Sanction(loai, val, tg, cond, rec["id"], clause, list(note)))
    return out


def extract_all(records: dict[str, dict], dieu_list: set[str]) -> list[Sanction]:
    """Trích chế tài của các Điều trong ``dieu_list`` của một phiên bản."""
    by_parent: dict[str, list[dict]] = {}
    for r in records.values():
        if r["parent_id"]:
            by_parent.setdefault(r["parent_id"], []).append(r)
    out: list[Sanction] = []
    for r in records.values():
        if r["dieu"] not in dieu_list or r["level"] == "dieu" or r["status"] != "active":
            continue
        if not SANCTION_HINT.search(r["text"]):
            continue
        out.extend(extract_from_record(r, by_parent.get(r["id"], [])))
    return out


def applies_to(s: Sanction, rid_parts: tuple[str, str | None, str | None]) -> bool:
    """Chế tài ``s`` có áp cho phần tử (điều, khoản, điểm) không."""
    d, k, p = rid_parts
    for td, tk, tp in s.targets:
        if td != d or tk != k:
            continue
        if tp is None or tp == p:
            return True
    return False
