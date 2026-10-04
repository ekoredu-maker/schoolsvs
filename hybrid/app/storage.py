from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "schoolsvs.db"
BACKUP_DIR = Path(__file__).resolve().parents[1] / "data" / "backups"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                case_no TEXT,
                status TEXT,
                received_at TEXT,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cases_case_no ON cases(case_no);
            CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);

            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


def _upsert_case_conn(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    case_id = str(data.get("id") or "").strip()
    if not case_id:
        raise ValueError("사안 id가 없습니다.")
    now = _now()
    payload = json.dumps(data, ensure_ascii=False)
    old = conn.execute("SELECT created_at FROM cases WHERE id=?", (case_id,)).fetchone()
    created_at = old["created_at"] if old else now
    conn.execute(
        """INSERT INTO cases(id, case_no, status, received_at, payload, created_at, updated_at)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             case_no=excluded.case_no,
             status=excluded.status,
             received_at=excluded.received_at,
             payload=excluded.payload,
             updated_at=excluded.updated_at""",
        (
            case_id,
            data.get("caseNo") or data.get("case_no"),
            data.get("status"),
            data.get("recvAt") or data.get("receivedAt") or data.get("received_at") or data.get("reportDate"),
            payload,
            created_at,
            now,
        ),
    )


def _set_value_conn(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """INSERT INTO kv(key,value,updated_at) VALUES(?,?,?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
        (key, json.dumps(value, ensure_ascii=False), _now()),
    )


def upsert_case(data: dict[str, Any]) -> dict[str, Any]:
    with connect() as conn:
        _upsert_case_conn(conn, data)
    return data


def list_cases() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT payload FROM cases ORDER BY updated_at DESC").fetchall()
    return [json.loads(r["payload"]) for r in rows]


def get_case(case_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT payload FROM cases WHERE id=?", (case_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def delete_case(case_id: str) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM cases WHERE id=?", (case_id,))
        return cur.rowcount > 0


def set_value(key: str, value: Any) -> None:
    with connect() as conn:
        _set_value_conn(conn, key, value)


def get_value(key: str, fallback: Any = None) -> Any:
    with connect() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else fallback


def backup_state(reason: str = "manual") -> Path:
    """현재 SQLite 논리 상태를 JSON으로 보존한다. 삭제/전체대조 전에 호출한다."""
    state = {
        "createdAt": _now(),
        "reason": reason,
        "cases": list_cases(),
        "counter": get_value("counter", 1),
        "settings": get_value("settings", {}),
    }
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = BACKUP_DIR / f"state_{stamp}.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def sync_state(
    cases: list[dict[str, Any]],
    counter: Any = 1,
    settings: Any = None,
    *,
    mode: str = "merge",
    allow_empty_reconcile: bool = False,
) -> dict[str, Any]:
    """브라우저 상태를 SQLite에 반영한다.

    merge: 입력된 사안만 추가/갱신하고 SQLite의 다른 사안은 삭제하지 않는다.
    reconcile: 입력 목록에 없는 사안을 삭제한다. 삭제 전 자동 백업하며, 빈 목록으로의 전체삭제는 명시 허용 없이는 차단한다.
    """
    if not isinstance(cases, list):
        raise ValueError("cases는 목록이어야 합니다.")
    mode = str(mode or "merge").lower()
    if mode not in {"merge", "reconcile"}:
        raise ValueError("지원하지 않는 동기화 모드입니다.")

    normalized = [case for case in cases if isinstance(case, dict) and str(case.get("id") or "").strip()]
    existing = list_cases()
    existing_ids = {str(case.get("id") or "") for case in existing if case.get("id")}
    incoming_ids = {str(case.get("id") or "") for case in normalized if case.get("id")}
    removed_ids = sorted(existing_ids - incoming_ids) if mode == "reconcile" else []

    if mode == "reconcile" and existing_ids and not incoming_ids and not allow_empty_reconcile:
        raise ValueError("빈 브라우저 상태로 SQLite 전체 사안을 삭제하는 동작을 차단했습니다.")

    backup = None
    if removed_ids:
        backup = backup_state("state_reconcile_before_delete")

    with connect() as conn:
        for case in normalized:
            _upsert_case_conn(conn, case)
        if mode == "reconcile" and removed_ids:
            conn.executemany("DELETE FROM cases WHERE id=?", [(case_id,) for case_id in removed_ids])
        _set_value_conn(conn, "counter", counter if counter is not None else 1)
        _set_value_conn(conn, "settings", settings if isinstance(settings, dict) else {})

    return {
        "mode": mode,
        "imported": len(normalized),
        "removed": len(removed_ids),
        "removedIds": removed_ids,
        "backup": backup.name if backup else None,
    }
