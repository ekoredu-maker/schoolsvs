from __future__ import annotations

import base64
import json
import mimetypes
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from document_readiness import document_readiness
from form10_markers import apply_form10_markers_to_hwpx
from form10_student_rows import apply_student_rows_to_hwpx
from hwpx_engine import (
    TEMPLATE_DIR,
    generate_document,
    get_structure_report,
    inspect_template,
    list_documents,
    load_registry,
    register_template,
)
from mapping_service import build_mapping_workspace, save_mapping, source_catalog
from storage import delete_case, get_case, get_value, init_db, list_cases, set_value, upsert_case
from student_profiles import consent_readiness, profile_readiness
from template_builder import build_template, load_build_report
from workflow import calculate_deadlines, load_rules, validate_case, workflow_state

ROOT = Path(__file__).resolve().parents[2]
HOST = "127.0.0.1"
PORT = int(os.environ.get("SCHOOLSVS_PORT", "8768"))
VERSION = "0.16.0"

FORM10_DIRECT_TOKENS = {
    "INVESTIGATION_MODE", "NO2_ACTION_DATE", "VIOLENCE_TYPE", "SEPARATION_PERIOD",
    "OTHER_MATTERS", "OTHER_SCHOOL_NAME", "OTHER_SCHOOL_NOTIFY_AT",
    "OTHER_SCHOOL_NOTIFY_METHOD", "OTHER_SCHOOL_RECIPIENT", "OTHER_SCHOOL_CONTACT",
    "VICTIM_INTERVIEW_TIME", "PERP_INTERVIEW_TIME", "VICTIM_RECOVERY_OPINION",
    "PERP_RECOVERY_OPINION", "RELATED_STUDENT_ROWS",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "SchoolSVS-Hybrid/0.16"

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
        content_type = mime or "application/octet-stream"
        if path.suffix.lower() == ".hwpx":
            content_type = "application/octet-stream"
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(path.name)}")
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if path == "/api/health":
            rules = load_rules()
            return self._json({
                "ok": True,
                "engine": "python",
                "version": VERSION,
                "port": PORT,
                "rulesVersion": rules.get("version"),
                "documentRegistryVersion": load_registry().get("version"),
            })
        if path == "/api/rules":
            return self._json({"ok": True, "rules": load_rules()})
        if path == "/api/documents":
            docs = list_documents()
            return self._json({
                "ok": True,
                "documents": docs,
                "templateDir": str(TEMPLATE_DIR),
                "readyCount": sum(1 for d in docs if d.get("builtTemplateReady")),
            })
        if path == "/api/documents/sources":
            return self._json({"ok": True, "sources": source_catalog()})
        if path == "/api/documents/mapping":
            key = (query.get("key") or [""])[0]
            try:
                workspace = build_mapping_workspace(key)
            except KeyError as e:
                return self._json({"ok": False, "error": str(e)}, 404)
            return self._json({"ok": True, "workspace": workspace})
        if path == "/api/documents/build-report":
            key = (query.get("key") or [""])[0]
            report = load_build_report(key)
            return self._json({"ok": bool(report), "report": report}, 200 if report else 404)
        if path == "/api/documents/structure":
            key = (query.get("key") or [""])[0]
            report = get_structure_report(key)
            return self._json({"ok": bool(report), "report": report}, 200 if report else 404)
        if path == "/api/documents/inspect":
            key = (query.get("key") or [""])[0]
            registry = load_registry()
            doc = (registry.get("documents") or {}).get(key)
            if not doc:
                return self._json({"ok": False, "error": "등록되지 않은 문서입니다."}, 404)
            template = TEMPLATE_DIR / str(doc.get("template") or "")
            try:
                info = inspect_template(template)
            except FileNotFoundError as e:
                return self._json({"ok": False, "error": str(e), "templateReady": False}, 404)
            except ValueError as e:
                return self._json({"ok": False, "error": str(e), "templateReady": True}, 400)
            return self._json({"ok": True, "document": key, "inspection": info})
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
            return self._json({
                "ok": True,
                "workflow": workflow_state(case),
                "studentProfiles": profile_readiness(case),
                "consentProfiles": consent_readiness(case),
            })

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
                    return self._json({"ok": False, "validation": result, "workflow": workflow_state(data)}, 400)
                upsert_case(data)
                return self._json({
                    "ok": True,
                    "case": data,
                    "validation": result,
                    "workflow": workflow_state(data),
                    "studentProfiles": profile_readiness(data),
                    "consentProfiles": consent_readiness(data),
                })
            if path == "/api/validate":
                return self._json({
                    "ok": True,
                    "validation": validate_case(data),
                    "workflow": workflow_state(data),
                    "deadlines": calculate_deadlines(data),
                    "studentProfiles": profile_readiness(data),
                    "consentProfiles": consent_readiness(data),
                })
            if path == "/api/student-profiles/readiness":
                return self._json({
                    "ok": True,
                    "form10": profile_readiness(data),
                    "consent": consent_readiness(data),
                })
            if path == "/api/documents/readiness":
                key = str(data.get("documentKey") or "").strip()
                case = data.get("case")
                if not isinstance(case, dict):
                    return self._json({"ok": False, "error": "점검할 사안 데이터가 없습니다."}, 400)
                settings = data.get("settings") if isinstance(data.get("settings"), dict) else get_value("settings", {})
                return self._json({"ok": True, "readiness": document_readiness(key, case, settings=settings)})
            if path == "/api/documents/register":
                key = str(data.get("documentKey") or "").strip()
                file_name = str(data.get("fileName") or "").strip()
                encoded = str(data.get("base64") or "")
                if not key or not encoded:
                    return self._json({"ok": False, "error": "서식키와 HWPX 파일이 필요합니다."}, 400)
                try:
                    file_bytes = base64.b64decode(encoded, validate=True)
                except Exception:
                    return self._json({"ok": False, "error": "HWPX 파일 데이터가 올바르지 않습니다."}, 400)
                result = register_template(key, file_bytes, original_name=file_name)
                return self._json({"ok": True, **result})
            if path == "/api/documents/mapping":
                key = str(data.get("documentKey") or "").strip()
                items = data.get("items") or []
                if not isinstance(items, list):
                    return self._json({"ok": False, "error": "매핑 항목 형식이 올바르지 않습니다."}, 400)
                result = save_mapping(key, items, status=str(data.get("status") or "draft"))
                return self._json({"ok": True, "mapping": result})
            if path == "/api/documents/build":
                key = str(data.get("documentKey") or "").strip()
                if not key:
                    return self._json({"ok": False, "error": "서식키가 필요합니다."}, 400)
                report = build_template(key)
                return self._json({"ok": True, "report": report})
            if path == "/api/documents/generate":
                key = str(data.get("documentKey") or "").strip()
                case = data.get("case")
                if not case and data.get("caseId"):
                    case = get_case(str(data.get("caseId")))
                if not isinstance(case, dict):
                    return self._json({"ok": False, "error": "문서 생성에 사용할 사안 데이터가 없습니다."}, 400)
                settings = data.get("settings")
                if not isinstance(settings, dict):
                    settings = get_value("settings", {})
                readiness = document_readiness(key, case, settings=settings)
                if key == "form10_case_report" and not readiness.get("ready"):
                    return self._json({
                        "ok": False,
                        "error": "서식10 생성 전 필수 점검을 완료하세요.",
                        "readiness": readiness,
                    }, 409)
                result = generate_document(key, case, settings=settings, output_name=data.get("outputName"))
                student_rows = None
                form10_markers = None
                missing_tokens = list(result.missing_tokens)
                if key == "form10_case_report":
                    student_rows = apply_student_rows_to_hwpx(result.output_path, case)
                    form10_markers = apply_form10_markers_to_hwpx(result.output_path, case)
                    missing_tokens = [token for token in missing_tokens if token not in FORM10_DIRECT_TOKENS]
                relative = result.output_path.relative_to(ROOT).as_posix()
                return self._json({
                    "ok": True,
                    "documentKey": result.document_key,
                    "fileName": result.output_path.name,
                    "downloadUrl": "/" + relative,
                    "replacedTokens": result.replaced_tokens,
                    "missingTokens": missing_tokens,
                    "studentRows": student_rows,
                    "form10Markers": form10_markers,
                    "readiness": readiness,
                    "warning": "템플릿 구조 검증 전 시험 생성본입니다." if missing_tokens else None,
                })
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
        except FileNotFoundError as e:
            self._json({"ok": False, "error": str(e)}, 404)
        except (ValueError, KeyError) as e:
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
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    url = f"http://{HOST}:{PORT}/hybrid/web/index.html"
    print(f"SchoolSVS Hybrid v{VERSION}: {url}")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    run()
