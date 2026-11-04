"""Giao diện chatbot tư vấn vi phạm giao thông (Streamlit).

Chạy:   streamlit run app/streamlit_app.py
        (hoặc `python -m scripts.run_app` để bật cả API lẫn giao diện)

Hai cột: trái là khung chat nhiều lượt; phải là bảng sự kiện đã trích (sửa được rồi chạy lại suy luận), cây suy luận,
nguyên văn điều khoản và chi tiết kỹ thuật. Thanh bên có ô chọn ngày vi phạm.

Backend: biến môi trường APP_BACKEND = auto (mặc định: dùng API ở API_URL nếu đang chạy, không thì chạy trực tiếp
trong tiến trình) | api | truc_tiep. API_URL mặc định http://127.0.0.1:8000.
"""

from __future__ import annotations

import os
import sys
import textwrap
from datetime import date
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
NGUON = {"tu_dien": "bạn nêu", "llm": "bạn nêu", "normalizer": "bạn nêu", "suy_ra": "suy ra từ lời kể",
         "nguoi_dung_xac_nhan": "bạn đã xác nhận", "nguoi_dung_sua": "bạn sửa", "embedding": "ánh xạ gần nghĩa",
         "nguoi_dung": "bạn chọn"}
BA_TRANG_THAI = ["không rõ", "có", "không"]
MAU = {"su_kien": "#fff3bf", "nguong": "#d0ebff", "do_tuoi": "#d0ebff", "hop": "#e7f5ff", "dau_hieu": "#d0ebff",
       "phuong_tien": "#e6fcf5", "lop": "#f1f3f5", "hanh_vi": "#ffc9c9", "quy_tac": "#ffd8a8",
       "dieu_khoan": "#d3f9d8", "muc_phat": "#e9ecef"}


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

class ApiBackend:
    ten = "API"

    def __init__(self, url: str):
        import httpx

        self.url = url
        self.c = httpx.Client(base_url=url, timeout=600)

    def _r(self, method: str, path: str, **kw) -> dict:
        r = self.c.request(method, path, **kw)
        if r.status_code == 404 and path.startswith("/phien/"):
            raise LookupError(r.json().get("detail", "Phiên không tồn tại"))
        if r.status_code >= 400:
            raise RuntimeError(r.json().get("detail", r.text))
        return r.json()

    def suc_khoe(self):
        return self._r("GET", "/suc-khoe")

    def danh_muc(self):
        return self._r("GET", "/danh-muc")

    def tao_phien(self):
        return self._r("POST", "/phien")["phien_id"]

    def gui(self, pid, tin_nhan, ngay):
        return self._r("POST", f"/phien/{pid}/tin-nhan",
                       json={"tin_nhan": tin_nhan, "ngay_vi_pham": ngay.isoformat() if ngay else None})

    def sua(self, pid, thay_doi):
        return self._r("PATCH", f"/phien/{pid}/ho-so", json={"thay_doi": thay_doi})

    def dat_ngay(self, pid, ngay):
        return self._r("PUT", f"/phien/{pid}/ngay", json={"ngay_vi_pham": ngay.isoformat() if ngay else None})

    def moi(self, pid):
        return self._r("POST", f"/phien/{pid}/moi")


@st.cache_resource(show_spinner="Đang khởi tạo hệ thống (nạp ontology, Java)...")
def _manager():
    from src.dialogue.manager import DialogueManager

    return DialogueManager()


class TrucTiepBackend:
    ten = "trực tiếp (trong tiến trình)"

    def __init__(self):
        self.m = _manager()

    def _goi(self, fn, *a):
        from src.dialogue.manager import PhienKhongTonTai

        try:
            return fn(*a)
        except PhienKhongTonTai as e:
            raise LookupError(str(e)) from None

    def suc_khoe(self):
        from src.config import get_settings

        s = get_settings()
        return {"llm_provider": s.llm_provider, "llm_model": s.gemini_model if s.llm_provider == "gemini"
                else s.ollama_model, "reasoner": s.reasoner}

    def danh_muc(self):
        from src.dialogue.manager import danh_muc_giao_dien

        return danh_muc_giao_dien()

    def tao_phien(self):
        return self.m.tao_phien()

    def gui(self, pid, tin_nhan, ngay):
        return self._goi(self.m.gui, pid, tin_nhan, ngay)

    def sua(self, pid, thay_doi):
        return self._goi(self.m.sua_ho_so, pid, thay_doi)

    def dat_ngay(self, pid, ngay):
        return self._goi(self.m.dat_ngay, pid, ngay)

    def moi(self, pid):
        return self._goi(self.m.vu_viec_moi, pid)


