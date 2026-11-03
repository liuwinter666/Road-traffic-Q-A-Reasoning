"""Suy ra sự kiện gián tiếp từ lời kể (Bài toán 1 — phần LLM).

Ví dụ "thấy CSGT vẫy thì rồ ga chạy" → coHieuLenhDungXe = true, chapHanhHieuLenh = false, boChay = true.

LLM chỉ nêu SỰ KIỆN (thuộc tính boolean của ontology) kèm độ tin cậy và đoạn trích làm bằng chứng; hành vi
vi phạm, điều khoản, mức phạt vẫn do reasoner kết luận từ các sự kiện đó. Sau LLM là các bước tất định:

  1. Thuộc tính phải thuộc danh mục (lấy từ ontology: thuộc tính dữ liệu boolean trên HanhViDieuKhienXe/HanhVi,
     trừ ``khong_suy_ra`` trong ``config/fact_inducer.yaml``) — JSON schema dùng enum nên LLM không chọn ngoài.
  2. Bằng chứng phải có trong lời người dùng (khớp ≥ ``ty_le_khop_bang_chung`` theo từ, bỏ dấu).
  3. Sự kiện trực tiếp (người dùng nói / từ điển) luôn thắng; suy ra trái với sự kiện trực tiếp → ``xung_dot``.
  4. Độ tin cậy ≥ ``nguong_chap_nhan`` → dùng ngay; trong [``nguong_hoi_lai``, ``nguong_chap_nhan``) hoặc thuộc
     ``luon_hoi_lai`` → chờ người dùng xác nhận (slot_checker sinh câu hỏi); thấp hơn → bỏ.
  5. Sự kiện người dùng đã xác nhận/bác bỏ ở lượt trước không bị LLM ghi đè.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Literal

import yaml
from loguru import logger
from pydantic import BaseModel, Field, create_model

from src.config import ROOT_DIR
from src.extraction.grounding import _tu, tap_tu
from src.extraction.schema import HoSoVuViec, NguonGoc, SuKienSuyRa
from src.llm.client import LLMClient, get_llm_client
from src.llm.prompts import load_prompt

CONFIG_FILE = ROOT_DIR / "config" / "fact_inducer.yaml"
ONTOLOGY_FILE = ROOT_DIR / "ontology" / "traffic_law.owl"
MIEN_CHO_PHEP = {"HanhViDieuKhienXe", "HanhVi"}


@lru_cache(maxsize=1)
def cau_hinh() -> dict:
    return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def danh_muc() -> dict[str, str]:
    """{thuộc tính: nhãn tiếng Việt} — thuộc tính boolean của ontology mà LLM được phép suy ra."""
    from src.kb.loader import load_world

    _, onto = load_world(ONTOLOGY_FILE)
    out = {}
    for p in onto.data_properties():
        if bool in p.range and {d.name for d in p.domain} & MIEN_CHO_PHEP:
            out[p.name] = str(p.label[0]) if p.label else p.name
    for x in cau_hinh().get("khong_suy_ra") or []:
        out.pop(x, None)
    return dict(sorted(out.items()))


@lru_cache(maxsize=1)
def schema_llm() -> type[BaseModel]:
    """Schema đầu ra của LLM; ``thuoc_tinh`` là enum theo danh mục (Gemini JSON schema mode ép đúng)."""
    ten = tuple(danh_muc())
    item = create_model(
        "SuKienSuyRaLLM",
        thuoc_tinh=(Literal[ten], Field(description="Tên thuộc tính trong danh mục")),       # type: ignore[valid-type]
        gia_tri=(bool, Field(description="true/false")),
        do_tin_cay=(float, Field(ge=0, le=1, description="Độ tin cậy 0–1")),
        bang_chung=(str, Field(description="Đoạn trích nguyên văn lời người dùng làm căn cứ")),
        giai_thich=(str, Field("", description="Một câu ngắn vì sao đoạn trích hàm ý sự kiện")),
    )
    return create_model("KetQuaSuyRaLLM", su_kien=(list[item], Field(default_factory=list)))  # type: ignore[valid-type]


@lru_cache(maxsize=None)
def _ban_ghi_bo_tro(khoa: str) -> dict[str, dict]:
    import json

    from src.config import PROCESSED_DIR

    with (PROCESSED_DIR / f"support_{khoa.lower()}.jsonl").open(encoding="utf-8") as f:
        return {r["id"]: r for r in map(json.loads, f)}


def dinh_nghia_phap_ly(ngay: date) -> list[dict]:
    """Định nghĩa đính kèm prompt: [{thuoc_tinh, id, van_ban, nguyen_van}] — văn bản có hiệu lực tại ``ngay``."""
    from src.kb.temporal import chon_van_ban_bo_tro

    out = []
    for d in cau_hinh().get("dinh_nghia") or []:
        vb = chon_van_ban_bo_tro(d["vai_tro"], ngay)
        rid = d["id"].get(vb.van_ban) if vb.van_ban else None
        rec = _ban_ghi_bo_tro(vb.khoa).get(rid) if rid else None
        if rec is None:
            logger.warning("Không tìm thấy định nghĩa {} cho {} ngày {}", d["vai_tro"], d["thuoc_tinh"], ngay)
            continue
        out.append({"thuoc_tinh": list(d["thuoc_tinh"]), "id": rid, "van_ban": vb.khoa,
                    "nguyen_van": rec["text"].strip()})
    return out


def ty_le_khop(doan: str, tap: set[str]) -> float:
    ws = _tu(doan)
    return sum(w in tap for w in ws) / len(ws) if ws else 0.0


@dataclass
class FactInducer:
    """Gọi LLM suy ra sự kiện gián tiếp rồi áp vào hồ sơ vụ việc."""

    client: LLMClient | None = None
    prompt_version: int | None = None

    def __post_init__(self):
        self.client = self.client or get_llm_client()
        self.prompt = load_prompt("fact_induction", self.prompt_version)

    # ---- LLM ----
    def goi_llm(self, loi_ke: list[str], hs: HoSoVuViec, hom_nay: date | None = None) -> list[dict]:
        dm = danh_muc()
        system = self.prompt.system + "\n\nDANH MỤC thuộc tính (tên: ý nghĩa khi giá trị true):\n" + "\n".join(
            f"- {k}: {v}" for k, v in dm.items())
        dn = dinh_nghia_phap_ly(_ngay(hs, hom_nay))
        if dn:
            system += "\n\nĐỊNH NGHĨA PHÁP LÝ (trích nguyên văn):\n" + "\n".join(
                f"- [{d['id']}] {d['nguyen_van']} (liên quan: {', '.join(d['thuoc_tinh'])})" for d in dn)
        da_biet = "\n".join(f"- {k} = {str(v).lower()}" for k, v in sorted(hs.su_kien.items()) if k in dm) or "(chưa có)"
        prompt = self.prompt.render(da_biet=da_biet, loi_ke="\n".join(f"[{i + 1}] {m}" for i, m in enumerate(loi_ke)))
        out = self.client.generate_structured(prompt, schema_llm(), system=system)
        ds = [x.model_dump() for x in out.su_kien]
        logger.debug("Suy ra ({}): {}", self.prompt.ma, ds)
        return ds

    # ---- tất định ----
    @staticmethod
    def ap_dung(hs: HoSoVuViec, ds: list[dict], loi_ke: list[str], hom_nay: date | None = None) -> list[SuKienSuyRa]:
        """Phân loại từng sự kiện LLM nêu và cập nhật ``hs`` (su_kien, nguon, su_kien_suy_ra). Trả các bản ghi mới."""
        cfg, dm = cau_hinh(), danh_muc()
        tap = tap_tu("\n".join(loi_ke))
        dinh_nghia = dinh_nghia_phap_ly(_ngay(hs, hom_nay))
        cu = {x.thuoc_tinh: x for x in hs.su_kien_suy_ra}
        moi: list[SuKienSuyRa] = []
        for d in ds:
            t = d["thuoc_tinh"]
            if t not in dm:
                continue
            truoc = cu.get(t)
            if truoc and truoc.trang_thai in ("xac_nhan", "tu_choi", "chap_nhan"):
                continue                                   # đã chốt ở lượt trước
            sk = SuKienSuyRa(thuoc_tinh=t, gia_tri=bool(d["gia_tri"]), do_tin_cay=float(d["do_tin_cay"]),
                             bang_chung=d.get("bang_chung", ""), giai_thich=d.get("giai_thich", ""), nhan=dm[t])
            if can_cu := [x["id"] for x in dinh_nghia if t in x["thuoc_tinh"]]:
                sk.giai_thich = (sk.giai_thich + " " if sk.giai_thich else "") + f"(định nghĩa: {', '.join(can_cu)})"
            nguon = hs.nguon.get(f"su_kien.{t}")
            truc_tiep = t in hs.su_kien and (nguon is None or nguon.phuong_phap != "suy_ra")
            if truc_tiep:
                if hs.su_kien[t] == sk.gia_tri:
                    continue                               # trùng sự kiện trực tiếp — không cần ghi
                sk.trang_thai = "xung_dot"
            elif ty_le_khop(sk.bang_chung, tap) < cfg["ty_le_khop_bang_chung"]:
                sk.trang_thai = "khong_can_cu"
            elif sk.do_tin_cay < cfg["nguong_hoi_lai"]:
                sk.trang_thai = "tin_cay_thap"
            elif sk.do_tin_cay < cfg["nguong_chap_nhan"] or t in (cfg.get("luon_hoi_lai") or []):
                sk.trang_thai = "cho_xac_nhan"
            else:
                sk.trang_thai = "chap_nhan"
            if sk.trang_thai != "chap_nhan":
                logger.info("Sự kiện suy ra {} = {} ({:.2f}): {}", t, sk.gia_tri, sk.do_tin_cay, sk.trang_thai)
            cu[t] = sk
            moi.append(sk)
        hs.su_kien_suy_ra = list(cu.values())
        dong_bo_su_kien(hs)
        return moi

    def suy_ra(self, hs: HoSoVuViec, loi_ke: list[str], hom_nay: date | None = None) -> list[SuKienSuyRa]:
        """Gọi LLM và áp kết quả vào ``hs``."""
        return self.ap_dung(hs, self.goi_llm(loi_ke, hs, hom_nay), loi_ke, hom_nay)


def _ngay(hs: HoSoVuViec, hom_nay: date | None) -> date:
    return hs.ngay_vi_pham or hs.ngay_tu or hom_nay or date.today()


def dong_bo_su_kien(hs: HoSoVuViec) -> None:
    """Đưa sự kiện suy ra đang áp dụng (chấp nhận / người dùng xác nhận) vào ``hs.su_kien``; gỡ các sự kiện suy ra
    không còn áp dụng (vd. người dùng bác bỏ). Không động tới sự kiện trực tiếp."""
    for sk in hs.su_kien_suy_ra:
        key = f"su_kien.{sk.thuoc_tinh}"
        nguon = hs.nguon.get(key)
        cua_suy_ra = nguon is not None and nguon.phuong_phap in ("suy_ra", "nguoi_dung_xac_nhan")
        if sk.dang_ap_dung:
            if sk.thuoc_tinh in hs.su_kien and not cua_suy_ra:
                continue
            hs.su_kien[sk.thuoc_tinh] = sk.gia_tri
            hs.nguon[key] = NguonGoc(goc=sk.bang_chung,
                                     phuong_phap="nguoi_dung_xac_nhan" if sk.trang_thai == "xac_nhan" else "suy_ra",
                                     do_tin_cay=sk.do_tin_cay, ghi_chu=[sk.giai_thich] if sk.giai_thich else [])
        elif cua_suy_ra:
            hs.su_kien.pop(sk.thuoc_tinh, None)
            hs.nguon.pop(key, None)
