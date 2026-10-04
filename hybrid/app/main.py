from __future__ import annotations

import json
import mimetypes
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from storage import delete_case, get_case, get_value, init_db, list_cases, set_value, upsert_case
from workflow import validate_case, workflow_state

ROOT = Path(__file__).resolve().parents[2]
HOST = "127.0.0.1"
PORT = int(os.environ.get("SCHOOLSVS_PORT", "8768"))
VERSION = "0.2.0"


class Handler(BaseHTTPRequestHandler):
    server_version = "SchoolSVS-Hybrid/0.2"

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _serve_file(self, path: Path):
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        mime, _ = mimetypes.guess_type(str(path))
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (mime or "application/octet-stream") + ("; charset=utf-8" if mime and mime.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/health":
            return self._json({"ok": True, "engine": "python", "version": VERSION, "port": PORT})
        if path == "/api/cases":
            return self._json({"ok": True, "cases": list_cases()})
        if path.startswith("/api/cases/"):
            case_id = path.removeprefix("/api/cases/")
            case = get_case(case_id)
            return self._json({"ok": bool(case), "case": case}, 200 if case else 404)
        if path == "/api/state":
            return self._json({
                "ok": True,
                "cases": list_cases(),
                "counter": get_value("counter", 1),
                "settings": get_value("settings", {}),
            })
        if path.startswith("/api/workflow/"):
            case_id = path.removeprefix("/api/workflow/")
            case = get_case(case_id)
            if not case:
                return self._json({"ok": False, "error": "사안을 찾을 수 없습니다."}, 404)
            return self._json({"ok": True, "workflow": workflow_state(case)})

        if path in ("", "/"):
            relative = "hybrid/web/index.html"
        elif path.endswith("/"):
            relative = path.lstrip("/") + "index.html"
        else:
            relative = path.lstrip("/")
        target = (ROOT / relative).resolve()
        if ROOT not in target.parents and target != ROOT:
            self.send_error(403)
            return
        self._serve_file(target)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            data = self._body()
            if path == "/api/cases":
                result = validate_case(data)
                if not result["ok"]:
                    return self._json({"ok": False, "validation": result}, 400)
                upsert_case(data)
                return self._json({"ok": True, "case": data, "validation": result})
            if path == "/api/validate":
                return self._json({"ok": True, "validation": validate_case(data), "workflow": workflow_state(data)})
            if path == "/api/state":
                cases = data.get("cases") or []
                incoming_ids = {str(case.get("id")) for case in cases if case.get("id")}
                existing = list_cases()
                removed = 0
                for case in existing:
                    case_id = str(case.get("id") or "")
                    if case_id and case_id not in incoming_ids:
                        if delete_case(case_id):
                            removed += 1
                for case in cases:
                    if case.get("id"):
                        upsert_case(case)
                set_value("counter", data.get("counter", 1))
                set_value("settings", data.get("settings", {}))
                return self._json({"ok": True, "imported": len(cases), "removed": removed})
            self._json({"ok": False, "error": "지원하지 않는 API입니다."}, 404)
        except ValueError as e:
            self._json({"ok": False, "error": str(e)}, 400)
        except Exception as e:
            self._json({"ok": False, "error": f"서버 처리 오류: {e}"}, 500)

    def do_DELETE(self):
        path = unquote(urlparse(self.path).path)
        if path.startswith("/api/cases/"):
            case_id = path.removeprefix("/api/cases/")
            return self._json({"ok": delete_case(case_id)})
        self._json({"ok": False, "error": "지원하지 않는 API입니다."}, 404)

    def log_message(self, fmt, *args):
        print("[SchoolSVS]", fmt % args)


def run():
    init_db()
    url = f"http://{HOST}:{PORT}/hybrid/web/index.html"
    print(f"SchoolSVS Hybrid v{VERSION}: {url}")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    run()
