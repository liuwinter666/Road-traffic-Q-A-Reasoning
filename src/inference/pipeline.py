"""Pipeline đầu-cuối cho một lượt hội thoại (mục 8 đặc tả, bước 2–6).

    tin nhắn ─► [trả lời xác nhận có/không?] ─► llm_extractor (+ grounding, normalizer, entity_linker)
             ─► fact_inducer (sự kiện gián tiếp) ─► slot_checker ──thiếu──► câu hỏi làm rõ (dừng)
                                                                └─đủ──► fact_builder ─► reasoner (HermiT, theo phiên bản)
                                                                        ─► penalty.quyet_dinh ─► kết quả có truy vết

LLM chỉ ở bước trích xuất và suy ra sự kiện; từ fact_builder trở đi hoàn toàn tất định. Trạng thái nhiều lượt
nằm trong ``PhienLamViec`` (hồ sơ Pydantic + lời kể + câu hỏi vừa hỏi); Phase 7 (dialogue manager) dùng lại.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date

from loguru import logger

from src.extraction import normalizer as N
from src.extraction.llm_extractor import LLMExtractor, xep_loai_xe
from src.extraction.schema import HoSoVuViec, NguonGoc
from src.extraction.slot_checker import CauHoi, cho_xac_nhan_lien_ket, kiem_tra, loai_xe_cho_xac_nhan
from src.inference.fact_builder import DuLieuVuViec, xay_dung
from src.inference.fact_inducer import FactInducer, dong_bo_su_kien
from src.llm.client import LLMClient, LLMError, get_llm_client

CO = {"có", "đúng", "phải", "ừ", "ừm", "uh", "vâng", "dạ", "ok", "okay", "yes", "chuẩn", "co", "phai", "u", "vang"}
KHONG = {"không", "sai", "chưa", "ko", "k", "no", "hông", "khong", "chua"}
CO_2 = {"chính xác", "chinh xac", "đúng rồi", "dung roi", "dung vay", "đúng vậy"}
KHONG_2 = {"không phải", "khong phai", "không đúng", "khong dung", "chưa đúng"}


def tra_loi_co_khong(tin_nhan: str) -> tuple[bool | None, int]:
    """(True/False nếu tin nhắn mở đầu bằng đồng ý/phủ nhận, None nếu không) + số từ còn lại sau câu trả lời.

    So khớp trên chữ CÓ DẤU trước ("dừng" ≠ "đúng"); dạng không dấu chỉ nhận các từ ít nhập nhằng."""
    ws = re.findall(r"\w+", N.chuan_hoa_chu(tin_nhan))
    if not ws:
        return None, 0
    hai = " ".join(ws[:2])
    if hai in KHONG_2:
        return False, len(ws) - 2
    if hai in CO_2:
        return True, len(ws) - 2
    if ws[0] in KHONG:
        return False, len(ws) - 1
    if ws[0] in CO or ws[0] == "dung" and len(ws) <= 2:
        return True, len(ws) - 1
    return None, len(ws)


@dataclass
class PhienLamViec:
    """Trạng thái một cuộc hội thoại về MỘT vụ việc."""

    ho_so: HoSoVuViec = field(default_factory=HoSoVuViec)
    loi_ke: list[str] = field(default_factory=list)          # tin nhắn có nội dung (không tính "có"/"không")
    cau_hoi_truoc: list[CauHoi] = field(default_factory=list)
    so_luot: int = 0


@dataclass
class KetQuaLuot:
    trang_thai: str                                           # can_hoi | ket_luan | khong_phat_hien
    ho_so: HoSoVuViec
    cau_hoi: list[CauHoi] = field(default_factory=list)
    du_lieu: DuLieuVuViec | None = None
    suy_luan: object | None = None                            # kb.reasoner.KetQuaSuyLuan
    quyet_dinh: object | None = None                          # kb.penalty.QuyetDinh
    ghi_chu: list[str] = field(default_factory=list)
    thoi_gian_s: dict[str, float] = field(default_factory=dict)
    trace: object | None = None                               # explanation.tracer.Trace
    tra_loi: str = ""                                         # câu trả lời cuối (verbalizer hoặc tất định)
    dien_dat: object | None = None                            # explanation.verbalizer.KetQuaDienDat
    lien_quan: list = field(default_factory=list)             # gợi ý RAG khi không phát hiện vi phạm


class Pipeline:
    """Ghép các tầng; dùng chung một reasoner (khởi tạo Java/sổ đăng ký một lần)."""

    def __init__(self, client: LLMClient | None = None, extractor: LLMExtractor | None = None,
                 inducer: FactInducer | None = None, reasoner=None, dung_fact_inducer: bool = True,
                 hom_nay: date | None = None, verbalizer=None, dung_dien_dat: bool = True, retriever=None,
                 dung_goi_y_lien_quan: bool = True):
        self._client = client
        self._extractor, self._inducer, self._reasoner = extractor, inducer, reasoner
        self._verbalizer, self._retriever = verbalizer, retriever
        self.dung_fact_inducer = dung_fact_inducer
        self.dung_dien_dat = dung_dien_dat
        self.dung_goi_y_lien_quan = dung_goi_y_lien_quan
        self.hom_nay = hom_nay

    # Khởi tạo lười: chạy test/CLI chỉ dựng tầng cần dùng
    @property
    def client(self) -> LLMClient:
        if self._client is None:
            self._client = get_llm_client()
        return self._client

    @property
    def extractor(self) -> LLMExtractor:
        if self._extractor is None:
            self._extractor = LLMExtractor(client=self.client)
        return self._extractor

    @property
    def inducer(self) -> FactInducer:
        if self._inducer is None:
            self._inducer = FactInducer(client=self.client)
        return self._inducer

    @property
    def verbalizer(self):
        if self._verbalizer is None:
            from src.explanation.verbalizer import Verbalizer

            self._verbalizer = Verbalizer(client=self.client)
        return self._verbalizer

    @property
    def retriever(self):
        if self._retriever is None:
            from src.explanation.retriever import retriever_mac_dinh

            self._retriever = retriever_mac_dinh()
        return self._retriever

    @property
    def reasoner(self):
        if self._reasoner is None:
            from src.kb.reasoner import TrafficReasoner

            self._reasoner = TrafficReasoner()
        return self._reasoner

    # ------------------------------------------------------------------
    def xu_ly(self, phien: PhienLamViec, tin_nhan: str, ngay_vi_pham: date | None = None) -> KetQuaLuot:
        """Xử lý một tin nhắn của người dùng trong ``phien`` (cập nhật ``phien`` tại chỗ)."""
        today = self.hom_nay or date.today()
        tg: dict[str, float] = {}
        canh_bao: list[str] = []
        phien.so_luot += 1
        hs = phien.ho_so

        # 1. Trả lời câu hỏi xác nhận ("có"/"không")?
        da_hoi_xn = any(q.truong == "xac_nhan" for q in phien.cau_hoi_truoc)
        tra_loi, con_lai = tra_loi_co_khong(tin_nhan) if da_hoi_xn else (None, 0)
        if tra_loi is not None:
            muc = [m for q in phien.cau_hoi_truoc if q.truong == "xac_nhan" for m in q.muc_xac_nhan]
            self._ap_dung_xac_nhan(hs, tra_loi, set(muc))
        co_noi_dung = tra_loi is None or con_lai >= 3

        # 2. Trích xuất + chuẩn hóa + liên kết
        if co_noi_dung:
            t0 = time.perf_counter()
            moi = self.extractor.ho_so(tin_nhan, today, [q.cau_hoi for q in phien.cau_hoi_truoc])
            hs = phien.ho_so = hs.cap_nhat(moi)
            # loại xe và dung tích có thể đến ở hai lượt khác nhau → xếp loại lại trên hồ sơ đã gộp
            if xep_loai_xe(hs, today):
                hs.gia_dinh = list(dict.fromkeys(hs.gia_dinh + hs.nguon["loai_xe"].ghi_chu))
            phien.loi_ke.append(tin_nhan)
            tg["trich_xuat"] = time.perf_counter() - t0

            # 3. Sự kiện gián tiếp
            if self.dung_fact_inducer:
                t0 = time.perf_counter()
                try:
                    self.inducer.suy_ra(hs, phien.loi_ke, today)
                except LLMError as e:
                    # Không suy ra được thì vẫn kết luận từ sự kiện trực tiếp — và nói rõ điều đó
                    logger.warning("fact_inducer lỗi, bỏ qua bước suy ra: {}", e)
                    canh_bao.append("Không suy ra được sự kiện gián tiếp ở lượt này (lỗi LLM) — kết quả chỉ dựa "
                                    "trên các sự kiện bạn nêu trực tiếp.")
                tg["suy_ra_su_kien"] = time.perf_counter() - t0
        return self._ket_luan(phien, today, tg, canh_bao, ngay_vi_pham)

    def chay_lai(self, phien: PhienLamViec, ngay_vi_pham: date | None = None) -> KetQuaLuot:
        """Chạy lại từ bước kiểm tra thiếu thông tin trên hồ sơ hiện có — KHÔNG gọi LLM trích xuất/suy ra (dùng sau
        khi người dùng sửa bảng sự kiện trên giao diện)."""
        return self._ket_luan(phien, self.hom_nay or date.today(), {}, [], ngay_vi_pham)

    def _ket_luan(self, phien: PhienLamViec, today: date, tg: dict[str, float], canh_bao: list[str],
                  ngay_vi_pham: date | None) -> KetQuaLuot:
        """Bước 4–7: hỏi nếu thiếu → fact_builder → reasoner → quyết định → giải thích."""
        hs = phien.ho_so
        if ngay_vi_pham is not None:                           # ngày người dùng chọn trên giao diện / CLI
            hs.ngay_tu = hs.ngay_den = ngay_vi_pham
            hs.do_chinh_xac_ngay = "ngay"
            hs.nguon["ngay"] = NguonGoc(goc=ngay_vi_pham.isoformat(), phuong_phap="nguoi_dung")

        # 4. Thiếu thông tin → hỏi
        slot = kiem_tra(hs, today)
        phien.cau_hoi_truoc = slot.cau_hoi
        if not slot.du_thong_tin:
            from src.inference.report import trinh_bay

            kq = KetQuaLuot("can_hoi", hs, slot.cau_hoi, ghi_chu=canh_bao + slot.ghi_chu, thoi_gian_s=tg)
            kq.tra_loi = trinh_bay(kq)
            return kq

        # 5. Sự kiện → cá thể → suy luận → quyết định
        from src.kb.penalty import quyet_dinh

        du_lieu = xay_dung(hs, today)
        t0 = time.perf_counter()
        kq = self.reasoner.run([du_lieu.case], hom_nay=today)[0]
        tg["suy_luan"] = time.perf_counter() - t0
        qd = quyet_dinh(kq, du_lieu.case, du_lieu.case.get("ngay") or today)
        ghi_chu = list(dict.fromkeys(canh_bao + slot.ghi_chu + du_lieu.gia_dinh + hs.gia_dinh))
        trang_thai = "ket_luan" if kq.hanh_vi or kq.nguoi_khong_du_dieu_kien else "khong_phat_hien"
        logger.info("Lượt {}: {} — {} hành vi ({:.1f}s suy luận)", phien.so_luot, trang_thai, len(kq.hanh_vi),
                    tg["suy_luan"])
        out = KetQuaLuot(trang_thai, hs, [], du_lieu, kq, qd, ghi_chu, tg)
        self._giai_thich(out, phien)
        return out

    def _giai_thich(self, out: KetQuaLuot, phien: PhienLamViec) -> None:
        """6–7. Trace → (gợi ý RAG nếu không phát hiện) → câu trả lời (verbalizer có kiểm tra, hoặc tất định)."""
        from src.explanation.tracer import dung_trace
        from src.explanation.verbalizer import KetQuaDienDat
        from src.inference.report import trinh_bay

        t0 = time.perf_counter()
        out.trace = dung_trace(out)
        if out.trang_thai == "khong_phat_hien" and self.dung_goi_y_lien_quan and phien.loi_ke:
            try:
                out.lien_quan = self.retriever.tim(" ".join(phien.loi_ke), out.suy_luan.phien_ban, k=3)
            except Exception as e:  # noqa: BLE001 — gợi ý tra cứu là phụ, lỗi không chặn câu trả lời
                logger.warning("Không tìm được quy định liên quan: {}", e)
        out.thoi_gian_s["giai_thich"] = time.perf_counter() - t0
        du_phong = trinh_bay(out)
        if self.dung_dien_dat:
            t0 = time.perf_counter()
            out.dien_dat = self.verbalizer.dien_dat(out.trace, du_phong)
            out.thoi_gian_s["dien_dat"] = time.perf_counter() - t0
        else:
            out.dien_dat = KetQuaDienDat(du_phong, "tat_dinh")
        out.tra_loi = out.dien_dat.van_ban
        if out.lien_quan and out.dien_dat.nguon == "llm":
            from src.inference.report import goi_y_lien_quan

            out.tra_loi += "\n\n" + goi_y_lien_quan(out.lien_quan)

    @staticmethod
    def _ap_dung_xac_nhan(hs: HoSoVuViec, dong_y: bool, muc: set[str]) -> None:
        """Áp câu trả lời có/không cho ĐÚNG các mục ``muc`` mà câu xác nhận vừa hỏi."""
        for sk in hs.su_kien_suy_ra:
            if sk.trang_thai == "cho_xac_nhan" and f"su_kien:{sk.thuoc_tinh}" in muc:
                sk.trang_thai = "xac_nhan" if dong_y else "tu_choi"
        if "loai_xe" in muc and loai_xe_cho_xac_nhan(hs):
            if dong_y:
                hs.nguon["loai_xe"].phuong_phap = "nguoi_dung_xac_nhan"
            else:
                hs.loai_xe = None
                hs.nguon.pop("loai_xe", None)
        bo = []
        for d in cho_xac_nhan_lien_ket(hs):
            if f"lien_ket:{d.node}|{d.goc}" not in muc:
                continue
            if dong_y:
                d.phuong_phap = "nguoi_dung_xac_nhan"
            else:
                bo.append(d)
        for d in bo:
            hs.dau_hieu.remove(d)
            for k in d.su_kien:
                if (n := hs.nguon.get(f"su_kien.{k}")) and n.goc == d.goc:
                    hs.su_kien.pop(k, None)
                    hs.nguon.pop(f"su_kien.{k}", None)
        dong_bo_su_kien(hs)