def chon_backend():
    if "backend" in st.session_state:
        return st.session_state.backend
    kieu = os.environ.get("APP_BACKEND", "auto")
    be = None
    if kieu in ("auto", "api"):
        try:
            be = ApiBackend(API_URL)
            be.c.get("/suc-khoe", timeout=2).raise_for_status()
        except Exception:  # noqa: BLE001 — không có API: chạy trực tiếp (auto) hoặc báo lỗi (api)
            if kieu == "api":
                st.error(f"Không kết nối được API ở {API_URL}. Chạy: uvicorn src.api.main:app --port 8000")
                st.stop()
            be = None
    st.session_state.backend = be or TrucTiepBackend()
    return st.session_state.backend


# ---------------------------------------------------------------------------
# Tiện ích hiển thị
# ---------------------------------------------------------------------------

def tien(x) -> str:
    return "—" if x is None else f"{x:,}".replace(",", ".") + " đồng"


def dot(do_thi: dict) -> str:
    """Đồ thị suy luận (Graphviz DOT): sự kiện → điều kiện → quy tắc → hành vi → điều khoản → mức phạt."""
    def nhan(s: str) -> str:
        return "\\n".join(textwrap.wrap(s, 38)).replace('"', "'")
    dong = ['digraph G {', 'rankdir=LR; bgcolor="transparent";',
            'node [shape=box, style="rounded,filled", fontname="Arial", fontsize=10];', 'edge [color="#868e96"];']
    for n in do_thi["nodes"]:
        dong.append(f'"{n["id"]}" [label="{nhan(n["label"])}", fillcolor="{MAU.get(n["loai"], "#ffffff")}"];')
    for e in do_thi["edges"]:
        lb = f' [label="{e["label"]}", fontsize=9]' if e.get("label") else ""
        dong.append(f'"{e["from"]}" -> "{e["to"]}"{lb};')
    dong.append("}")
    return "\n".join(dong)


def ba_trang_thai(v) -> str:
    return "không rõ" if v is None else ("có" if v else "không")


def tu_ba_trang_thai(s: str):
    return None if s == "không rõ" else s == "có"


# ---------------------------------------------------------------------------
# Trạng thái phiên
# ---------------------------------------------------------------------------

def khoi_tao():
    ss = st.session_state
    ss.setdefault("lich_su", [])
    ss.setdefault("ket_qua", None)
    ss.setdefault("ngay_da_dat", None)
    if "phien_id" not in ss:
        ss.phien_id = chon_backend().tao_phien()


def goi(fn, *a):
    """Gọi backend; phiên hết hạn (API khởi động lại) → tạo phiên mới và báo."""
    be = chon_backend()
    try:
        return fn(be, *a)
    except LookupError:
        st.session_state.phien_id = be.tao_phien()
        st.session_state.lich_su, st.session_state.ket_qua = [], None
        st.warning("Phiên cũ đã hết hạn — đã tạo phiên mới, bạn gửi lại mô tả nhé.")
        return None
    except Exception as e:  # noqa: BLE001
        st.error(f"Lỗi: {e}")
        return None


def gui_tin(msg: str, ngay):
    st.session_state.lich_su.append({"vai": "user", "noi_dung": msg})
    with st.spinner("Đang phân tích và suy luận..."):
        kq = goi(lambda be, *a: be.gui(*a), st.session_state.phien_id, msg, ngay)
    if kq is not None:
        if kq.get("trang_thai") == "vu_viec_moi":
            st.session_state.ket_qua = None
        else:
            st.session_state.ket_qua = kq
        st.session_state.lich_su.append({"vai": "assistant", "noi_dung": kq["tra_loi"]})


# ---------------------------------------------------------------------------
# Các khối giao diện
# ---------------------------------------------------------------------------

