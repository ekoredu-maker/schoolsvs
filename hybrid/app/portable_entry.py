from __future__ import annotations

import ctypes
import json
import os
import re
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import main
from hwpx_engine import OUTPUT_DIR
from official_2026_direct import FORM10, FORM12, generate_official_2026, is_official_2026_template

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
SERVER_INFO = DATA_DIR / "server.json"
STARTUP_LOG = DATA_DIR / "startup.log"
DIRECT_KEYS = {FORM10, FORM12}

_ORIGINAL_GENERATE = main.generate_document
_ORIGINAL_READINESS = main.document_readiness
_ORIGINAL_LIST_DOCUMENTS = main.list_documents


def _append_log(message: str) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        with STARTUP_LOG.open("a", encoding="utf-8") as fp:
            fp.write(f"[{timestamp}] {message.rstrip()}\n")
    except Exception:
        pass


def _official_template_path(document_key: str) -> Path | None:
    doc = (main.load_registry().get("documents") or {}).get(document_key) or {}
    name = str(doc.get("template") or "").strip()
    return (main.TEMPLATE_DIR / name) if name else None


def _direct_official_ready(document_key: str) -> bool:
    if document_key not in DIRECT_KEYS:
        return False
    path = _official_template_path(document_key)
    return bool(path and is_official_2026_template(document_key, path))


def _direct_readiness(document_key: str, case: dict, settings: dict | None = None):
    result = _ORIGINAL_READINESS(document_key, case, settings=settings)
    if not _direct_official_ready(document_key):
        return result
    result = dict(result)
    result.update({
        "templateReady": True,
        "builtTemplateReady": True,
        "mappingReady": True,
        "officialVerified": True,
        "experimentalOnly": False,
        "directOfficial2026": True,
        "fidelityNote": "등록된 HWPX가 확인된 2026 공식 구조와 일치합니다. 원본 구조를 유지하고 값 셀만 직접 입력합니다.",
    })
    blocking = []
    for section in result.get("sections") or []:
        label = str(section.get("label") or "입력정보")
        for missing in section.get("missing") or []:
            blocking.append(f"{label}: {missing}")
    result["blocking"] = blocking
    result["ready"] = bool(result.get("contentReady"))
    return result


def _direct_list_documents():
    docs = _ORIGINAL_LIST_DOCUMENTS()
    for doc in docs:
        key = str(doc.get("key") or "")
        if _direct_official_ready(key):
            doc.update({
                "templateReady": True,
                "builtTemplateReady": True,
                "mappingReady": True,
                "directOfficial2026": True,
            })
    return docs


def _safe_output_name(document_key: str, case: dict, requested: str | None = None) -> str:
    if requested:
        name = Path(str(requested)).name
        if not name.lower().endswith(".hwpx"):
            name += ".hwpx"
        return re.sub(r'[<>:"/\\|?*]+', "_", name)
    form = "서식10" if document_key == FORM10 else "서식12"
    case_no = str(case.get("caseNo") or "사안번호미정")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = f"{form}_{case_no}_{stamp}.hwpx"
    return re.sub(r'[<>:"/\\|?*]+', "_", name)


def _direct_generate(document_key: str, case: dict, settings: dict | None = None, output_name: str | None = None):
    if not _direct_official_ready(document_key):
        return _ORIGINAL_GENERATE(document_key, case, settings=settings, output_name=output_name)
    template = _official_template_path(document_key)
    if template is None:
        raise FileNotFoundError("2026 공식 HWPX 원본이 등록되지 않았습니다.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / _safe_output_name(document_key, case, output_name)
    result = generate_official_2026(document_key, template, case, settings or {}, output)
    _append_log(f"Official 2026 direct HWPX generated: {document_key} -> {output.name}")
    return result


def _install_official_2026_runtime() -> None:
    main.VERSION = "0.21.0-rc2"
    main.document_readiness = _direct_readiness
    main.list_documents = _direct_list_documents
    main.generate_document = _direct_generate
    states = {key: _direct_official_ready(key) for key in sorted(DIRECT_KEYS)}
    _append_log("Official 2026 HWPX direct runtime installed: " + json.dumps(states, ensure_ascii=False))


_install_official_2026_runtime()


class PortableHandler(main.Handler):
    server_version = "SchoolSVS-Portable/0.21.0-rc2"

    def log_message(self, fmt, *args):
        message = fmt % args
        _append_log("HTTP " + message)
        print("[SchoolSVS]", message)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/shutdown":
            self._json({"ok": True, "appId": main.APP_ID, "message": "SchoolSVS를 종료합니다."})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        super().do_POST()


def _show_error(message: str) -> None:
    text = "SchoolSVS를 시작하지 못했습니다.\n\n" + message + "\n\n자세한 내용: hybrid\\data\\startup.log"
    try:
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(0, text, "SchoolSVS 시작 오류", 0x10)
            return
    except Exception:
        pass
    print(text, file=sys.stderr)


def _write_server_info(port: int, url: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "appId": main.APP_ID, "version": main.VERSION, "pid": os.getpid(),
        "port": port, "url": url, "startedAt": datetime.now(timezone.utc).isoformat(),
    }
    SERVER_INFO.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_portable_server():
    return main.ThreadingHTTPServer((main.HOST, 0), PortableHandler)


def _wait_for_health(port: int, timeout_seconds: float = 6.0) -> bool:
    health_url = f"http://{main.HOST}:{port}/api/health"
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if response.status == 200 and payload.get("appId") == main.APP_ID:
                _append_log(f"Health check OK: {health_url}")
                return True
        except Exception as exc:
            last_error = exc
            time.sleep(0.15)
    _append_log(f"Health check FAILED: {health_url}; last_error={last_error!r}")
    return False


def _launch_safe_browser(url: str) -> None:
    _append_log(f"Opening default browser in safe mode: {url}")
    try:
        if os.name == "nt" and hasattr(os, "startfile"):
            os.startfile(url)  # type: ignore[attr-defined]
            _append_log("Default browser launch requested with os.startfile().")
            return
    except Exception as exc:
        _append_log(f"os.startfile browser launch failed: {exc!r}")
    try:
        opened = bool(webbrowser.open_new(url))
        _append_log(f"webbrowser.open_new returned opened={opened}")
        if not opened:
            _show_error(f"브라우저를 자동으로 열지 못했습니다.\n다음 주소를 직접 여세요.\n{url}")
    except Exception as exc:
        _append_log(f"Default browser launch failed: {exc!r}")
        _show_error(f"브라우저 실행 중 오류가 발생했습니다.\n다음 주소를 직접 여세요.\n{url}")


def run() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _append_log("=" * 64)
    _append_log(f"Starting SchoolSVS portable. python={sys.executable}")
    main.init_db()
    main.TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    server = create_portable_server()
    port = int(server.server_address[1])
    url = f"http://{main.HOST}:{port}/hybrid/web/index.html"
    _write_server_info(port, url)
    _append_log(f"Server socket created: {url}")
    server_thread = threading.Thread(target=server.serve_forever, name="SchoolSVS-HTTP", daemon=False)
    server_thread.start()
    try:
        if not _wait_for_health(port):
            raise RuntimeError("SchoolSVS localhost 서버가 시작되었지만 자체 상태확인에 응답하지 않습니다.")
        _append_log("Server health verified. Browser launch begins.")
        _launch_safe_browser(url)
        server_thread.join()
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
        if server_thread.is_alive():
            server_thread.join(timeout=2.0)
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
