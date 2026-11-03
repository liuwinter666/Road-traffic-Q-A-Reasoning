"""Schema dữ liệu của tầng trích xuất.

* ``TrichXuatLLM``: đầu ra của LLM — CHỈ cụm từ bề mặt trong lời người dùng (chưa chuẩn hóa, chưa suy luận).
  Schema giữ kiểu đơn giản (chuỗi, bool, danh sách) để tương thích JSON schema mode của Gemini.
* ``HoSoVuViec``: hồ sơ vụ việc đã chuẩn hóa (số, đơn vị, node ontology), kèm nguồn gốc của từng trường;
  gộp được qua nhiều lượt hội thoại (``cap_nhat``).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Đầu ra LLM
# ---------------------------------------------------------------------------


class SuKienTho(BaseModel):
    """Một hành vi/sự kiện người dùng nêu trực tiếp."""

    mo_ta: str = Field(description="Cụm từ ngắn gọn mô tả hành vi, giữ cách nói của người dùng (vd. 'vượt đèn đỏ')")
    trich_dan: str = Field(description="Câu hoặc đoạn nguyên văn trong lời người dùng chứa hành vi")
    phu_dinh: bool = Field(False, description="True nếu người dùng nói hành vi KHÔNG xảy ra (vd. 'tôi không vượt đèn')")


class TrichXuatLLM(BaseModel):
    """Các cụm từ trích nguyên văn; để null nếu người dùng không nói tới."""

    thoi_diem: str | None = Field(None, description="Cụm chỉ thời điểm vi phạm (vd. '10/3/2025', 'tối qua')")
    loai_xe: str | None = Field(None, description="Cụm chỉ loại xe người vi phạm điều khiển (vd. 'xe máy', 'ô tô con')")
    dung_tich_xi_lanh: str | None = Field(None, description="Dung tích xi-lanh nếu có (vd. '110 phân khối')")
    cong_suat_dong_co: str | None = Field(None, description="Công suất động cơ điện nếu có (vd. '1500W')")
    tuoi_nguoi_lai: str | None = Field(None, description="Tuổi hoặc năm sinh người điều khiển (vd. '17 tuổi', 'sinh 2009')")
    nong_do_con: str | None = Field(None, description="Kết quả đo nồng độ cồn nguyên văn kèm đơn vị (vd. '0,3 mg/l')")
    toc_do_thuc_te: str | None = Field(None, description="Tốc độ xe đang chạy (vd. '80 cây')")
    toc_do_toi_da: str | None = Field(None, description="Tốc độ giới hạn/biển báo (vd. 'biển 60')")
    loai_duong: list[str] = Field(default_factory=list, description="Các cụm mô tả đường (vd. 'cao tốc', 'trong khu dân cư')")
    su_kien: list[SuKienTho] = Field(default_factory=list, description="Các hành vi, sự kiện người dùng nêu trực tiếp")
    nguoi_lai_khong_phai_chu_xe: bool | None = Field(
        None, description="True nếu xe là của người khác giao/cho mượn (vd. 'đi xe của bố')")
    tuoi_chu_xe: str | None = Field(None, description="Tuổi chủ xe nếu được nêu")


# ---------------------------------------------------------------------------
# Hồ sơ vụ việc (đã chuẩn hóa)
# ---------------------------------------------------------------------------


class NguonGoc(BaseModel):
    """Nguồn gốc giá trị của một trường."""

    goc: str | None = None                    # cụm từ gốc
    phuong_phap: str = "llm"                  # llm | normalizer | tu_dien | embedding | nguoi_dung | suy_ra
    do_tin_cay: float = 1.0
    ghi_chu: list[str] = Field(default_factory=list)


class DauHieu(BaseModel):
    """Node ontology đã liên kết từ một sự kiện."""

    node: str                                 # vd. KhongChapHanhDenTinHieu, _CO_CON
    kieu: str                                 # dau_hieu | tinh_tiet | goi_y
    su_kien: dict[str, bool] = Field(default_factory=dict)   # giá trị boolean kéo theo
    goc: str
    trich_dan: str = ""
    phuong_phap: str = "tu_dien"
    do_tin_cay: float = 1.0
    phu_dinh: bool = False


class SuKienSuyRa(BaseModel):
    """Sự kiện gián tiếp do fact_inducer (LLM) suy ra, sau khi kiểm tra tất định."""

    thuoc_tinh: str                           # thuộc tính boolean của ontology (vd. chapHanhHieuLenh)
    gia_tri: bool
    do_tin_cay: float
    bang_chung: str                           # trích nguyên văn lời người dùng
    giai_thich: str = ""
    nhan: str = ""                            # nhãn tiếng Việt của thuộc tính (từ ontology)
    # chap_nhan | cho_xac_nhan | xac_nhan (người dùng đồng ý) | tu_choi (người dùng bác) |
    # tin_cay_thap | khong_can_cu (bằng chứng không có trong lời người dùng) | xung_dot (trái sự kiện trực tiếp)
    trang_thai: str = "chap_nhan"

    @property
    def dang_ap_dung(self) -> bool:
        return self.trang_thai in ("chap_nhan", "xac_nhan")

    def mo_ta(self) -> str:
        return f"{self.nhan or self.thuoc_tinh}: {'có' if self.gia_tri else 'không'}"


class HoSoVuViec(BaseModel):
    """Hồ sơ một vụ việc, cập nhật qua nhiều lượt hội thoại."""

    ngay_tu: date | None = None
    ngay_den: date | None = None
    do_chinh_xac_ngay: str | None = None      # ngay | thang | nam | tuong_doi
    loai_xe: str | None = None                # lớp ontology (NhomXeMoTo, OTo, XeMayDien...)
    dung_tich_xi_lanh: float | None = None    # cm3
    cong_suat_dong_co_dien: float | None = None   # kW
    tuoi_nguoi_lai: int | None = None
    nong_do_con_khi_tho: float | None = None  # mg/L
    nong_do_con_mau: float | None = None      # mg/100 mL
    toc_do_thuc_te: float | None = None       # km/h
    toc_do_toi_da: float | None = None        # km/h
    loai_duong: list[str] = Field(default_factory=list)       # lớp ontology
    khu_dong_dan_cu: bool | None = None
    duong_doi: bool | None = None             # True: đường đôi/một chiều nhiều làn; False: hai chiều/một làn
    kinh_doanh_van_tai: bool | None = None
    chu_xe_giao_xe: bool | None = None
    tuoi_chu_xe: int | None = None
    su_kien: dict[str, bool] = Field(default_factory=dict)    # thuộc tính boolean của ontology
    dau_hieu: list[DauHieu] = Field(default_factory=list)
    nguon: dict[str, NguonGoc] = Field(default_factory=dict)
    gia_dinh: list[str] = Field(default_factory=list)
    khong_lien_ket: list[str] = Field(default_factory=list)   # cụm không ánh xạ được vào ontology
    cum_tu_loai_bo: list[str] = Field(default_factory=list)   # cụm LLM trả về nhưng không có trong lời người dùng
    su_kien_suy_ra: list[SuKienSuyRa] = Field(default_factory=list)   # từ fact_inducer (kèm trạng thái)

    @property
    def ngay_vi_pham(self) -> date | None:
        return self.ngay_tu if self.ngay_tu and self.ngay_tu == self.ngay_den else None

    def goi_y(self) -> set[str]:
        return {d.node for d in self.dau_hieu if d.kieu == "goi_y" and not d.phu_dinh}

    def nodes(self) -> set[str]:
        return {d.node for d in self.dau_hieu if not d.phu_dinh}

    def cap_nhat(self, moi: "HoSoVuViec") -> "HoSoVuViec":
        """Gộp hồ sơ của lượt mới: trường có giá trị ở lượt mới ghi đè; danh sách/dict được hợp."""
        data = self.model_dump()
        for k, v in moi.model_dump().items():
            if k in ("loai_duong", "gia_dinh", "khong_lien_ket", "cum_tu_loai_bo"):
                data[k] = list(dict.fromkeys(data[k] + v))
            elif k == "dau_hieu":
                seen = {(d["node"], d["goc"]) for d in data[k]}
                data[k] += [d for d in v if (d["node"], d["goc"]) not in seen]
            elif k in ("su_kien", "nguon"):
                data[k] = {**data[k], **v}
            elif k == "su_kien_suy_ra":
                gop = {x["thuoc_tinh"]: x for x in data[k]}
                gop.update({x["thuoc_tinh"]: x for x in v})
                data[k] = list(gop.values())
            elif v is not None:
                data[k] = v
        return HoSoVuViec.model_validate(data)