def thanh_ben() -> date | None:
    with st.sidebar:
        st.header("Thiết lập")
        biet = st.checkbox("Tôi biết ngày vi phạm", value=False,
                           help="Không chọn: hệ thống lấy ngày từ lời kể; không có thì dùng luật đang có hiệu lực hôm nay.")
        ngay = st.date_input("Ngày vi phạm", value=date.today(), format="DD/MM/YYYY", disabled=not biet)
        ngay = ngay if biet else None
        if ngay != st.session_state.ngay_da_dat:
            st.session_state.ngay_da_dat = ngay
            goi(lambda be, *a: be.dat_ngay(*a), st.session_state.phien_id, ngay)
        if st.button("Vụ việc mới", use_container_width=True):
            goi(lambda be, *a: be.moi(*a), st.session_state.phien_id)
            st.session_state.lich_su, st.session_state.ket_qua = [], None
            st.rerun()
        st.divider()
        be = chon_backend()
        try:
            sk = be.suc_khoe()
            st.caption(f"Backend: {be.ten}  \nLLM: {sk['llm_provider']} / {sk['llm_model']}  \n"
                       f"Reasoner: {sk['reasoner']}")
        except Exception:  # noqa: BLE001
            st.caption(f"Backend: {be.ten}")
        st.caption("LLM chỉ trích xuất sự kiện và diễn đạt câu trả lời; kết luận pháp lý do bộ suy luận "
                   "(ontology + luật SWRL) đưa ra. Kết quả chỉ mang tính tham khảo.")
    return ngay


def cot_chat(ngay):
    hop = st.container(height=640)
    with hop:
        if not st.session_state.lich_su:
            st.info("Mô tả tình huống của bạn, ví dụ: *“Tối qua tôi đi xe máy 110 phân khối, thấy CSGT vẫy thì rồ ga "
                    "chạy luôn, không đội mũ bảo hiểm”*. Hệ thống sẽ hỏi lại nếu thiếu thông tin.")
        for m in st.session_state.lich_su:
            with st.chat_message(m["vai"]):
                st.markdown(m["noi_dung"])
    if msg := st.chat_input("Mô tả tình huống hoặc trả lời câu hỏi..."):
        gui_tin(msg, ngay)
        st.rerun()


