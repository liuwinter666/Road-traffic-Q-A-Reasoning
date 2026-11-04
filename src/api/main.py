"""API FastAPI của hệ thống tư vấn.

Chạy:  uvicorn src.api.main:app --port 8000      (tài liệu tương tác: http://localhost:8000/docs)

Các endpoint:
  GET    /suc-khoe                      trạng thái + provider LLM đang dùng
  GET    /danh-muc                      lựa chọn cho giao diện (loại xe, loại đường, sự kiện)
  POST   /phien                         tạo phiên (một vụ việc) → {phien_id}
  GET    /phien/{id}                    hồ sơ, lịch sử, kết quả gần nhất
  POST   /phien/{id}/tin-nhan           {tin_nhan, ngay_vi_pham?} → kết quả một lượt
  PATCH  /phien/{id}/ho-so              {thay_doi: {...}} → sửa bảng sự kiện rồi chạy lại suy luận
  PUT    /phien/{id}/ngay               {ngay_vi_pham | null} → đặt ngày vi phạm (ô chọn ngày)
  POST   /phien/{id}/moi                bắt đầu vụ việc mới trong phiên
  DELETE /phien/{id}
  GET    /dieu-khoan/{id}?phien_ban=V4&ngay=YYYY-MM-DD   nguyên văn một điều/khoản/điểm

Các route là hàm đồng bộ → FastAPI chạy trong threadpool; manager tự khóa khi gọi reasoner.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.dialogue.manager import DialogueManager, PhienKhongTonTai, danh_muc_giao_dien
from src.llm.client import LLMError

app = FastAPI(title="Tư vấn vi phạm giao thông đường bộ", version="0.7.0",
              description="Hệ chuyên gia: LLM trích xuất sự kiện, reasoner OWL/SWRL kết luận, có truy vết căn cứ.")


@lru_cache(maxsize=1)
def get_manager() -> DialogueManager:
    return DialogueManager()


class TinNhanVao(BaseModel):
    tin_nhan: str = Field(min_length=1, max_length=4000)
    ngay_vi_pham: date | None = None


class SuaHoSo(BaseModel):
    thay_doi: dict


class DatNgay(BaseModel):
    ngay_vi_pham: date | None = None


def _phien(mgr: DialogueManager, pid: str):
    try:
        return mgr.lay(pid)
    except PhienKhongTonTai:
        raise HTTPException(404, f"Không có phiên {pid} (hoặc đã hết hạn)") from None


def _chay(fn, *a):
    try:
        return fn(*a)
    except PhienKhongTonTai as e:
        raise HTTPException(404, f"Không có phiên {e.args[0]} (hoặc đã hết hạn)") from None
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    except LLMError as e:
        raise HTTPException(503, f"Lỗi dịch vụ LLM: {e}") from None


@app.get("/suc-khoe")
def suc_khoe() -> dict:
    from src.config import get_settings

    s = get_settings()
    model = s.gemini_model if s.llm_provider == "gemini" else s.ollama_model
    return {"ok": True, "llm_provider": s.llm_provider, "llm_model": model, "reasoner": s.reasoner}


@app.get("/danh-muc")
def danh_muc() -> dict:
    return danh_muc_giao_dien()


@app.post("/phien")
def tao_phien(mgr: DialogueManager = Depends(get_manager)) -> dict:
    return {"phien_id": mgr.tao_phien()}


@app.get("/phien/{pid}")
def xem_phien(pid: str, mgr: DialogueManager = Depends(get_manager)) -> dict:
    return _phien(mgr, pid).tom_tat()


@app.post("/phien/{pid}/tin-nhan")
def gui_tin_nhan(pid: str, body: TinNhanVao, mgr: DialogueManager = Depends(get_manager)) -> dict:
    return _chay(mgr.gui, pid, body.tin_nhan, body.ngay_vi_pham)


@app.patch("/phien/{pid}/ho-so")
def sua_ho_so(pid: str, body: SuaHoSo, mgr: DialogueManager = Depends(get_manager)) -> dict:
    return _chay(mgr.sua_ho_so, pid, body.thay_doi)


@app.put("/phien/{pid}/ngay")
def dat_ngay(pid: str, body: DatNgay, mgr: DialogueManager = Depends(get_manager)) -> dict:
    _chay(mgr.dat_ngay, pid, body.ngay_vi_pham)
    return {"ngay_vi_pham": body.ngay_vi_pham}


@app.post("/phien/{pid}/moi")
def vu_viec_moi(pid: str, mgr: DialogueManager = Depends(get_manager)) -> dict:
    _chay(mgr.vu_viec_moi, pid)
    return {"ok": True}


@app.delete("/phien/{pid}")
def xoa_phien(pid: str, mgr: DialogueManager = Depends(get_manager)) -> dict:
    mgr.xoa(pid)
    return {"ok": True}


@app.get("/dieu-khoan/{id_}")
def dieu_khoan(id_: str, phien_ban: str | None = None, ngay: date | None = None) -> dict:
    from src.explanation.retriever import lay

    b = lay(id_, phien_ban, ngay)
    if b is None:
        raise HTTPException(404, f"Không có phần tử {id_}" + (f" trong {phien_ban}" if phien_ban else ""))
    return {"id": b.id, "trich_dan": b.trich_dan, "van_ban": b.so_hieu, "nguyen_van": b.full_text,
            "hieu_luc_tu": b.hieu_luc_tu, "hieu_luc_den": b.hieu_luc_den, "nguon": b.nguon}
