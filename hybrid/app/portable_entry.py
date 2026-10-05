from __future__ import annotations

import json
import os
import subprocess
import threading
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import main

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
SERVER_INFO = DATA_DIR / "server.json"
BROWSER_PROFILE = DATA_DIR / "browser-profile"


class PortableHandler(main.Handler):
    server_version = "SchoolSVS-Portable/0.19"

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/shutdown":
            self._json({"ok": True, "appId": main.APP_ID, "message": "SchoolSVS를 종료합니다."})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        super().do_POST()


def _browser_candidates() -> list[Path]:
    env = os.environ
    candidates: list[Path] = []
    for base_name in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = env.get(base_name)
        if not base:
            continue
        root = Path(base)
        candidates.extend([
            root / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            root / "Google" / "Chrome" / "Application" / "chrome.exe",
        ])
    seen: set[str] = set()
    result: list[Path] = []
    for item in candidates:
        key = str(item).lower()
        if key not in seen and item.exists():
            seen.add(key)
            result.append(item)
    return result


def _launch_app_window(url: str, server) -> subprocess.Popen | None:
    browsers = _browser_candidates()
    if not browsers:
        webbrowser.open(url)
        return None

    BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)
    browser = browsers[0]
    args = [
        str(browser),
        f"--app={url}",
        f"--user-data-dir={BROWSER_PROFILE}",
        "--no-first-run",
        "--disable-translate",
        "--start-maximized",
    ]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def monitor() -> None:
        try:
            proc.wait()
        finally:
            try:
                server.shutdown()
            except Exception:
                pass

    threading.Thread(target=monitor, daemon=True).start()
    return proc


def _write_server_info(port: int, url: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "appId": main.APP_ID,
        "version": main.VERSION,
        "pid": os.getpid(),
        "port": port,
        "url": url,
        "startedAt": datetime.now(timezone.utc).isoformat(),
    }
    SERVER_INFO.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run() -> None:
    main.init_db()
    main.TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    server = main.ThreadingHTTPServer((main.HOST, 0), PortableHandler)
    port = int(server.server_address[1])
    url = f"http://{main.HOST}:{port}/hybrid/web/index.html"
    _write_server_info(port, url)
    print(f"SchoolSVS Portable v{main.VERSION}: {url}")
    threading.Timer(0.7, lambda: _launch_app_window(url, server)).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        SERVER_INFO.unlink(missing_ok=True)


if __name__ == "__main__":
    run()
