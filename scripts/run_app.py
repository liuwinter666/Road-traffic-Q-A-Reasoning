"""Bật API (uvicorn, cổng 8000) rồi giao diện Streamlit (cổng 8501), tự mở trình duyệt; Ctrl+C để tắt.

    python -m scripts.run_app                 # API + giao diện
    python -m scripts.run_app --chi-giao-dien # chỉ giao diện (tự chạy pipeline trong tiến trình)
    python -m scripts.run_app --khong-mo-trinh-duyet

Streamlit chạy headless (không hỏi "Email:" ở lần chạy đầu — câu hỏi đó chặn server khởi động).
Nếu API đã chạy sẵn ở cổng đã chọn thì dùng lại, không bật thêm.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

import httpx

from src.config import ROOT_DIR


def _cong_ban(cong: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", cong)) == 0


def _cho(url: str, giay: int) -> bool:
    for _ in range(giay):
        try:
            httpx.get(url, timeout=1).raise_for_status()
            return True
        except Exception:  # noqa: BLE001
            time.sleep(1)
    return False


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cong-api", type=int, default=8000)
    ap.add_argument("--cong-ui", type=int, default=8501)
    ap.add_argument("--chi-giao-dien", action="store_true")
    ap.add_argument("--khong-mo-trinh-duyet", action="store_true")
    a = ap.parse_args()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
           "TRANSFORMERS_VERBOSITY": "error"}

    if _cong_ban(a.cong_ui):
        print(f"Cổng {a.cong_ui} đang bận — có thể giao diện đã chạy ở cửa sổ khác: http://localhost:{a.cong_ui}\n"
              f"Tắt cửa sổ đó (Ctrl+C) hoặc chạy với --cong-ui khác.", file=sys.stderr)
        return 1

    api = None
    if not a.chi_giao_dien:
        url = f"http://127.0.0.1:{a.cong_api}"
        env.update(API_URL=url, APP_BACKEND="api")
        if _cho(f"{url}/suc-khoe", 1):
            print(f"Dùng API đang chạy sẵn: {url}")
        elif _cong_ban(a.cong_api):
            print(f"Cổng {a.cong_api} bị chiếm bởi chương trình khác — chạy với --cong-api khác.", file=sys.stderr)
            return 1
        else:
            print("Đang bật API...")
            api = subprocess.Popen([sys.executable, "-m", "uvicorn", "src.api.main:app", "--port", str(a.cong_api),
                                    "--log-level", "warning"], cwd=ROOT_DIR, env=env)
            if not _cho(f"{url}/suc-khoe", 90):
                print("API không khởi động được", file=sys.stderr)
                api.terminate()
                return 1
            print(f"API sẵn sàng: {url}/docs")
    else:
        env["APP_BACKEND"] = "truc_tiep"

    ui_url = f"http://localhost:{a.cong_ui}"
    if not a.khong_mo_trinh_duyet:
        def mo():
            if _cho(f"http://127.0.0.1:{a.cong_ui}/_stcore/health", 240):
                print(f"Giao diện sẵn sàng: {ui_url}")
                webbrowser.open(ui_url)
        threading.Thread(target=mo, daemon=True).start()
    try:
        return subprocess.call([sys.executable, "-m", "streamlit", "run", str(ROOT_DIR / "app" / "streamlit_app.py"),
                                "--server.port", str(a.cong_ui), "--server.headless", "true", "--server.address", "127.0.0.1",
                                "--browser.gatherUsageStats", "false"], cwd=ROOT_DIR, env=env)
    except KeyboardInterrupt:
        return 0
    finally:
        if api is not None:
            api.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