def tab_su_kien(kq: dict, dm: dict):
    hs = kq["ho_so"]
    xe_nhan = {x["ma"]: x["nhan"] for x in dm["loai_xe"]}
    if hs.get("loai_xe") and hs["loai_xe"] not in xe_nhan:
        xe_nhan[hs["loai_xe"]] = hs["loai_xe"]
    duong_nhan = {x["ma"]: x["nhan"] for x in dm["loai_duong"]}
    sk_nhan = {x["ma"]: x["nhan"] for x in dm["su_kien"]}
    nhan_sk = {v: k for k, v in sk_nhan.items()}
    st.caption("Sửa giá trị hệ thống đã hiểu rồi bấm **Chạy lại suy luận** (không gọi lại LLM trích xuất). "
               "Giá trị bạn sửa luôn được ưu tiên hơn giá trị hệ thống suy ra.")
    with st.form("ho_so"):
        lua_xe = ["(chưa rõ)"] + list(xe_nhan)
        xe = st.selectbox("Loại xe", lua_xe, index=lua_xe.index(hs["loai_xe"]) if hs.get("loai_xe") in xe_nhan else 0,
                          format_func=lambda m: xe_nhan.get(m, m))
        c1, c2 = st.columns(2)
        so = {}
        for col, k, nhan, buoc in ((c1, "dung_tich_xi_lanh", "Dung tích xi-lanh (cm3)", 1.0),
                                   (c2, "cong_suat_dong_co_dien", "Công suất động cơ điện (kW)", 0.1),
                                   (c1, "tuoi_nguoi_lai", "Tuổi người lái", 1.0),
                                   (c2, "nong_do_con_khi_tho", "Nồng độ cồn khí thở (mg/L)", 0.01),
                                   (c1, "nong_do_con_mau", "Nồng độ cồn trong máu (mg/100 mL)", 1.0),
                                   (c2, "toc_do_thuc_te", "Tốc độ thực tế (km/h)", 1.0),
                                   (c1, "toc_do_toi_da", "Tốc độ tối đa theo biển báo (km/h)", 1.0)):
            v = hs.get(k)
            so[k] = col.number_input(nhan, min_value=0.0, value=None if v is None else float(v), step=buoc,
                                     placeholder="không rõ")
        c3, c4, c5 = st.columns(3)
        kdc = c3.selectbox("Trong khu đông dân cư", BA_TRANG_THAI, index=BA_TRANG_THAI.index(ba_trang_thai(hs.get("khu_dong_dan_cu"))))
        doi = c4.selectbox("Đường đôi", BA_TRANG_THAI, index=BA_TRANG_THAI.index(ba_trang_thai(hs.get("duong_doi"))))
        kd = c5.selectbox("Kinh doanh vận tải", BA_TRANG_THAI,
                          index=BA_TRANG_THAI.index(ba_trang_thai(hs.get("kinh_doanh_van_tai"))))
        duong = st.multiselect("Loại đường", list(duong_nhan), default=[d for d in hs.get("loai_duong", []) if d in duong_nhan],
                               format_func=lambda m: duong_nhan.get(m, m))
        import pandas as pd

        rows = [{"Sự kiện": sk_nhan.get(k, k), "Giá trị": bool(v),
                 "Nguồn": NGUON.get((hs.get("nguon", {}).get(f"su_kien.{k}") or {}).get("phuong_phap", ""), "")}
                for k, v in hs.get("su_kien", {}).items()]
        df = pd.DataFrame(rows or [], columns=["Sự kiện", "Giá trị", "Nguồn"])
        st.markdown("**Sự kiện** (thêm dòng để bổ sung, xóa dòng để bỏ)")
        moi = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={
            "Sự kiện": st.column_config.SelectboxColumn(options=sorted(sk_nhan.values()), required=True, width="large"),
            "Giá trị": st.column_config.CheckboxColumn(help="Tích = có / đúng"),
            "Nguồn": st.column_config.TextColumn(disabled=True)})
        bam = st.form_submit_button("Chạy lại suy luận", type="primary", use_container_width=True)
    if not bam:
        return
    td: dict = {}
    xe_moi = None if xe == "(chưa rõ)" else xe
    if xe_moi != hs.get("loai_xe"):
        td["loai_xe"] = xe_moi
    for k, v in so.items():
        cu = hs.get(k)
        if (v is None) != (cu is None) or (v is not None and abs(float(v) - float(cu)) > 1e-9):
            td[k] = (int(v) if k == "tuoi_nguoi_lai" else v) if v is not None else None
    for k, s in (("khu_dong_dan_cu", kdc), ("duong_doi", doi), ("kinh_doanh_van_tai", kd)):
        if tu_ba_trang_thai(s) != hs.get(k):
            td[k] = tu_ba_trang_thai(s)
    if sorted(duong) != sorted(hs.get("loai_duong", [])):
        td["loai_duong"] = duong
    moi_sk = {nhan_sk[r["Sự kiện"]]: bool(r["Giá trị"]) for _, r in moi.iterrows()
              if isinstance(r["Sự kiện"], str) and r["Sự kiện"] in nhan_sk}
    sk_doi = {k: v for k, v in moi_sk.items() if hs.get("su_kien", {}).get(k) != v}
    sk_doi.update({k: None for k in hs.get("su_kien", {}) if k not in moi_sk})
    if sk_doi:
        td["su_kien"] = sk_doi
    if not td:
        st.info("Không có thay đổi.")
        return
    with st.spinner("Đang chạy lại suy luận..."):
        kq2 = goi(lambda be, *a: be.sua(*a), st.session_state.phien_id, td)
    if kq2 is not None:
        st.session_state.ket_qua = kq2
        st.session_state.lich_su.append({"vai": "assistant", "noi_dung": "*(Đã cập nhật theo bảng sự kiện bạn sửa)*\n\n"
                                         + kq2["tra_loi"]})
        st.rerun()


def tab_cay(kq: dict):
    if not kq.get("do_thi") or not kq["do_thi"]["nodes"]:
        st.info("Chưa có kết luận để vẽ cây suy luận" + (" — hệ thống đang chờ bạn trả lời câu hỏi."
                                                          if kq["trang_thai"] == "can_hoi" else "."))
        return
    st.graphviz_chart(dot(kq["do_thi"]), use_container_width=True)
    st.caption("Vàng: sự kiện · xanh dương: điều kiện của luật (ngưỡng, dấu hiệu) · cam: quy tắc SWRL · "
               "đỏ: hành vi vi phạm · xanh lá: điều khoản áp dụng · xám: mức đề xuất")
    with st.expander("Chuỗi suy luận dạng chữ"):
        for d in kq["chuoi_suy_luan"]:
            st.markdown(f"- {d}")


