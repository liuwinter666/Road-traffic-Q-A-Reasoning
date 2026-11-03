"""Parser tách văn bản nghị định (DOCX/PDF) thành cấu trúc phân cấp Điều → Khoản → Điểm.

Quy ước định danh: ``{DOC}-D{dieu}[-K{khoan}[-{diem}]]``, ví dụ ``ND168-D7-K10-a``.
Chữ ``đ`` trong số hiệu điểm được viết thành ``dd`` trong id (``ND168-D6-K1-dd``) để id
an toàn khi dùng làm IRI trong ontology; trường ``diem`` vẫn giữ chữ gốc ``đ``.

Nội dung nằm trong ngoặc kép “...” (văn bản trích dẫn của điều sửa đổi) được coi là
phần tiếp nối của đơn vị đang mở, không bị tách thành Điều/Khoản/Điểm mới.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

# Bảng chữ cái tiếng Việt dùng đánh số điểm
DIEM_LETTERS = "a b c d đ e g h i k l m n o p q r s t u ư v x y".split()

RE_CHUONG = re.compile(r"^Chương\s+([IVXLC]+)\b")
RE_PHAN = re.compile(r"^Phần thứ\s+\w+")
RE_NOTE = re.compile(r"\[(\d+)\]")
RE_FOOTNOTE = re.compile(r"^\[(\d+)\]\s*(.*)$")
RE_MUC = re.compile(r"^Mục\s+(\d+)\.\s*(.*)$")
RE_DIEU = re.compile(r"^Điều\s+(\d+[a-zđ]?)\.\s*(.*)$")
RE_KHOAN = re.compile(r"^(\d+[a-zđ]?)\.\s+(.*)$")
RE_DIEM = re.compile(r"^([a-zđư]\d?)\)\s*(.*)$")  # cho phép điểm "k1" (NĐ 238)

OPEN_Q, CLOSE_Q = "“", "”"


def id_token(s: str) -> str:
    """Chuẩn hóa ký hiệu (điều/khoản/điểm) để dùng trong id: ``đ`` → ``dd``."""
    return s.replace("đ", "dd")


def make_id(doc: str, dieu: str, khoan: str | None = None, diem: str | None = None) -> str:
    """Sinh id dạng ``ND168-D7-K10-a``."""
    parts = [doc, f"D{id_token(dieu)}"]
    if khoan is not None:
        parts.append(f"K{id_token(khoan)}")
    if diem is not None:
        parts.append(id_token(diem))
    return "-".join(parts)


@dataclass
class Diem:
    """Điểm (a, b, c, ...) trong một khoản."""

    so: str
    text: str
    para: int
    status: str = "active"  # active | bai_bo
    history: list[str] = field(default_factory=list)
    notes: list[int] = field(default_factory=list)  # số chú thích [n] (văn bản hợp nhất)


@dataclass
class Khoan:
    """Khoản: ``text`` là đoạn mở đầu (lead-in), các điểm nằm trong ``diem``."""

    so: str
    text: str
    para: int
    diem: list[Diem] = field(default_factory=list)
    status: str = "active"
    history: list[str] = field(default_factory=list)
    notes: list[int] = field(default_factory=list)

    def find_diem(self, so: str) -> Diem | None:
        return next((d for d in self.diem if d.so == so), None)


@dataclass
class Dieu:
    """Điều: ``title`` là tên điều, ``intro`` là đoạn không đánh số (nếu có)."""

    so: str
    title: str
    para: int
    chuong: str = ""
    muc: str = ""
    intro: str = ""
    khoan: list[Khoan] = field(default_factory=list)
    status: str = "active"
    history: list[str] = field(default_factory=list)
    notes: list[int] = field(default_factory=list)

    def find_khoan(self, so: str) -> Khoan | None:
        return next((k for k in self.khoan if k.so == so), None)


@dataclass
class ParsedDoc:
    """Kết quả parse một văn bản."""

    doc: str
    paragraphs: list[str]
    dieu: list[Dieu] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    footnotes: dict[int, str] = field(default_factory=dict)  # chú thích của văn bản hợp nhất

    def find_dieu(self, so: str) -> Dieu | None:
        return next((d for d in self.dieu if d.so == so), None)


def read_paragraphs(path: Path) -> list[str]:
    """Đọc văn bản thành danh sách đoạn (đã strip, bỏ đoạn rỗng).

    Hỗ trợ DOCX (python-docx) và PDF (pdfplumber, mỗi dòng là một đoạn).
    """
    if path.suffix.lower() == ".docx":
        import docx

        paras = _docx_lines(docx.Document(str(path)))
    elif path.suffix.lower() == ".pdf":
        import pdfplumber

        paras = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                paras.extend((page.extract_text() or "").splitlines())
    else:
        raise ValueError(f"Không hỗ trợ định dạng {path.suffix}")
    return [normalize_ws(p) for p in paras if p and p.strip()]


SKIP_TABLE_MARKERS = ("CỘNG HÒA XÃ HỘI CHỦ NGHĨA", "Nơi nhận")


def _docx_lines(d) -> list[str]:
    """Đọc thân DOCX theo đúng thứ tự, gồm cả bảng.

    Mỗi hàng của bảng thành một dòng ``| ô 1 | ô 2 | ...`` (gộp ô trùng do merge). Bỏ qua bảng
    quốc hiệu/số hiệu ở đầu và bảng "Nơi nhận"/chữ ký ở cuối văn bản.
    """
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    lines: list[str] = []
    for el in d.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            lines.append(Paragraph(el, d).text)
        elif tag == "tbl":
            t = Table(el, d)
            text = " ".join(c.text for r in t.rows for c in r.cells)
            if any(m in text for m in SKIP_TABLE_MARKERS):
                continue
            for r in t.rows:
                cells: list[str] = []
                for c in r.cells:
                    v = normalize_ws(c.text.replace("\n", " "))
                    if not cells or cells[-1] != v:
                        cells.append(v)
                lines.append("| " + " | ".join(cells) + " |")
    return lines


# Chữ Kirin trông giống chữ Latin (lỗi gõ trong văn bản nguồn, vd. "р)" thay cho "p)" ở NĐ 123)
HOMOGLYPHS = str.maketrans("аеорсхуАВЕКМНОРСТХ", "aeopcxyABEKMHOPCTX")


def fix_homoglyphs(s: str) -> tuple[str, int]:
    """Thay chữ Kirin giống Latin bằng chữ Latin. Trả về (chuỗi mới, số ký tự đã thay)."""
    fixed = s.translate(HOMOGLYPHS)
    return fixed, sum(1 for x, y in zip(s, fixed) if x != y)


def normalize_ws(s: str) -> str:
    """Gộp khoảng trắng thừa, thay khoảng trắng không ngắt (NBSP) bằng khoảng trắng thường."""
    return re.sub(r"[ \t ]+", " ", s).strip()


def quote_balance(s: str) -> int:
    """Hiệu số ngoặc kép mở – đóng trong chuỗi.

    Ngoài ngoặc cong “ ”, xử lý cả ngoặc ASCII (NĐ 238 dùng loại này, NĐ 123 có chỗ trộn
    ASCII mở + cong đóng): một dấu nháy ASCII là *mở* nếu đứng đầu dòng hoặc sau khoảng trắng/"("
    và ngay sau nó không phải khoảng trắng; ngược lại là *đóng*.
    """
    bal = s.count(OPEN_Q) - s.count(CLOSE_Q)
    for i, ch in enumerate(s):
        if ch != '"':
            continue
        prev = s[i - 1] if i > 0 else " "
        nxt = s[i + 1] if i + 1 < len(s) else " "
        bal += 1 if (prev.isspace() or prev == "(") and not nxt.isspace() else -1
    return bal


def parse_paragraphs(doc: str, paras: list[str], quiet: bool = False,
                     strip_notes: bool = False) -> ParsedDoc:
    """Dựng cây Điều/Khoản/Điểm từ danh sách đoạn. ``quiet=True`` để không log thống kê.

    ``strip_notes=True`` (văn bản hợp nhất): bỏ dấu chú thích ``[n]`` khỏi nội dung và ghi số
    chú thích vào ``notes`` của đơn vị chứa nó.
    """
    out = ParsedDoc(doc=doc, paragraphs=paras)
    chuong = muc = ""
    cur_dieu: Dieu | None = None
    cur_khoan: Khoan | None = None
    cur_diem: Diem | None = None
    depth = 0  # độ sâu ngoặc kép, >0 nghĩa là đang ở trong đoạn trích dẫn
    expect_chuong_title = False

    def append_cont(text: str) -> None:
        if cur_diem is not None:
            cur_diem.text += "\n" + text
        elif cur_khoan is not None:
            cur_khoan.text += "\n" + text
        elif cur_dieu is not None:
            cur_dieu.intro = (cur_dieu.intro + "\n" + text).strip()

    for i, line in enumerate(paras):
        line_notes: list[int] = []
        if strip_notes:
            line_notes = [int(x) for x in RE_NOTE.findall(line)]
            line = normalize_ws(RE_NOTE.sub("", line))
        quoted = depth > 0 or line.startswith(OPEN_Q) or line.startswith('"')
        if quoted:
            append_cont(line)
        elif expect_chuong_title:
            chuong = f"{chuong}. {line}"
            expect_chuong_title = False
        elif m := RE_CHUONG.match(line):
            chuong, muc = f"Chương {m.group(1)}", ""
            expect_chuong_title = True
        elif RE_PHAN.match(line) and depth == 0:
            chuong, muc = line, ""
            expect_chuong_title = True
        elif m := RE_MUC.match(line):
            muc = f"Mục {m.group(1)}. {m.group(2)}"
        elif m := RE_DIEU.match(line):
            cur_dieu = Dieu(so=m.group(1), title=m.group(2).strip(), para=i,
                            chuong=chuong, muc=muc)
            if out.find_dieu(cur_dieu.so):
                out.warnings.append(f"Trùng Điều {cur_dieu.so} tại đoạn {i}")
            out.dieu.append(cur_dieu)
            cur_khoan = cur_diem = None
        elif cur_dieu is not None and (m := RE_KHOAN.match(line)):
            cur_khoan = Khoan(so=m.group(1), text=m.group(2), para=i)
            if cur_dieu.find_khoan(cur_khoan.so):
                out.warnings.append(f"Trùng khoản {cur_khoan.so} Điều {cur_dieu.so} tại đoạn {i}")
            cur_dieu.khoan.append(cur_khoan)
            cur_diem = None
        elif cur_khoan is not None and (m := RE_DIEM.match(line)):
            cur_diem = Diem(so=m.group(1), text=m.group(2), para=i)
            if cur_khoan.find_diem(cur_diem.so):
                out.warnings.append(
                    f"Trùng điểm {cur_diem.so} khoản {cur_khoan.so} Điều {cur_dieu.so} tại đoạn {i}")
            cur_khoan.diem.append(cur_diem)
        else:
            append_cont(line)
        if line_notes:
            unit = cur_diem or cur_khoan or cur_dieu
            if unit is not None:
                unit.notes.extend(line_notes)
        depth = max(0, depth + quote_balance(line))

    log = logger.debug if quiet else logger.info
    log("{}: {} điều, {} khoản, {} điểm", doc, len(out.dieu),
                sum(len(d.khoan) for d in out.dieu),
                sum(len(k.diem) for d in out.dieu for k in d.khoan))
    for w in out.warnings:
        (logger.debug if quiet else logger.warning)("{}: {}", doc, w)
    return out


def parse_file(doc: str, path: Path) -> ParsedDoc:
    """Đọc và parse một file văn bản (có chuẩn hóa chữ Kirin giống Latin)."""
    paras, notes = [], []
    for i, raw in enumerate(read_paragraphs(path)):
        fixed, n = fix_homoglyphs(raw)
        if n:
            notes.append(f"Đoạn {i}: thay {n} ký tự Kirin giống Latin: '{raw[:40]}' -> '{fixed[:40]}'")
        paras.append(fixed)
    body, footnotes = split_footnotes(paras)
    out = parse_paragraphs(doc, body, strip_notes=bool(footnotes))
    out.footnotes = footnotes
    for note in notes:
        logger.warning("{}: {}", doc, note)
    out.warnings = notes + out.warnings
    return out


def split_footnotes(paras: list[str]) -> tuple[list[str], dict[int, str]]:
    """Tách phần chú thích cuối văn bản hợp nhất (các đoạn bắt đầu ``[1] ...``, ``[2] ...``).

    Phần chú thích bắt đầu ở đoạn ``[1] ...`` đầu tiên nằm sau Điều đầu tiên. Văn bản không có
    phần này thì trả về nguyên danh sách và dict rỗng.
    """
    first_dieu = next((i for i, x in enumerate(paras) if RE_DIEU.match(x)), None)
    if first_dieu is None:
        return paras, {}
    start = next((i for i in range(first_dieu, len(paras)) if paras[i].startswith("[1] ")), None)
    if start is None:
        return paras, {}
    notes: dict[int, str] = {}
    cur = None
    for line in paras[start:]:
        if m := RE_FOOTNOTE.match(line):
            cur = int(m.group(1))
            notes[cur] = m.group(2)
        elif cur is not None:
            notes[cur] += "\n" + line
    return paras[:start], notes


def parse_units(lines: list[str], level: str) -> list:
    """Parse đoạn nội dung trích dẫn thành danh sách đơn vị cùng cấp ``level``.

    level: ``dieu`` → list[Dieu]; ``khoan`` → list[Khoan]; ``diem`` → list[Diem].
    Dùng khi áp nội dung sửa đổi (“...”) của văn bản sửa đổi.
    """
    lines = [ln for ln in lines if ln.strip()]
    if level == "dieu":
        return parse_paragraphs("_frag", lines, quiet=True).dieu
    if level == "khoan":
        return parse_paragraphs("_frag", ["Điều 0. _"] + lines, quiet=True).dieu[0].khoan
    if level == "diem":
        frag = parse_paragraphs("_frag", ["Điều 0. _", "0. _"] + lines, quiet=True)
        return frag.dieu[0].khoan[0].diem
    raise ValueError(level)
