"""Hợp nhất bán tự động: áp các lệnh sửa đổi của một văn bản sửa đổi (vd. NĐ 123) lên văn bản gốc (NĐ 100).

Các dạng lệnh được hỗ trợ (đều trích từ cách viết thực tế của NĐ 123, Điều 2):
  * ``Sửa đổi [điểm X[, điểm Y]] [khoản K] Điều D như sau: “...”``  → thay đơn vị
  * ``Sửa đổi đoạn mở đầu khoản K Điều D`` / ``Sửa đổi tên Điều D``  → thay đoạn mở đầu / tên điều
  * ``Bổ sung <đơn vị mới> vào sau <đơn vị> như sau: “...”``         → chèn đơn vị
  * ``Bãi bỏ <danh sách đơn vị>``                                       → đánh dấu bãi bỏ
  * ``Thay cụm từ “A” bằng cụm từ “B” tại <danh sách>``                 → thay chuỗi
  * ``Bổ sung cụm từ “A” vào trước/sau cụm từ “B” tại <danh sách>``     → chèn chuỗi
  * ``Bỏ cụm từ “A” tại <danh sách>``                                   → xóa chuỗi

Lệnh nào không nhận dạng được hoặc áp không chắc chắn (không tìm thấy cụm từ, cụm từ xuất
hiện nhiều lần, số hiệu không khớp) sẽ KHÔNG được áp và được ghi vào danh sách cần duyệt tay.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from loguru import logger

from src.ingest.parser import (
    CLOSE_Q,
    OPEN_Q,
    Diem,
    Dieu,
    Khoan,
    ParsedDoc,
    parse_units,
    quote_balance,
)

# ---------------------------------------------------------------------------
# Cấu trúc dữ liệu
# ---------------------------------------------------------------------------


@dataclass
class Target:
    """Địa chỉ một đơn vị trong văn bản gốc. ``part``: all | lead (đoạn mở đầu khoản) | title."""

    dieu: str | None = None
    khoan: str | None = None
    diem: str | None = None
    part: str = "all"

    def label(self) -> str:
        bits = []
        if self.part == "lead":
            bits.append("đoạn mở đầu")
        if self.part == "title":
            bits.append("tên")
        if self.diem:
            bits.append(f"điểm {self.diem}")
        if self.khoan:
            bits.append(f"khoản {self.khoan}")
        bits.append(f"Điều {self.dieu}")
        return " ".join(bits)


@dataclass
class Instruction:
    """Một lệnh sửa đổi kèm nội dung trích dẫn."""

    ref: str            # vd "Điều 2 khoản 3 điểm a NĐ 123"
    para: int
    text: str           # câu lệnh (đã bỏ số thứ tự)
    content: list[str] = field(default_factory=list)
    sub: bool = False   # True nếu là lệnh con đánh chữ (a, b, c...)


@dataclass
class ApplyResult:
    """Kết quả áp một lệnh."""

    instr: Instruction
    status: str          # applied | header | review
    detail: str = ""
    changed_ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tách lệnh từ văn bản sửa đổi
# ---------------------------------------------------------------------------

RE_NUM = re.compile(r"^(\d+)\.\s+(.*)$")
RE_LET = re.compile(r"^([a-zđ])\)\s+(.*)$")


def extract_instructions(amend: ParsedDoc, dieu_so: str, doc_label: str) -> list[Instruction]:
    """Lấy danh sách lệnh trong Điều ``dieu_so`` của văn bản sửa đổi."""
    dieu = amend.find_dieu(dieu_so)
    if dieu is None:
        raise ValueError(f"Không thấy Điều {dieu_so} trong {amend.doc}")
    idx = amend.dieu.index(dieu)
    start = dieu.para + 1
    end = amend.dieu[idx + 1].para if idx + 1 < len(amend.dieu) else len(amend.paragraphs)

    out: list[Instruction] = []
    depth = 0
    num = ""
    for i in range(start, end):
        line = amend.paragraphs[i]
        in_quote = depth > 0 or line.startswith(OPEN_Q)
        if in_quote and out:
            out[-1].content.append(line)
        else:
            if m := RE_NUM.match(line):
                num, body, ref = m.group(1), m.group(2), f"khoản {m.group(1)}"
            elif m := RE_LET.match(line):
                body, ref = m.group(2), f"điểm {m.group(1)} khoản {num}"
            else:
                body, ref = line, f"khoản {num} (đoạn không đánh số)"
            out.append(Instruction(ref=f"{ref} Điều {dieu_so} {doc_label}", para=i, text=body,
                                   sub=bool(RE_LET.match(line))))
        depth = max(0, depth + quote_balance(line))
    return out


def strip_outer_quotes(lines: list[str]) -> list[str]:
    """Bỏ ngoặc kép mở ở dòng đầu và ngoặc đóng + dấu câu ở dòng cuối của khối trích dẫn."""
    if not lines:
        return lines
    lines = list(lines)
    lines[0] = re.sub(r'^[“"]', "", lines[0]).strip()
    lines[-1] = re.sub(r'[”"]\s*[.;,]*\s*[”"]?\s*[.;]*\s*$', "", lines[-1]).strip()
    return lines


# ---------------------------------------------------------------------------
# Phân tích danh sách đơn vị đích
# ---------------------------------------------------------------------------

RE_TOKEN = re.compile(
    r"(?:(?P<pre>tên|đoạn mở đầu)\s+)?(?P<kind>điểm|khoản|Điều)\s+(?P<so>\d+[a-zđ]?|[a-zđư])(?![\w])"
)


def parse_targets(s: str) -> list[Target]:
    """Phân tích chuỗi như ``điểm b khoản 1, điểm a khoản 2 Điều 4; khoản 3 Điều 11``."""
    results: list[Target] = []
    open_items: list[Target] = []
    pending_diem: list[str] = []
    for m in RE_TOKEN.finditer(s):
        kind, so, pre = m.group("kind"), m.group("so"), m.group("pre")
        if kind == "điểm":
            pending_diem.append(so)
        elif kind == "khoản":
            if pending_diem:
                open_items.extend(Target(khoan=so, diem=d) for d in pending_diem)
                pending_diem = []
            else:
                open_items.append(Target(khoan=so, part="lead" if pre else "all"))
        else:  # Điều
            if not open_items:
                open_items.append(Target(part="title" if pre == "tên" else "all"))
            for t in open_items:
                t.dieu = so
            results.extend(open_items)
            open_items = []
    # Đơn vị thiếu số Điều -> trả về với dieu=None để nơi gọi báo lỗi
    results.extend(open_items)
    results.extend(Target(diem=d) for d in pending_diem)
    return results


# ---------------------------------------------------------------------------
# Truy cập cây văn bản
# ---------------------------------------------------------------------------


def locate(doc: ParsedDoc, t: Target):
    """Trả về (đơn vị, danh sách chứa nó) hoặc (None, None)."""
    d = doc.find_dieu(t.dieu) if t.dieu else None
    if d is None:
        return None, None
    if t.khoan is None:
        return d, doc.dieu
    k = d.find_khoan(t.khoan)
    if k is None:
        return None, None
    if t.diem is None:
        return k, d.khoan
    p = k.find_diem(t.diem)
    return (p, k.diem) if p else (None, None)


def unit_id(doc: str, t: Target) -> str:
    from src.ingest.parser import make_id

    return make_id(doc, t.dieu or "?", t.khoan, t.diem)


# ---------------------------------------------------------------------------
# Áp lệnh
# ---------------------------------------------------------------------------

RE_REPLACE = re.compile(r"^Sửa đổi(?:,\s*bổ sung)?\s+(?P<tg>.+?)\s+như sau:?\s*$")
RE_INSERT = re.compile(r"^Bổ sung\s+(?P<new>.+?)\s+vào sau\s+(?P<after>.+?)\s+như sau:?\s*$")
RE_REPEAL = re.compile(r"^Bãi bỏ\s+(?P<tg>.+?)[;.]?\s*$")
Q = r"[“\"](?P<{n}>.+?)[”\"]"
RE_PH_REPLACE = re.compile(
    rf"^Thay cụm từ {Q.format(n='old')} bằng cụm từ {Q.format(n='new')} tại (?P<tg>.+?)[;.]?\s*$")
RE_PH_INSERT = re.compile(
    rf"^Bổ sung cụm từ {Q.format(n='new')} vào (?P<pos>trước|sau) cụm từ {Q.format(n='anchor')}"
    r" tại (?P<tg>.+?)[;.]?\s*$")
RE_PH_DELETE = re.compile(rf"^(?:[Bb]ỏ|[Bb]ãi bỏ) cụm từ {Q.format(n='old')} tại (?P<tg>.+?)[;.]?\s*$")
RE_HEADER = re.compile(r"(một số|các) (điểm|khoản|điều|từ, cụm từ)|sau đây:?\s*$|như sau:\s*$")


class Consolidator:
    """Áp lần lượt các lệnh lên một bản sao của văn bản gốc."""

    def __init__(self, base: ParsedDoc, amend_label: str, overrides: list[dict] | None = None):
        self.doc = copy.deepcopy(base)
        self.label = amend_label
        self.results: list[ApplyResult] = []
        self.overrides = {o["ref"]: o for o in (overrides or []) if o.get("action") != "set_text"}
        self.set_texts = [o for o in (overrides or []) if o.get("action") == "set_text"]

    # ---- tiện ích ----
    def _note(self, unit, instr: Instruction, action: str) -> None:
        unit.history.append(f"{action} bởi {instr.ref}")

    def _review(self, instr: Instruction, detail: str) -> ApplyResult:
        r = ApplyResult(instr, "review", detail)
        self.results.append(r)
        logger.warning("CẦN DUYỆT [{}]: {} — {}", instr.ref, instr.text[:90], detail)
        return r

    def _ok(self, instr: Instruction, detail: str, ids: list[str]) -> ApplyResult:
        r = ApplyResult(instr, "applied", detail, ids)
        self.results.append(r)
        return r

    # ---- điều phối ----
    def apply(self, instr: Instruction, next_instr: Instruction | None) -> ApplyResult:
        ov = self.overrides.get(instr.ref)
        if ov and ov["action"] == "skip":
            r = ApplyResult(instr, "skipped", f"Bỏ qua theo quyết định duyệt tay: {ov.get('note', '')}")
            self.results.append(r)
            return r
        text = instr.text.strip()
        # sửa lỗi chính tả trong văn bản gốc: "Sửa đổi l khoản 5" (thiếu chữ "điểm")
        text = re.sub(r"^Sửa đổi ([a-zđ]) khoản", r"Sửa đổi điểm \1 khoản", text)

        if not instr.content:
            # Lệnh thao tác cụm từ / bãi bỏ (không có nội dung trích dẫn)
            parts = re.split(r";\s*(?=(?:bãi bỏ|bỏ|thay|bổ sung) cụm từ)", text, flags=re.I)
            if len(parts) > 1:
                rs = [self._apply_inline(Instruction(instr.ref, instr.para, p), p) for p in parts]
                if any(r is None for r in rs):
                    return self._review(instr, "Không nhận dạng được một phần của lệnh ghép")
                return rs[-1]
            r = self._apply_inline(instr, text)
            if r is not None:
                return r
            if RE_HEADER.search(text) and next_instr is not None and next_instr.sub:
                r = ApplyResult(instr, "header", "Tiêu đề nhóm lệnh")
                self.results.append(r)
                return r
            return self._review(instr, "Không nhận dạng được lệnh (không có nội dung trích dẫn)")

        content = strip_outer_quotes(instr.content)
        if m := RE_INSERT.match(text):
            return self._insert(instr, m.group("new"), m.group("after"), content)
        if m := RE_REPLACE.match(text):
            return self._replace(instr, m.group("tg"), content)
        return self._review(instr, "Không nhận dạng được lệnh có nội dung trích dẫn")

    def _apply_inline(self, instr: Instruction, text: str) -> ApplyResult | None:
        text = text.strip().rstrip(";.")
        if m := RE_PH_REPLACE.match(text + ";"):
            return self._phrase(instr, m.group("tg"), m.group("old"), m.group("new"), "thay")
        if m := RE_PH_INSERT.match(text + ";"):
            anchor, new, pos = m.group("anchor"), m.group("new"), m.group("pos")
            return self._phrase(instr, m.group("tg"), anchor, (pos, new), "bổ sung cụm từ")
        if m := RE_PH_DELETE.match(text + ";"):
            return self._phrase(instr, m.group("tg"), m.group("old"), "", "bỏ cụm từ")
        m = RE_REPEAL.match(text)
        if m and not RE_HEADER.search(text):
            return self._repeal(instr, m.group("tg"))
        return None

    # ---- thao tác cấu trúc ----
    def _replace(self, instr: Instruction, tg: str, content: list[str]) -> ApplyResult:
        targets = parse_targets(tg)
        if not targets or any(t.dieu is None for t in targets):
            return self._review(instr, f"Không xác định được đơn vị đích từ '{tg}'")
        level = "diem" if targets[0].diem else ("khoan" if targets[0].khoan else "dieu")
        part = targets[0].part
        if part in ("lead", "title"):
            return self._replace_part(instr, targets[0], content)
        new_units = parse_units(content, level)
        if len(new_units) != len(targets):
            return self._review(instr, f"Số đơn vị trong nội dung ({len(new_units)}) "
                                       f"khác số đơn vị đích ({len(targets)})")
        ids = []
        for t, new in zip(targets, new_units):
            old, container = locate(self.doc, t)
            if old is None:
                return self._review(instr, f"Không tìm thấy {t.label()} trong văn bản gốc")
            want = t.diem or t.khoan or t.dieu
            if new.so != want:
                return self._review(instr, f"Nội dung đánh số '{new.so}' không khớp đích '{want}'")
            new.para = old.para
            new.history = old.history + [f"Sửa đổi bởi {instr.ref}"]
            if isinstance(old, Dieu):
                new.chuong, new.muc = old.chuong, old.muc
            container[container.index(old)] = new
            ids.append(unit_id(self.doc.doc, t))
        return self._ok(instr, "Thay đơn vị", ids)

    def _replace_part(self, instr: Instruction, t: Target, content: list[str]) -> ApplyResult:
        old, _ = locate(self.doc, t)
        if old is None:
            return self._review(instr, f"Không tìm thấy {t.label()}")
        if t.part == "title":
            units = parse_units(content, "dieu")
            if len(units) != 1 or units[0].so != t.dieu:
                return self._review(instr, "Nội dung tên điều không đúng dạng 'Điều N. ...'")
            old.title = units[0].title
        else:
            units = parse_units(content, "khoan")
            if len(units) != 1 or units[0].so != t.khoan or units[0].diem:
                return self._review(instr, "Nội dung đoạn mở đầu không đúng dạng 'K. ...'")
            old.text = units[0].text
        self._note(old, instr, "Sửa đổi " + ("tên điều" if t.part == "title" else "đoạn mở đầu"))
        return self._ok(instr, f"Thay {t.label()}", [unit_id(self.doc.doc, t)])

    def _insert(self, instr: Instruction, new_desc: str, after: str, content: list[str]) -> ApplyResult:
        anchors = parse_targets(after)
        if len(anchors) != 1 or anchors[0].dieu is None:
            return self._review(instr, f"Không xác định được vị trí chèn '{after}'")
        a = anchors[0]
        level = "diem" if a.diem else ("khoan" if a.khoan else "dieu")
        anchor, container = locate(self.doc, a)
        if anchor is None:
            return self._review(instr, f"Không tìm thấy {a.label()} để chèn sau")
        new_units = parse_units(content, level)
        kind = {"diem": "điểm", "khoan": "khoản", "dieu": "Điều"}[level]
        wanted = re.findall(rf"{kind}\s+(\d+[a-zđ]?|[a-zđ])(?![\w])", new_desc)
        got = [u.so for u in new_units]
        if wanted != got:
            return self._review(instr, f"{kind} cần bổ sung {wanted} nhưng nội dung có {got}")
        pos = container.index(anchor) + 1
        ids = []
        for u in new_units:
            if any(x.so == u.so for x in container):
                return self._review(instr, f"{kind} {u.so} đã tồn tại")
            u.history.append(f"Bổ sung bởi {instr.ref}")
            u.para = -1
            if isinstance(u, Dieu):
                u.chuong, u.muc = anchor.chuong, anchor.muc
            container.insert(pos, u)
            pos += 1
            t = Target(dieu=a.dieu if level != "dieu" else u.so,
                       khoan=(a.khoan if level == "diem" else u.so) if level != "dieu" else None,
                       diem=u.so if level == "diem" else None)
            ids.append(unit_id(self.doc.doc, t))
        return self._ok(instr, f"Bổ sung {kind} {got}", ids)

    def _repeal(self, instr: Instruction, tg: str) -> ApplyResult:
        targets = parse_targets(tg)
        if not targets or any(t.dieu is None for t in targets):
            return self._review(instr, f"Không xác định được đơn vị bãi bỏ từ '{tg}'")
        ids = []
        for t in targets:
            unit, _ = locate(self.doc, t)
            if unit is None:
                return self._review(instr, f"Không tìm thấy {t.label()} để bãi bỏ")
            unit.status = "bai_bo"
            self._note(unit, instr, "Bãi bỏ")
            ids.append(unit_id(self.doc.doc, t))
        return self._ok(instr, "Bãi bỏ", ids)

    def _phrase(self, instr: Instruction, tg: str, old: str, new: str, action: str) -> ApplyResult:
        targets = parse_targets(tg)
        if not targets or any(t.dieu is None for t in targets):
            return self._review(instr, f"Không xác định được đơn vị đích từ '{tg}'")
        # Kiểm tra trước toàn bộ, chỉ áp khi mọi đích đều rõ ràng
        plan = []
        for t in targets:
            unit, _ = locate(self.doc, t)
            if unit is None:
                return self._review(instr, f"Không tìm thấy {t.label()}")
            fields = _text_fields(unit, t)
            hits = [(obj, attr) for obj, attr in fields if old in getattr(obj, attr)]
            n = sum(getattr(o, a).count(old) for o, a in hits)
            replace_all = self.overrides.get(instr.ref, {}).get("action") == "replace_all"
            if n == 0 or (n > 1 and not replace_all):
                return self._review(
                    instr, f"Cụm từ “{old}” xuất hiện {n} lần tại {t.label()} (cần đúng 1 lần)")
            plan.extend((t, h) for h in (hits if replace_all else hits[:1]))
        ids = []
        for t, (obj, attr) in plan:
            before = getattr(obj, attr)
            after = _apply_phrase(before, old, new)
            setattr(obj, attr, after)
            obj.history.append(f"{_phrase_desc(action, old, new)} bởi {instr.ref}")
            ids.append(unit_id(self.doc.doc, t))
        return self._ok(instr, _phrase_desc(action, old, new), ids)

    def _set_text(self, o: dict) -> None:
        t = target_from_id(o["id"])
        unit, _ = locate(self.doc, t)
        instr = Instruction(ref=o.get("ref", f"duyệt tay {o['id']}"), para=-1,
                            text=f"Gán nguyên văn cho {o['id']}")
        if unit is None:
            self._review(instr, f"set_text: không tìm thấy {o['id']}")
            return
        if isinstance(unit, Dieu):
            unit.title = o["text"]
        else:
            unit.text = o["text"]
        unit.history.append(f"Gán nguyên văn theo duyệt tay ({o.get('reviewer', '?')})")
        self._ok(instr, "set_text theo duyệt tay", [o["id"]])

    # ---- chạy toàn bộ ----
    def run(self, instructions: list[Instruction]) -> ParsedDoc:
        for i, ins in enumerate(instructions):
            nxt = instructions[i + 1] if i + 1 < len(instructions) else None
            self.apply(ins, nxt)
        for o in self.set_texts:
            self._set_text(o)
        n_ok = sum(r.status == "applied" for r in self.results)
        n_rv = sum(r.status == "review" for r in self.results)
        logger.info("Hợp nhất {}: {} lệnh đã áp, {} lệnh cần duyệt tay", self.label, n_ok, n_rv)
        return self.doc


PUNCT = ";,"


def _phrase_desc(action: str, old: str, new) -> str:
    """Mô tả ngắn một thao tác cụm từ để ghi lịch sử."""
    if isinstance(new, tuple):
        return f"Bổ sung cụm từ “{new[1]}” vào {new[0]} “{old}”"
    if new == "":
        return f"Bỏ cụm từ “{old}”"
    return f"Thay cụm từ “{old}” bằng “{new}”"


def _apply_phrase(text: str, old: str, new) -> str:
    """Áp một thao tác cụm từ lên ``text``.

    ``new`` là chuỗi (thay thế / xóa khi rỗng) hoặc tuple ``(vị trí, cụm bổ sung)`` với vị trí
    ``trước``/``sau``. Xử lý dấu câu khi ghép, vd. bổ sung “điểm d khoản 7;” vào sau “khoản 6”
    trong “khoản 6; điểm c khoản 8” → “khoản 6; điểm d khoản 7; điểm c khoản 8”.
    """
    if isinstance(new, str):
        out = text.replace(old, new)
        if new == "":
            out = re.sub(r" {2,}", " ", out)
            out = re.sub(r" +([;,.])", r"\1", out)
        return out
    pos, add = new
    i = text.index(old)
    if pos == "trước":
        sep = "" if add.endswith(" ") else " "
        return text[:i] + add + sep + text[i:]
    j = i + len(old)
    rest = text[j:]
    if add and add[-1] in PUNCT and rest.startswith(add[-1]):
        # “khoản 6” + “; ” + “điểm d khoản 7” + phần còn lại “; điểm c khoản 8”
        return text[:j] + add[-1] + " " + add[:-1].rstrip() + rest
    sep = "" if add.startswith((" ", ",", ";")) else " "
    return text[:j] + sep + add + rest


def target_from_id(uid: str) -> Target:
    """``ND100-D5-K4-c`` → Target(dieu='5', khoan='4', diem='c')."""
    parts = uid.split("-")[1:]
    rd = lambda x: x.replace("dd", "đ")  # noqa: E731
    t = Target(dieu=rd(parts[0][1:]))
    if len(parts) > 1:
        t.khoan = rd(parts[1][1:])
    if len(parts) > 2:
        t.diem = rd(parts[2])
    return t


def _text_fields(unit, t: Target) -> list[tuple[object, str]]:
    """Các (đối tượng, thuộc tính văn bản) để tìm cụm từ, theo thứ tự ưu tiên."""
    if isinstance(unit, Diem):
        return [(unit, "text")]
    if isinstance(unit, Khoan):
        if t.part == "lead":
            return [(unit, "text")]
        return [(unit, "text")] + [(d, "text") for d in unit.diem]
    return [(unit, "title"), (unit, "intro")] + [(k, "text") for k in unit.khoan] + [
        (d, "text") for k in unit.khoan for d in k.diem]