def tab_dieu_khoan(kq: dict):
    ds = kq.get("dieu_khoan_nguyen_van") or []
    if not ds and not kq.get("lien_quan"):
        st.info("Chưa có điều khoản nào được dẫn.")
    for d in ds:
        tieu_de = ("⚖️ " if d["la_ket_luan"] else "📎 ") + d["trich_dan"]
        with st.expander(tieu_de, expanded=d["la_ket_luan"]):
            st.markdown(d["nguyen_van"].replace("\n", "  \n"))
            st.caption(f"Hiệu lực: {d.get('hieu_luc_tu') or '?'} – {d.get('hieu_luc_den') or 'nay'}")
    if kq.get("lien_quan"):
        st.markdown("**Quy định có thể liên quan** — gợi ý tra cứu theo nội dung, hệ thống chưa mô hình hóa nên "
                    "**không** kết luận:")
        for x in kq["lien_quan"]:
            st.markdown(f"- {x['trich_dan']}: “{x['text']}” *(độ gần {x['diem']:.2f})*")


def tab_chi_tiet(kq: dict):
    if kq.get("phien_ban"):
        st.markdown(f"**Phiên bản pháp lý:** {kq['phien_ban'].get('ghi_chu', kq['phien_ban'].get('ma'))}")
    if kq.get("hanh_vi"):
        import pandas as pd

        st.dataframe(pd.DataFrame([{
            "Hành vi": h["ten"], "Căn cứ": h["dieu_khoan"],
            "Khung phạt": f"{tien(h['khung_phat'][0])} – {tien(h['khung_phat'][1])}" if h["khung_phat"] else "—",
            "Mức đề xuất": tien(h["muc_de_xuat"]), "Trừ điểm": h["tru_diem"] or "—",
            "Quy tắc": ", ".join(h.get("quy_tac") or []), "Mã điều khoản": h["dieu_khoan_id"]} for h in kq["hanh_vi"]]),
            hide_index=True, use_container_width=True)
        st.caption("Quy tắc: mã luật suy luận (SWRL) trong ontology/rule_registry.yaml đã đưa ra kết luận — tra mã để "
                   "xem điều kiện, điều khoản gốc và nguyên văn.")
        st.markdown(f"**Tổng đề xuất:** {tien(kq['tong_tien_de_xuat'])}"
                    + (f" · **Trừ điểm GPLX:** {kq['tru_diem_ap_dung']}" if kq.get("tru_diem_ap_dung") else ""))
    dd = kq.get("dien_dat")
    if dd:
        kt = dd.get("kiem_tra") or {}
        st.markdown(f"**Câu trả lời:** {'LLM viết từ chuỗi suy luận' if dd['nguon'] == 'llm' else 'trình bày tự động'}"
                    f" · {dd.get('so_lan_goi', 0)} lần gọi LLM · kiểm tra chống bịa: "
                    f"{'đạt' if kt.get('hop_le') else ('không đạt' if kt else '—')}")
        for x in kt.get("loi") or []:
            st.markdown(f"  - {x}")
        if dd.get("ly_do_du_phong"):
            st.caption(f"Dùng bản tự động vì: {dd['ly_do_du_phong']}")
    for g in kq.get("ghi_chu") or []:
        st.markdown(f"- {g}")
    if kq.get("ho_so", {}).get("cum_tu_loai_bo"):
        st.caption("Cụm LLM trả về nhưng không có trong lời bạn (đã bỏ): " + "; ".join(kq["ho_so"]["cum_tu_loai_bo"]))
    if kq.get("thoi_gian_s"):
        st.caption("Thời gian (giây): " + ", ".join(f"{k} {v}" for k, v in kq["thoi_gian_s"].items()))
    with st.expander("Hồ sơ vụ việc (JSON)"):
        st.json(kq["ho_so"])
    if kq.get("trace"):
        with st.expander("Trace (JSON)"):
            st.json(kq["trace"])


def main():
    st.set_page_config(page_title="Tư vấn vi phạm giao thông", page_icon="🚦", layout="wide")
    khoi_tao()
    ngay = thanh_ben()
    st.title("Tư vấn vi phạm giao thông đường bộ")
    trai, phai = st.columns([1.1, 1], gap="large")
    with trai:
        cot_chat(ngay)
    with phai:
        kq = st.session_state.ket_qua
        if kq is None:
            st.info("Bảng sự kiện, cây suy luận và nguyên văn điều khoản sẽ hiện ở đây sau khi bạn gửi mô tả.")
            return
        if "danh_muc" not in st.session_state:
            st.session_state.danh_muc = chon_backend().danh_muc()
        t1, t2, t3, t4 = st.tabs(["Sự kiện", "Cây suy luận", "Điều khoản", "Chi tiết"])
        with t1:
            tab_su_kien(kq, st.session_state.danh_muc)
        with t2:
            tab_cay(kq)
        with t3:
            tab_dieu_khoan(kq)
        with t4:
            tab_chi_tiet(kq)


main()
