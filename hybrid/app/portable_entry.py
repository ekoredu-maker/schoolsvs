from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import threading
import traceback
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import main

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
SERVER_INFO = DATA_DIR / "server.json"
BROWSER_PROFILE = DATA_DIR / "browser-profile"
STARTUP_LOG = DATA_DIR / "startup.log"


class PortableHandler(main.Handler):
    server_version = "SchoolSVS-Portable/0.20.2"

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/shutdown":
            self._json({"ok": True, "appId": main.APP_ID, "message": "SchoolSVS를 종료합니다."})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        super().do_POST()


def _append_log(message: str) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        with STARTUP_LOG.open("a", encoding="utf-8") as fp:
            fp.write(f"[{timestamp}] {message.rstrip()}\n")
    except Exception:
        pass


def _show_error(message: str) -> None:
    text = (
        "SchoolSVS를 시작하지 못했습니다.\n\n"
        + message
        + "\n\n자세한 내용: hybrid\\data\\startup.log"
    )
    try:
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(0, text, "SchoolSVS 시작 오류", 0x10)
            return
    except Exception:
        pass
    print(text, file=sys.stderr)


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


def _launch_app_window(url: str) -> subprocess.Popen | None:
    browsers = _browser_candidates()
    if browsers:
        try:
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
            _append_log(f"Browser launched: {browser}")
            # 중요: Edge/Chrome의 최초 launcher 프로세스가 바로 끝나는 경우가 있어도
            # SchoolSVS 서버는 종료하지 않는다. 종료는 UI 또는 Stop launcher에서만 수행한다.
            return proc
        except Exception as exc:
            _append_log(f"App-mode browser launch failed: {exc!r}")

    try:
        opened = bool(webbrowser.open(url))
        _append_log(f"Default browser open requested: opened={opened}, url={url}")
        if not opened:
            _show_error(f"브라우저를 자동으로 열지 못했습니다.\n다음 주소를 직접 여세요.\n{url}")
    except Exception as exc:
        _append_log(f"Default browser launch failed: {exc!r}")
        _show_error(f"브라우저 실행 중 오류가 발생했습니다.\n{url}")
    return None


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


def create_portable_server():
    return main.ThreadingHTTPServer((main.HOST, 0), PortableHandler)


def run() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _append_log(f"Starting SchoolSVS portable. python={sys.executable}")
    main.init_db()
    main.TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    server = create_portable_server()
    port = int(server.server_address[1])
    url = f"http://{main.HOST}:{port}/hybrid/web/index.html"
    _write_server_info(port, url)
    _append_log(f"Server ready: {url}")
    threading.Timer(0.7, lambda: _launch_app_window(url)).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        SERVER_INFO.unlink(missing_ok=True)
        _append_log("SchoolSVS server stopped.")


def _main() -> int:
    try:
        run()
        return 0
    except Exception:
        detail = traceback.format_exc()
        _append_log("FATAL STARTUP ERROR\n" + detail)
        _show_error(detail.splitlines()[-1] if detail.splitlines() else "알 수 없는 시작 오류")
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
