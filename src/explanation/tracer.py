"""Dựng chuỗi suy luận (trace) từ kết quả reasoner — tất định, không dùng LLM.

    sự kiện đầu vào ─► điều kiện của luật (ngưỡng / dấu hiệu / lớp xe / độ tuổi) ─► quy tắc R0xx
                    ─► hành vi vi phạm ─► điều khoản (nguyên văn) ─► khung phạt ─► mức đề xuất ─► chế tài

Reasoner gắn lớp đánh dấu QT_<mã> (tương đương ``duocSuyRaBoi``) cho cá thể được kết luận; tracer đi ngược: với
mỗi quy tắc đã kích hoạt, đọc thân luật SWRL trong ``rule_registry.yaml``, giải thích từng nguyên tử lớp bằng
định nghĩa trong ``config/ontology_concepts.yaml`` (ngưỡng kèm câu văn bản làm căn cứ, lớp hợp, dấu hiệu
boolean) và giá trị của vụ việc, cho tới sự kiện đầu vào cùng nguồn của nó (người dùng nêu / suy ra từ lời kể
kèm bằng chứng / người dùng xác nhận / tra bảng thông tư).

``Trace`` là đầu vào DUY NHẤT của verbalizer; ``can_cu_hop_le()`` / ``so_tien_hop_le()`` là danh sách được phép
xuất hiện trong câu trả lời (kiểm tra chống bịa điều khoản).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from functools import lru_cache

import yaml

from src.config import ROOT_DIR
from src.explanation.retriever import lay, trich_dan

KHUNG = {"HanhViDieuKhienXe", "HanhViGiaoXe", "HanhVi"}
RE_ATOM = re.compile(r"(\w+)\(\?(\w+)\)")
RE_ID = re.compile(r"\b(?:ND\d+|LXLVPHC|LTTATGT|GTDB2008|TT\d+)-D\d+(?:-K\d+)?(?:-[a-zđ]{1,2})?\b")
TRUONG_HO_SO = {"nongDoConKhiTho": "nong_do_con_khi_tho", "nongDoConMau": "nong_do_con_mau",
                "tocDoThucTe": "toc_do_thuc_te", "tocDoToiDaChoPhep": "toc_do_toi_da",
                "dungTichXiLanh": "dung_tich_xi_lanh", "congSuatDongCoDien": "cong_suat_dong_co_dien"}
NGUON_CHU = {"truc_tiep": "bạn nêu", "suy_ra": "suy ra từ lời kể", "xac_nhan": "bạn đã xác nhận",
             "tra_bang": "tra bảng tốc độ của thông tư", "tinh_toan": "tính từ tốc độ thực tế − tốc độ tối đa",
             "xep_loai": "xếp loại xe theo dung tích/công suất quy định trong luật"}


# ---------------------------------------------------------------------------
# Cấu trúc trace
# ---------------------------------------------------------------------------

@dataclass
class CanCu:
    id: str
    trich_dan: str
    nguyen_van: str = ""


@dataclass
class Nut:
    """Một điều kiện (hoặc sự kiện) trong cây giải thích."""

    loai: str                    # su_kien | nguong | hop | dau_hieu | phuong_tien | do_tuoi | hanh_vi | lop
    ten: str                     # tên lớp / thuộc tính
    mo_ta: str                   # câu tiếng Việt
    gia_tri: object = None
    nguon: str | None = None     # với su_kien: truc_tiep | suy_ra | xac_nhan | tra_bang | tinh_toan
    bang_chung: str | None = None
    can_cu: list[CanCu] = field(default_factory=list)
    con: list["Nut"] = field(default_factory=list)


@dataclass
class BuocQuyTac:
    ma: str
    mo_ta: str
    dieu_kien: list[Nut]


@dataclass
class KetLuanTrace:
    ma_hanh_vi: str
    ten: str
    quy_tac: list[BuocQuyTac]
    dieu_khoan: CanCu
    hinh_thuc_chinh: str
    khung_phat: list[int] | None
    muc_de_xuat: int | None
    ly_do: list[str]
    che_tai: list[dict]
    tru_diem: int | None
    tinh_tiet_tang: list[dict]
    tinh_tiet_giam: list[dict]
    can_cu_khac: list[CanCu]


@dataclass
class Trace:
    phien_ban: dict
    su_kien: list[Nut]
    ket_luan: list[KetLuanTrace]
    loai_tru: list[dict]
    nguoi_khong_du_dieu_kien: list[dict]
    tong_tien_de_xuat: int
    tru_diem_ap_dung: int | None
    ghi_chu: list[str]
    can_cu_chung: list[CanCu]

    def to_dict(self) -> dict:
        return asdict(self)

    # ---- danh sách được phép xuất hiện trong câu trả lời ----
    def can_cu_hop_le(self) -> dict[str, CanCu]:
        out: dict[str, CanCu] = {}

        def them(c: CanCu):
            out.setdefault(c.id, c)

        def duyet(n: Nut):
            for c in n.can_cu:
                them(c)
            for x in n.con:
                duyet(x)
        for n in self.su_kien:
            duyet(n)
        for k in self.ket_luan:
            them(k.dieu_khoan)
            for c in k.can_cu_khac:
                them(c)
            for q in k.quy_tac:
                for n in q.dieu_kien:
                    duyet(n)
            for ct in k.che_tai:
                them(CanCu(ct["can_cu_id"], ct["trich_dan"]))
        for c in self.can_cu_chung:
            them(c)
        for x in self.loai_tru + self.nguoi_khong_du_dieu_kien:
            for c in x.get("can_cu", []):
                them(CanCu(**c))
        for g in self.ghi_chu:
            for i in RE_ID.findall(g):
                if i not in out and (b := lay(i, self.phien_ban["ma"] if i.startswith("ND") else None,
                                              _d(self.phien_ban.get("ngay")))):
                    them(CanCu(i, b.trich_dan, b.text))
        return out

    def ma_quy_tac(self) -> set[str]:
        out = {q.ma for k in self.ket_luan for q in k.quy_tac}
        for x in self.nguoi_khong_du_dieu_kien:
            out |= set(x["quy_tac"])
        return out

    def so_tien_hop_le(self) -> set[int]:
        s = {self.tong_tien_de_xuat}
        for k in self.ket_luan:
            s |= set(k.khung_phat or []) | ({k.muc_de_xuat} if k.muc_de_xuat else set())
        return {x for x in s if x}

    # ---- hiển thị ----
    def dong_suy_luan(self, hien_ma: bool = True) -> list[str]:
        """Chuỗi suy luận dạng dòng. ``hien_ma=False``: bỏ mã quy tắc R… (câu trả lời cho người dùng; mã vẫn hiện ở
        tab Cây suy luận / Chi tiết)."""
        out = []
        for k in self.ket_luan:
            for q in k.quy_tac:
                dk = "; ".join(_mo_ta_cay(n) for n in q.dieu_kien)
                out.append((f"{q.ma}: " if hien_ma else "") + f"{dk} ⇒ {k.ten} ⇒ {k.dieu_khoan.trich_dan}")
        for x in self.nguoi_khong_du_dieu_kien:
            out.append((f"{', '.join(x['quy_tac'])}: " if hien_ma else "") + x["mo_ta"])
        return out

    def do_thi(self) -> dict:
        """Đồ thị suy luận {nodes, edges} (cho giao diện — Phase 7)."""
        nodes, edges, seen = [], [], set()

        def node(i, label, loai):
            if i not in seen:
                seen.add(i)
                nodes.append({"id": i, "label": label, "loai": loai})

        def duyet(n: Nut, cha: str):
            i = f"{n.loai}:{n.ten}"
            node(i, n.mo_ta, n.loai)
            edges.append({"from": i, "to": cha})
            for x in n.con:
                duyet(x, i)
        for k in self.ket_luan:
            hv = f"hanh_vi:{k.ma_hanh_vi}"
            node(hv, k.ten, "hanh_vi")
            dk = f"dieu_khoan:{k.dieu_khoan.id}"
            node(dk, k.dieu_khoan.trich_dan, "dieu_khoan")
            edges.append({"from": hv, "to": dk, "label": "áp dụng"})
            if k.muc_de_xuat:
                mp = f"muc:{k.ma_hanh_vi}"
                node(mp, f"Đề xuất {k.muc_de_xuat:,} đồng".replace(",", "."), "muc_phat")
                edges.append({"from": dk, "to": mp})
            for q in k.quy_tac:
                qi = f"quy_tac:{q.ma}"
                node(qi, f"{q.ma}: {q.mo_ta}", "quy_tac")
                edges.append({"from": qi, "to": hv, "label": "kết luận"})
                for n in q.dieu_kien:
                    duyet(n, qi)
        return {"nodes": nodes, "edges": edges}


def _mo_ta_cay(n: Nut, nguon: bool = False) -> str:
    """Cây điều kiện thành một dòng; ``nguon=True`` ghi nguồn của từng sự kiện lá (cho verbalizer)."""
    s = n.mo_ta
    if nguon and n.loai == "su_kien" and n.nguon:
        s += f" ({NGUON_CHU.get(n.nguon, n.nguon)}" + (f": “{n.bang_chung}”" if n.bang_chung and n.nguon in
                                                       ("suy_ra", "xac_nhan") else "") + ")"
    if not n.con:
        return s
    return f"{s} ← " + ", ".join(_mo_ta_cay(c, nguon) for c in n.con)


def doc_id(text: str, phien_ban: str, ngay: date | None) -> str:
    """Thay mã phần tử (LTTATGT-D34-K1-g) trong câu ghi chú bằng cách viết tiếng Việt (điểm g khoản 1 Điều 34 …)."""
    def thay(m):
        b = lay(m.group(0), phien_ban if m.group(0).startswith("ND") else None, ngay)
        return b.trich_dan if b else m.group(0)
    return RE_ID.sub(thay, text)


def _d(x) -> date | None:
    if x is None or isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10])


# ---------------------------------------------------------------------------
# Tri thức để giải thích
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _khai_niem() -> dict:
    cfg = yaml.safe_load((ROOT_DIR / "config" / "ontology_concepts.yaml").read_text(encoding="utf-8"))
    nguong = {t["name"]: t for t in cfg["thresholds"] + cfg.get("thresholds_luat", [])}
    hop = {u["name"]: u for u in cfg["unions"]}
    quan_sat = {o["name"]: o for o in cfg["observations"]}
    tinh_tiet = {f"DH_{t['fact']}": t for t in cfg["tinh_tiet_facts"]}
    return {"nguong": nguong, "hop": hop, "quan_sat": quan_sat, "tinh_tiet": tinh_tiet}


@lru_cache(maxsize=1)
def _nhan_ontology() -> tuple[dict[str, str], dict[str, str]]:
    """(nhãn lớp + cá thể, nhãn thuộc tính dữ liệu) từ traffic_law.owl — nạp một lần."""
    from src.kb.loader import load_world

    _, onto = load_world()
    lop = {c.name: str(c.label[0]) for c in onto.classes() if c.label}
    lop.update({i.name: str(i.label[0]) for i in onto.individuals() if getattr(i, "label", None)})
    tt = {p.name: str(p.label[0]) for p in onto.data_properties() if p.label}
    return lop, tt


def _nhan_lop() -> dict[str, str]:
    return _nhan_ontology()[0]


@lru_cache(maxsize=1)
def _tinh_tiet_cfg() -> dict[str, str]:
    """Cá thể tình tiết → id điều khoản (TTTN_b → LXLVPHC-D10-K1-b; TTGN_1 → LXLVPHC-D9-K1)."""
    cfg = yaml.safe_load((ROOT_DIR / "config" / "ontology_concepts.yaml").read_text(encoding="utf-8"))
    return {t["prefix"]: t["parent_id"] for t in cfg["tinh_tiet"]}


def id_tinh_tiet(ma: str) -> str:
    prefix, x = ma.split("_", 1)
    parent = _tinh_tiet_cfg()[prefix]
    return f"{parent}-{x}" if "-K" in parent else f"{parent}-K{x}"


@lru_cache(maxsize=1)
def _chuoi_phien_ban() -> dict[str, list[str]]:
    """V4 → [V4, V3]; V2 → [V2, V1] (phiên bản gốc để chọn bằng chứng ngưỡng)."""
    from src.kb.temporal import load_sources

    vs = load_sources()["versions"]
    def chain(v):
        b = (vs[v].get("build") or {}).get("base_version")
        return [v] + (chain(b) if b else [])
    return {v: chain(v) for v in vs}


RE_GHI_CHU_NHAN = re.compile(r"\s*\((?=[^)]*(?:Điều|NĐ|V\d))[^)]*\)")


def sach(nhan_: str) -> str:
    """Bỏ ghi chú kỹ thuật trong ngoặc của nhãn ("(đối tượng Điều 6 NĐ 100 / …)", "(V1–V3: …)") — tránh để
    verbalizer chép tham chiếu không thuộc vụ việc."""
    return RE_GHI_CHU_NHAN.sub("", nhan_).strip()


def nhan(ten: str) -> str:
    return sach(_nhan_lop().get(ten, ten))


def _bang_chung_nguong(t: dict, phien_ban: str, ngay: date | None) -> list[CanCu]:
    evs = t.get("evidence") or []
    chain = _chuoi_phien_ban().get(phien_ban, [phien_ban])
    chon = [e for v in chain for e in evs if e.get("version") == v]
    if not chon:                                   # văn bản bổ trợ (LXLVPHC, LTTATGT_*, GTDB2008)
        for e in evs:
            b = lay(e["id"], None, ngay)
            if b and (b.hieu_luc_tu is None or ngay is None or _d(b.hieu_luc_tu) <= ngay) and \
                    (b.hieu_luc_den is None or ngay is None or ngay <= _d(b.hieu_luc_den)):
                chon = [e]
                break
    out = []
    for e in chon[:1]:
        b = lay(e["id"], phien_ban if e["id"].startswith("ND") else None, ngay)
        out.append(CanCu(e["id"], b.trich_dan if b else e["id"], e["phrase"]))
    return out


# ---------------------------------------------------------------------------
# Dựng trace
# ---------------------------------------------------------------------------

class _Dung:
    def __init__(self, kq):
        self.kq, self.sl, self.qd, self.dl, self.hs = kq, kq.suy_luan, kq.quyet_dinh, kq.du_lieu, kq.ho_so
        self.case = self.dl.case
        self.v = self.sl.phien_ban
        self.ngay = _d(self.case.get("ngay"))
        from src.kb.rules_builder import load_registry

        self.reg = load_registry()
        self.suy_ra = {s.thuoc_tinh: s for s in self.hs.su_kien_suy_ra}
        self.dk_hien_tai: CanCu | None = None

    # ---- sự kiện ----
    def su_kien(self, prop: str, gia_tri, vai: str = "h") -> Nut:
        nguon = self.dl.nguon_su_kien.get(prop, "truc_tiep")
        bang_chung, can_cu = None, []
        if prop == "tocDoVuot":
            nguon = "tinh_toan"
        elif nguon in ("suy_ra", "xac_nhan") and (s := self.suy_ra.get(prop)):
            bang_chung = s.bang_chung
            for i in RE_ID.findall(s.giai_thich):
                if b := lay(i, None, self.ngay):
                    can_cu.append(CanCu(i, b.trich_dan, b.text))
        elif nguon == "tra_bang":
            can_cu = [CanCu(c["id"], lay(c["id"], None, self.ngay).trich_dan, c["nguyen_van"])
                      for c in self.dl.can_cu_bo_tro]
        else:
            f = TRUONG_HO_SO.get(prop) or ("tuoi_nguoi_lai" if prop == "tuoi" and vai != "n_chu" else
                                           "tuoi_chu_xe" if prop == "tuoi" else None)
            g = self.hs.nguon.get(f) if f else self.hs.nguon.get(f"su_kien.{prop}")
            bang_chung = g.goc if g else None
        mo_ta = f"{nhan_thuoc_tinh(prop)} = {_gia_tri(gia_tri)}"
        return Nut("su_kien", prop, mo_ta, gia_tri, nguon, bang_chung, can_cu)

    def gia_tri(self, prop: str, vai: str):
        if vai == "h":
            sk = self.case.get("su_kien") or {}
            if prop == "tocDoVuot" and sk.get("tocDoThucTe") is not None and sk.get("tocDoToiDaChoPhep") is not None:
                return float(sk["tocDoThucTe"]) - float(sk["tocDoToiDaChoPhep"])
            return sk.get(prop)
        if vai == "x":
            return (self.case.get("xe_tt") or {}).get(prop)
        if vai == "n":
            return (self.case.get("nguoi") or {}).get(prop)
        if vai == "n_chu":
            return (self.case.get("chu_xe") or {}).get(prop)
        return None

    # ---- điều kiện ----
    def giai_thich(self, lop: str, vai: str, ca_the: str) -> Nut:
        kn = _khai_niem()
        if lop in kn["nguong"]:
            t = kn["nguong"][lop]
            val = self.gia_tri(t["property"], vai)
            # Bằng chứng ngưỡng: ưu tiên chính điều khoản của kết luận nếu nó chứa câu ngưỡng
            dk = self.dk_hien_tai
            if dk and any(e["phrase"] in dk.nguyen_van for e in t.get("evidence") or []):
                ev = [CanCu(dk.id, dk.trich_dan, next(e["phrase"] for e in t["evidence"] if e["phrase"] in dk.nguyen_van))]
            else:
                ev = _bang_chung_nguong(t, self.v, self.ngay)
            n = Nut("nguong" if t.get("cls") != "Nguoi" else "do_tuoi", lop, sach(t["label"]), can_cu=ev)
            if val is not None:
                n.con.append(self.su_kien(t["property"], val, vai))
                if t["property"] == "tocDoVuot":
                    sk = self.case["su_kien"]
                    n.con[0].con = [self.su_kien("tocDoThucTe", sk["tocDoThucTe"]),
                                    self.su_kien("tocDoToiDaChoPhep", sk["tocDoToiDaChoPhep"])]
            return n
        if lop in kn["hop"]:
            u = kn["hop"][lop]
            co = set(self.sl.lop_suy_ra.get(ca_the, []))
            con = [self.giai_thich(m, vai, ca_the) for m in u["of"] if m in co]
            return Nut("hop", lop, sach(u["label"]), con=con)
        if lop in kn["quan_sat"]:
            o = kn["quan_sat"][lop]
            con = [self.su_kien(p, v) for p, v in o["values"].items()]
            for p, c in (o.get("some") or {}).items():
                con.append(Nut("lop", c, f"{nhan(c)} (đường của vụ việc)"))
            return Nut("dau_hieu", lop, sach(o["label"]), con=con)
        if lop in kn["tinh_tiet"]:
            t = kn["tinh_tiet"][lop]
            return Nut("dau_hieu", lop, sach(t["label"]), con=[self.su_kien(t["fact"], True)])
        if lop.startswith("HV_"):
            ma = lop[3:]
            qs = [q for k in self.sl.ket_luan if k.ma_hanh_vi == ma for q in k.quy_tac]
            return Nut("hanh_vi", ma, f"đã kết luận: {nhan(lop)}", gia_tri=qs)       # mã quy tắc để ở gia_tri, không vào câu chữ
        if vai == "x":
            xe = self.case.get("xe")
            n = Nut("phuong_tien", lop, f"{nhan(lop)}")
            n.con.append(Nut("su_kien", "loai_xe", f"Phương tiện: {nhan(xe)}", xe, *self._nguon_xe()))
            return n
        return Nut("lop", lop, nhan(lop))

    def _nguon_xe(self):
        g = self.hs.nguon.get("loai_xe")
        if g is None:
            return "truc_tiep", None, []
        can_cu = []
        for gc in g.ghi_chu:
            for i in RE_ID.findall(gc):
                if b := lay(i, None, self.ngay):
                    can_cu.append(CanCu(i, b.trich_dan, b.text))
        return ("xep_loai" if g.phuong_phap == "suy_ra" else "truc_tiep"), g.goc, can_cu

    def buoc(self, ma: str, ca_the: dict[str, str]) -> BuocQuyTac:
        r = self.reg["quy_tac"][ma]
        than = r["swrl"].split("->")[0]
        dk = []
        for lop, var in RE_ATOM.findall(than):
            if lop in KHUNG:
                continue
            vai = {"h": "h", "x": "x", "n": ca_the["vai_n"], "m": "n"}.get(var, var)
            dk.append(self.giai_thich(lop, vai, ca_the.get(var, "")))
        return BuocQuyTac(ma, r.get("mo_ta", ""), dk)

    def ca_the(self, hanh_vi_thuc_te: str) -> dict[str, str]:
        cid = hanh_vi_thuc_te.rsplit("_hanh_vi_", 1)[0]
        if hanh_vi_thuc_te.endswith("giao_xe"):
            return {"h": hanh_vi_thuc_te, "x": f"{cid}_xe", "n": f"{cid}_chu_xe", "m": f"{cid}_nguoi_lai",
                    "vai_n": "n_chu"}
        return {"h": hanh_vi_thuc_te, "x": f"{cid}_xe", "n": f"{cid}_nguoi_lai", "vai_n": "n"}

    def dung(self) -> Trace:
        sl, qd = self.sl, self.qd
        kl_theo_ma = {k.ma_hanh_vi: k for k in sl.hanh_vi}
        tt_nhan = {t["tinh_tiet"]: t for t in sl.tinh_tiet}
        ket_luan = []
        for d in qd.hanh_vi:
            k = kl_theo_ma.get(d.ma_hanh_vi)
            ct = self.ca_the(k.hanh_vi_thuc_te) if k else {}
            dk_id = d.dieu_khoan_id
            nv = d.can_cu[0]["nguyen_van"] if d.can_cu else ""
            self.dk_hien_tai = CanCu(dk_id, d.dieu_khoan, nv)
            buoc = [self.buoc(q, ct) for q in (k.quy_tac if k else [])]
            self.dk_hien_tai = None
            che_tai = [{"loai": c.loai, "gia_tri": c.gia_tri, "dieu_kien": c.dieu_kien, "trang_thai": c.trang_thai,
                        "can_cu_id": c.can_cu_id, "trich_dan": _trich(c.can_cu_id, self.v, self.ngay),
                        "nguyen_van": c.nguyen_van} for c in d.che_tai]
            khac = [CanCu(c["id"], _trich(c["id"], self.v, self.ngay), c["nguyen_van"]) for c in d.can_cu[1:]]

            def tinh_tiet(ma):
                t = tt_nhan.get(ma, {})
                b = lay(id_tinh_tiet(ma), None, self.ngay)
                # sự kiện làm phát sinh tình tiết (vd. thanhThatHoiLoi) + nguồn: bạn nêu / suy ra từ lời kể "…"
                qs = [self.reg["quy_tac"][q] for q in t.get("quy_tac", []) if q in self.reg["quy_tac"]]
                sk = [asdict(self.su_kien(q["su_kien"], True)) for q in qs if q.get("su_kien")]
                return {"ma": ma, "quy_tac": t.get("quy_tac", []), "nhan": "; ".join(dict.fromkeys(
                            q["mo_ta"] for q in qs)) or nhan(ma), "su_kien": sk,
                        "can_cu": asdict(CanCu(b.id, b.trich_dan, b.text)) if b else None}
            tang, giam = [tinh_tiet(t) for t in d.tinh_tiet_tang], [tinh_tiet(t) for t in d.tinh_tiet_giam]
            ket_luan.append(KetLuanTrace(
                d.ma_hanh_vi, sach(d.ten), buoc, CanCu(dk_id, d.dieu_khoan, nv), d.hinh_thuc_chinh,
                list(d.khung_phat) if d.khung_phat else None, d.muc_de_xuat, _ly_do_kem_nguon(d.ly_do, tang, giam),
                che_tai, d.tru_diem, tang, giam, khac))

        loai_tru = []
        for k in sl.ket_luan:
            if k.bi_loai_tru_boi:
                ld = k.ly_do_loai_tru or {}
                cc = [{"id": ld["id"], "trich_dan": _trich(ld["id"], self.v, self.ngay),
                       "nguyen_van": ld.get("nguyen_van", "")}] if ld.get("id") else []
                loai_tru.append({"ma_hanh_vi": k.ma_hanh_vi, "ten": nhan(f"HV_{k.ma_hanh_vi}"),
                                 "boi": k.bi_loai_tru_boi, "ly_do": ld.get("nguyen_van", ""), "can_cu": cc})
        khong_du = []
        for p in sl.nguoi_khong_du_dieu_kien:
            buoc = [self.buoc(q, {"h": f"{p['nguoi'].rsplit('_', 2)[0]}_hanh_vi_lai", "vai_n": "n",
                                  "x": f"{p['nguoi'].rsplit('_', 2)[0]}_xe"}) for q in p["quy_tac"]]
            khong_du.append({"nguoi": p["nguoi"], "quy_tac": p["quy_tac"],
                             "mo_ta": "Người không đủ điều kiện điều khiển xe ← " +
                                      "; ".join(_mo_ta_cay(n) for b in buoc for n in b.dieu_kien),
                             "dieu_kien": [asdict(n) for b in buoc for n in b.dieu_kien], "can_cu": []})

        su_kien = [self.su_kien(p, v) for p, v in (self.case.get("su_kien") or {}).items()]
        xe = self.case.get("xe")
        su_kien.insert(0, Nut("su_kien", "loai_xe", f"Phương tiện: {nhan(xe)}", xe, *self._nguon_xe()))
        if self.case.get("nguoi", {}).get("tuoi") is not None:
            su_kien.append(self.su_kien("tuoi", self.case["nguoi"]["tuoi"], "n"))
        for dg in self.case.get("duong") or []:
            su_kien.append(Nut("su_kien", "loai_duong", f"Đường: {nhan(dg)}", dg, "truc_tiep"))

        pb = {"ma": self.v, "ghi_chu": sl.ghi_chu_phien_ban, "mac_dinh": sl.mac_dinh_phien_ban,
              "ngay": self.ngay.isoformat() if self.ngay else None, "van_ban": _van_ban_phien_ban(self.v)}
        chung = [CanCu(c["id"], _trich(c["id"], self.v, self.ngay), c["nguyen_van"]) for c in qd.can_cu_chung]
        ghi_chu = list(dict.fromkeys(doc_id(g, self.v, self.ngay) for g in self.kq.ghi_chu + qd.ghi_chu))
        return Trace(pb, su_kien, ket_luan, loai_tru, khong_du, qd.tong_tien_de_xuat, qd.tru_diem_ap_dung,
                     ghi_chu, chung)


def _ly_do_kem_nguon(ly_do: list[str], tang: list[dict], giam: list[dict]) -> list[str]:
    """Dòng "Tình tiết giảm nhẹ: …" của penalty + nguồn của sự kiện làm phát sinh tình tiết
    ("hệ thống suy ra từ lời kể: “…”" / "bạn nêu: “…”")."""
    out = list(ly_do)
    for nhom, ds in (("tăng nặng", tang), ("giảm nhẹ", giam)):
        for t in ds:
            sk = next((s for s in t.get("su_kien") or [] if s.get("nguon")), None)
            if sk is None:
                continue
            nguon = {"suy_ra": "hệ thống suy ra từ lời kể", "xac_nhan": "bạn đã xác nhận"}.get(sk["nguon"], "bạn nêu")
            them = f" — {nguon}" + (f": “{sk['bang_chung']}”" if sk.get("bang_chung") else "")
            ten = t["nhan"][:1].lower() + t["nhan"][1:]
            for i, dong in enumerate(out):
                if dong.startswith(f"Tình tiết {nhom}: {ten}") and them not in dong:
                    out[i] = dong + them
                    break
    return out


def _trich(id_: str, v: str, ngay: date | None) -> str:
    b = lay(id_, v if id_.startswith("ND") else None, ngay)
    return b.trich_dan if b else id_


@lru_cache(maxsize=None)
def _van_ban_phien_ban(v: str) -> list[str]:
    """Các nghị định tạo nên phiên bản (vd. V4 → [ND168, ND238])."""
    from src.kb.temporal import load_sources

    vs = load_sources()["versions"]
    b = vs[v].get("build") or {}
    base = [b["base"]] if b.get("base") else _van_ban_phien_ban(b["base_version"])
    return list(base) + list(b.get("amendments") or [])


NHAN_RIENG = {"loai_xe": "Phương tiện", "tocDoVuot": "Mức vượt tốc độ (km/h)"}


def nhan_thuoc_tinh(p: str) -> str:
    return NHAN_RIENG.get(p) or _nhan_ontology()[1].get(p, p)


def _gia_tri(v) -> str:
    if isinstance(v, bool):
        return "có" if v else "không"
    if isinstance(v, float) and v.is_integer():
        return f"{int(v)}"
    return str(v).replace(".", ",") if isinstance(v, float) else str(v)


def dung_trace(kq) -> Trace:
    """Trace của một lượt đã có kết luận (``kq.trang_thai`` ∈ {ket_luan, khong_phat_hien})."""
    return _Dung(kq).dung()


__all__ = ["CanCu", "Nut", "BuocQuyTac", "KetLuanTrace", "Trace", "dung_trace", "trich_dan", "nhan"]
