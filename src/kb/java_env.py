"""Dò tìm Java và cấu hình owlready2 để gọi Pellet/HermiT.

Thứ tự ưu tiên: biến `JAVA_EXE` trong `.env` → `%JAVA_HOME%/bin/java` → `java` trong PATH →
JDK portable trong `%USERPROFILE%/.jdks/` (bản mới nhất).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from loguru import logger

from src.config import get_settings


class JavaNotFoundError(RuntimeError):
    """Không tìm thấy Java runtime, reasoner không chạy được."""


def find_java() -> str | None:
    """Trả về đường dẫn tuyệt đối tới `java` (hoặc `java.exe`), hoặc None nếu không có."""
    configured = get_settings().java_exe.strip()
    if configured:
        if Path(configured).is_file():
            return configured
        logger.warning("JAVA_EXE={} không tồn tại, thử các cách khác", configured)

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        for name in ("java.exe", "java"):
            cand = Path(java_home) / "bin" / name
            if cand.is_file():
                return str(cand)

    if found := shutil.which("java"):
        return found
    # JDK portable cài trong %USERPROFILE%/.jdks (cách cài của project) — chọn bản mới nhất
    for cand in sorted(Path.home().glob(".jdks/jdk-*/bin/java*"), reverse=True):
        if cand.name in ("java.exe", "java"):
            logger.debug("JAVA_EXE trống — dùng JDK tìm thấy tại {}", cand)
            return str(cand)
    return None


def java_version(java_path: str) -> str:
    """Chạy `java -version` và trả về dòng đầu tiên (Java in ra stderr)."""
    proc = subprocess.run(
        [java_path, "-version"], capture_output=True, text=True, timeout=30
    )
    out = (proc.stderr or proc.stdout).strip().splitlines()
    return out[0] if out else "unknown"


def configure_owlready() -> str:
    """Gán `owlready2.JAVA_EXE` và bộ nhớ JVM. Ném `JavaNotFoundError` nếu không có Java."""
    import owlready2

    java = find_java()
    if not java:
        raise JavaNotFoundError(
            "Không tìm thấy Java. Cài JDK 25+ rồi đặt JAVA_EXE trong .env "
            "hoặc thêm java vào PATH."
        )
    owlready2.JAVA_EXE = java
    owlready2.reasoning.JAVA_MEMORY = get_settings().java_memory_mb
    logger.debug("owlready2 dùng Java tại {}", java)
    return java
