"""Bật API (uvicorn, cổng 8000) rồi giao diện Streamlit (cổng 8501); Ctrl+C để tắt cả hai.

    python -m scripts.run_app                 # API + giao diện
    python -m scripts.run_app --chi-giao-dien # chỉ giao diện (tự chạy pipeline trong tiến trình)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

import httpx

from src.config import ROOT_DIR


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cong-api", type=int, default=8000)
    ap.add_argument("--cong-ui", type=int, default=8501)
    ap.add_argument("--chi-giao-dien", action="store_true")
    a = ap.parse_args()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
           "TRANSFORMERS_VERBOSITY": "error"}
    api = None
    if not a.chi_giao_dien:
        url = f"http://127.0.0.1:{a.cong_api}"
        env.update(API_URL=url, APP_BACKEND="api")
        api = subprocess.Popen([sys.executable, "-m", "uvicorn", "src.api.main:app", "--port", str(a.cong_api)],
                               cwd=ROOT_DIR, env=env)
        for _ in range(60):
            try:
                httpx.get(f"{url}/suc-khoe", timeout=1).raise_for_status()
                print(f"API sẵn sàng: {url}/docs")
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        else:
            print("API không khởi động được", file=sys.stderr)
            api.terminate()
            return 1
    else:
        env["APP_BACKEND"] = "truc_tiep"
    try:
        return subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT_DIR / "app" / "streamlit_app.py"),
                                "--server.port", str(a.cong_ui), "--browser.gatherUsageStats", "false"],
                               cwd=ROOT_DIR, env=env)
    except KeyboardInterrupt:
        return 0
    finally:
        if api is not None:
            api.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
