"""Kiểm tra kết nối LLM theo cấu hình .env.

  python -m scripts.check_llm          # gọi thử 1 request structured (có cache)
  python -m scripts.check_llm --list   # (Gemini) liệt kê model Flash/Flash-Lite khả dụng với key
"""

from __future__ import annotations

import sys

from loguru import logger
from pydantic import BaseModel

from src.config import get_settings
from src.llm.client import get_llm_client


class Ping(BaseModel):
    tra_loi: str
    so: int


def main() -> int:
    s = get_settings()
    logger.info("LLM_PROVIDER={} model={}", s.llm_provider,
                s.gemini_model if s.llm_provider == "gemini" else s.ollama_model)
    if "--list" in sys.argv and s.llm_provider == "gemini":
        from google import genai

        c = genai.Client(api_key=s.gemini_api_key)
        for m in c.models.list():
            if "flash" in m.name and "generateContent" in (m.supported_actions or []):
                print(m.name)
        return 0
    client = get_llm_client()
    out = client.generate_structured("Trả lời 'xin chào' và số 7.", Ping)
    logger.info("OK: {} | thống kê {}", out, client.stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
