"""Cấu hình tập trung của hệ thống, đọc từ biến môi trường / file `.env`.

Mọi module khác lấy cấu hình qua `get_settings()`, không đọc `os.environ` trực tiếp
và không hard-code API key.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Thư mục gốc của project (chứa README.md, data/, ontology/, src/...)
ROOT_DIR: Path = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
TEST_DATA_DIR = DATA_DIR / "test"
ONTOLOGY_DIR = ROOT_DIR / "ontology"
RULES_DIR = ONTOLOGY_DIR / "rules"
PROMPTS_DIR = ROOT_DIR / "src" / "llm" / "prompts"


class Settings(BaseSettings):
    """Tham số cấu hình; tên trường trùng tên biến môi trường (không phân biệt hoa thường)."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM — provider: gemini (chính, gói miễn phí) | ollama (dự phòng, chạy local)
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096
    llm_timeout_s: float = 60.0
    llm_max_rpm: int = 10              # giới hạn request/phút (gói miễn phí có hạn mức theo phút)
    llm_max_retries: int = 5           # số lần thử lại khi 429 / lỗi tạm thời
    llm_backoff_base_s: float = 2.0    # backoff = base * 2^lần (nếu máy chủ không gợi ý retryDelay)
    llm_cache: bool = True             # cache phản hồi ra .cache/llm/

    # Embedding / RAG
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"
    entity_link_threshold: float = Field(0.65, ge=0.0, le=1.0)
    entity_link_embedding: bool = True   # bật embedding dự phòng khi từ điển đồng nghĩa không khớp
    vector_store: Literal["faiss", "chroma"] = "faiss"

    # Reasoner
    java_exe: str = ""
    reasoner: Literal["pellet", "hermit"] = "hermit"
    java_memory_mb: int = 2000

    # Pháp lý
    default_legal_version: str = "V3"

    # Logging
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Trả về đối tượng Settings dùng chung (cache một lần cho cả tiến trình)."""
    return Settings()
