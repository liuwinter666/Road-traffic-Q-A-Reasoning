"""Nạp prompt có phiên bản từ ``src/llm/prompts/<tên>_v<số>.md``.

Định dạng file:

    ---
    id: extraction
    version: 1
    mo_ta: ...
    ---
    ## system
    ...
    ## user
    ... {bien} ...

Mặc định nạp phiên bản cao nhất; ghi rõ ``version`` để cố định khi đánh giá. Mã prompt ``<id>@v<version>``
được ghi vào kết quả để truy vết phản hồi nào sinh từ prompt nào.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

from src.config import PROMPTS_DIR


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    system: str
    user: str

    @property
    def ma(self) -> str:
        return f"{self.id}@v{self.version}"

    def render(self, **kw) -> str:
        return self.user.format(**kw)


def load_prompt(name: str, version: int | None = None) -> Prompt:
    files = sorted(PROMPTS_DIR.glob(f"{name}_v*.md"), key=lambda p: int(re.search(r"_v(\d+)", p.stem).group(1)))
    if version is not None:
        files = [p for p in files if p.stem == f"{name}_v{version}"]
    if not files:
        raise FileNotFoundError(f"Không có prompt '{name}' (v{version}) trong {PROMPTS_DIR}")
    text = files[-1].read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    meta, body = yaml.safe_load(m.group(1)), m.group(2)
    parts = re.split(r"^## (system|user)\s*$", body, flags=re.M)
    sec = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    return Prompt(meta["id"], int(meta["version"]), sec.get("system", ""), sec["user"])
