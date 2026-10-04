from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "schoolsvs.db"


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


def upsert_case(data: dict[str, Any]) -> dict[str, Any]:
    case_id = str(data.get("id") or "").strip()
    if not case_id:
        raise ValueError("사안 id가 없습니다.")
    now = _now()
    payload = json.dumps(data, ensure_ascii=False)
    with connect() as conn:
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
                data.get("receivedAt") or data.get("received_at") or data.get("reportDate"),
                payload,
                created_at,
                now,
            ),
        )
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
        conn.execute(
            """INSERT INTO kv(key,value,updated_at) VALUES(?,?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, json.dumps(value, ensure_ascii=False), _now()),
        )


def get_value(key: str, fallback: Any = None) -> Any:
    with connect() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else fallback
