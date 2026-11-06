"""Lớp adapter LLM dùng chung.

Interface (không phụ thuộc provider):

    client = get_llm_client()                       # chọn provider theo LLM_PROVIDER trong .env
    text = client.generate(prompt, system=...)       # văn bản tự do
    obj  = client.generate_structured(prompt, MyModel, system=...)   # Pydantic model đã validate

Provider:
  * ``gemini`` (mặc định) — Google Gemini API, key ``GEMINI_API_KEY``; structured output bằng JSON schema mode
    (response_mime_type="application/json" + response_schema).
  * ``ollama`` (dự phòng, chạy local) — HTTP /api/chat với ``format: "json"``.

Chung cho mọi provider:
  * **Cache đĩa**: khóa = SHA-256 của (provider, model, system, prompt, schema, temperature); lưu
    ``.cache/llm/<khóa>.json``. Gọi lại cùng prompt không tốn request.
  * **Giới hạn tốc độ**: tối đa ``LLM_MAX_RPM`` request/phút (cửa sổ trượt 60 s).
  * **Retry có backoff** khi gặp 429 (hết hạn mức) hoặc lỗi máy chủ 5xx/timeout: chờ theo ``retryDelay`` của
    máy chủ nếu có, ngược lại ``base * 2^lần`` (có jitter), tối đa ``LLM_MAX_RETRIES`` lần.
  * **Validate Pydantic**: phản hồi JSON sai schema → gọi lại 1 lần kèm thông báo lỗi; vẫn sai thì ném lỗi.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from pathlib import Path
from typing import Callable, TypeVar

from loguru import logger
from pydantic import BaseModel, ValidationError

from src.config import ROOT_DIR, get_settings

T = TypeVar("T", bound=BaseModel)
CACHE_DIR = ROOT_DIR / ".cache" / "llm"


class LLMError(RuntimeError):
    """Lỗi gọi LLM không phục hồi được."""


class RateLimitError(LLMError):
    """Lỗi 429 / hết hạn mức; ``retry_after`` (giây) nếu máy chủ gợi ý."""

    def __init__(self, msg: str, retry_after: float | None = None):
        super().__init__(msg)
        self.retry_after = retry_after


class TransientError(LLMError):
    """Lỗi tạm thời (5xx, timeout, mất kết nối) — có thể thử lại."""


class StructuredOutputError(LLMError):
    """Phản hồi không khớp schema sau khi đã thử lại."""


# ---------------------------------------------------------------------------
# Giới hạn tốc độ và cache
# ---------------------------------------------------------------------------


class RateLimiter:
    """Cửa sổ trượt: không quá ``max_per_minute`` lần gọi trong 60 giây gần nhất (an toàn đa luồng)."""

    def __init__(self, max_per_minute: int, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.max = max_per_minute
        self.clock, self.sleep = clock, sleep
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Chờ tới khi được phép gọi; trả về số giây đã chờ."""
        if self.max <= 0:
            return 0.0
        waited = 0.0
        while True:
            with self._lock:
                now = self.clock()
                while self._calls and now - self._calls[0] >= 60.0:
                    self._calls.popleft()
                if len(self._calls) < self.max:
                    self._calls.append(now)
                    return waited
                wait = 60.0 - (now - self._calls[0]) + 0.01
            logger.debug("Đạt giới hạn {} request/phút — chờ {:.1f}s", self.max, wait)
            self.sleep(wait)
            waited += wait


class DiskCache:
    """Cache phản hồi LLM ra đĩa, mỗi khóa một file JSON."""

    def __init__(self, directory: Path = CACHE_DIR, enabled: bool = True):
        self.dir = directory
        self.enabled = enabled

    @staticmethod
    def key(**parts) -> str:
        blob = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def get(self, key: str) -> str | None:
        if not self.enabled:
            return None
        p = self.dir / f"{key}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))["response"]
        return None

    def set(self, key: str, response: str, meta: dict) -> None:
        if not self.enabled:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / f"{key}.json").write_text(
            json.dumps({"response": response, "meta": meta}, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------
# Client chung
# ---------------------------------------------------------------------------


class LLMClient(ABC):
    """Lớp cơ sở: cache, giới hạn tốc độ, retry, validate. Provider chỉ cài ``_call``."""

    provider: str = "base"

    def __init__(self, model: str, *, temperature: float = 0.0, max_tokens: int = 4096, timeout_s: float = 60.0,
                 max_rpm: int = 10, max_retries: int = 5, backoff_base_s: float = 2.0,
                 cache: DiskCache | None = None, sleep: Callable[[float], None] = time.sleep):
        self.model = model
        self.temperature, self.max_tokens, self.timeout_s = temperature, max_tokens, timeout_s
        self.max_retries, self.backoff_base_s = max_retries, backoff_base_s
        self.cache = cache if cache is not None else DiskCache()
        self.sleep = sleep
        self.limiter = RateLimiter(max_rpm, sleep=sleep)
        self.stats = {"calls": 0, "cache_hits": 0, "retries": 0}

    # ---- provider ----
    @abstractmethod
    def _call(self, prompt: str, system: str | None, json_schema: dict | None,
              schema_model: type[BaseModel] | None) -> str:
        """Một lần gọi API; trả văn bản (JSON nếu có schema). Ném RateLimitError/TransientError/LLMError."""

    # ---- chung ----
    def _with_retry(self, fn: Callable[[], str]) -> str:
        for attempt in range(self.max_retries + 1):
            self.limiter.acquire()
            try:
                self.stats["calls"] += 1
                return fn()
            except RateLimitError as e:
                if attempt >= self.max_retries:
                    raise
                wait = e.retry_after if e.retry_after else self.backoff_base_s * (2 ** attempt)
                wait += random.uniform(0, 0.5)
                logger.warning("{} 429 (lần {}): chờ {:.1f}s rồi thử lại", self.provider, attempt + 1, wait)
            except TransientError as e:
                if attempt >= self.max_retries:
                    raise
                wait = self.backoff_base_s * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning("{} lỗi tạm thời ({}): chờ {:.1f}s", self.provider, e, wait)
            self.stats["retries"] += 1
            self.sleep(wait)
        raise LLMError("unreachable")

    def _cached(self, prompt: str, system: str | None, schema: dict | None,
                schema_model: type[BaseModel] | None, use_cache: bool) -> str:
        key = DiskCache.key(provider=self.provider, model=self.model, system=system, prompt=prompt,
                            schema=schema, temperature=self.temperature)
        if use_cache and (hit := self.cache.get(key)) is not None:
            self.stats["cache_hits"] += 1
            return hit
        text = self._with_retry(lambda: self._call(prompt, system, schema, schema_model))
        if use_cache:
            self.cache.set(key, text, {"provider": self.provider, "model": self.model, "time": time.time()})
        return text

    def generate(self, prompt: str, system: str | None = None, *, use_cache: bool = True) -> str:
        """Sinh văn bản tự do."""
        return self._cached(prompt, system, None, None, use_cache)

    def generate_structured(self, prompt: str, schema: type[T], system: str | None = None, *,
                            use_cache: bool = True) -> T:
        """Sinh JSON theo schema Pydantic; validate, sai thì thử lại 1 lần kèm thông báo lỗi."""
        js = schema.model_json_schema()
        text = self._cached(prompt, system, js, schema, use_cache)
        try:
            return schema.model_validate_json(_strip_fence(text))
        except ValidationError as e:
            logger.warning("{}: phản hồi sai schema {}, thử lại 1 lần", self.provider, schema.__name__)
            retry_prompt = (f"{prompt}\n\nPhản hồi trước KHÔNG hợp lệ với JSON schema. Lỗi:\n{e}\n"
                            "Hãy trả lại DUY NHẤT một đối tượng JSON hợp lệ theo đúng schema.")
            text2 = self._cached(retry_prompt, system, js, schema, use_cache)
            try:
                return schema.model_validate_json(_strip_fence(text2))
            except ValidationError as e2:
                raise StructuredOutputError(f"Phản hồi không khớp {schema.__name__}: {e2}") from e2


def _strip_fence(text: str) -> str:
    """Bỏ ```json ... ``` nếu model lỡ bọc khối mã."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        t = t.rsplit("```", 1)[0]
    return t.strip()


# ---------------------------------------------------------------------------
# Provider: Gemini
# ---------------------------------------------------------------------------


class GeminiClient(LLMClient):
    provider = "gemini"

    def __init__(self, model: str, api_key: str, **kw):
        super().__init__(model, **kw)
        if not api_key:
            raise LLMError("Thiếu GEMINI_API_KEY trong .env (lấy tại Google AI Studio)")
        from google import genai

        self._genai = genai
        self._client = genai.Client(api_key=api_key)

    def _call(self, prompt, system, json_schema, schema_model) -> str:
        from google.genai import errors, types

        cfg = types.GenerateContentConfig(
            system_instruction=system, temperature=self.temperature, max_output_tokens=self.max_tokens,
            http_options=types.HttpOptions(timeout=int(self.timeout_s * 1000)),
        )
        if schema_model is not None:
            cfg.response_mime_type = "application/json"
            cfg.response_schema = schema_model
        try:
            resp = self._client.models.generate_content(model=self.model, contents=prompt, config=cfg)
        except errors.APIError as e:
            code = getattr(e, "code", None)
            if code == 429:
                raise RateLimitError(str(e)[:300], _gemini_retry_delay(e)) from e
            if code is not None and code >= 500:
                raise TransientError(f"HTTP {code}") from e
            raise LLMError(f"Gemini lỗi {code}: {str(e)[:300]}") from e
        except Exception as e:  # noqa: BLE001 — lỗi mạng/timeout của httpx
            # lỗi mạng tạm thời: hết giờ, không kết nối được, máy chủ ngắt kết nối giữa chừng (ReadError/WinError 10054)
            ten = type(e).__name__.lower()
            if any(x in ten for x in ("timeout", "connect", "readerror", "remoteprotocol", "networkerror")):
                raise TransientError(type(e).__name__) from e
            raise
        text = resp.text
        if not text:
            raise TransientError("Phản hồi rỗng")
        return text


def _gemini_retry_delay(e) -> float | None:
    """Đọc 'retryDelay': '23s' trong chi tiết lỗi 429 của Gemini (nếu có)."""
    import re

    m = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", str(getattr(e, "details", "")) + str(e))
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Provider: Ollama
# ---------------------------------------------------------------------------


class OllamaClient(LLMClient):
    provider = "ollama"

    def __init__(self, model: str, base_url: str = "http://localhost:11434", num_ctx: int = 4096,
                 keep_alive: str = "30m", **kw):
        super().__init__(model, **kw)
        self.base_url = base_url.rstrip("/")
        self.num_ctx, self.keep_alive = num_ctx, keep_alive

    def _call(self, prompt, system, json_schema, schema_model) -> str:
        import httpx

        # Schema đặt trong system (phần đầu cố định giữa các lần gọi) → llama.cpp dùng lại KV-cache của prefix,
        # chỉ phải đọc phần lời người dùng thay đổi. Yêu cầu JSON gọn, bỏ trường null để giảm token sinh ra
        # (trường thiếu lấy giá trị mặc định khi validate Pydantic).
        if json_schema is not None:
            system = ((system + "\n\n") if system else "") + (
                "Trả lời DUY NHẤT bằng một đối tượng JSON gọn (không xuống dòng, không thụt lề) theo JSON schema "
                "dưới đây; được bỏ qua trường có giá trị null hoặc danh sách rỗng.\nJSON schema:\n"
                + json.dumps(json_schema, ensure_ascii=False, separators=(",", ":")))
        messages = ([{"role": "system", "content": system}] if system else [])
        messages.append({"role": "user", "content": prompt})
        body = {"model": self.model, "messages": messages, "stream": False, "keep_alive": self.keep_alive,
                "options": {"temperature": self.temperature, "num_predict": self.max_tokens,
                            "num_ctx": self.num_ctx}}
        if json_schema is not None:
            body["format"] = "json"
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=body, timeout=self.timeout_s)
        except httpx.ConnectError as e:
            raise TransientError(f"ConnectError — Ollama có đang chạy tại {self.base_url}?") from e
        except httpx.TimeoutException as e:
            # Không retry: gọi lại cũng chậm như vậy (máy chạy CPU) — báo rõ cách khắc phục.
            raise LLMError(f"Ollama quá thời gian chờ {self.timeout_s:.0f}s ({self.model}). Tăng OLLAMA_TIMEOUT_S "
                           "hoặc dùng model nhỏ hơn (OLLAMA_MODEL, vd. qwen2.5:3b).") from e
        if r.status_code == 429:
            raise RateLimitError("Ollama 429", None)
        if r.status_code >= 500:
            raise TransientError(f"HTTP {r.status_code}")
        if r.status_code != 200:
            raise LLMError(f"Ollama lỗi {r.status_code}: {r.text[:300]}")
        return r.json()["message"]["content"]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_llm_client(provider: str | None = None, **overrides) -> LLMClient:
    """Tạo client theo cấu hình (.env); ``provider`` ghi đè LLM_PROVIDER."""
    s = get_settings()
    provided = provider is not None
    provider = (provider or s.llm_provider).lower()
    common = dict(temperature=s.llm_temperature, max_tokens=s.llm_max_tokens, timeout_s=s.llm_timeout_s,
                  max_rpm=s.llm_max_rpm, max_retries=s.llm_max_retries, backoff_base_s=s.llm_backoff_base_s,
                  cache=DiskCache(enabled=s.llm_cache))
    common.update(overrides)
    if provider == "gemini":
        return GeminiClient(s.gemini_model, s.gemini_api_key, **common)
    if provider == "ollama":
        common["timeout_s"] = overrides.get("timeout_s", s.ollama_timeout_s)
        return OllamaClient(s.ollama_model, s.ollama_base_url, num_ctx=s.ollama_num_ctx,
                            keep_alive=s.ollama_keep_alive, **common)
    nguon = "tham số provider" if provided else (
        "biến môi trường LLM_PROVIDER của shell (ghi đè .env — xóa bằng "
        "`Remove-Item Env:LLM_PROVIDER` hoặc `unset LLM_PROVIDER`)" if "LLM_PROVIDER" in os.environ
        else "LLM_PROVIDER trong .env")
    raise LLMError(f"LLM_PROVIDER='{provider}' không hỗ trợ (gemini | ollama); giá trị lấy từ {nguon}")
