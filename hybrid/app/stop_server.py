from __future__ import annotations

import json
from pathlib import Path
from urllib import request

BASE_DIR = Path(__file__).resolve().parents[1]
SERVER_INFO = BASE_DIR / "data" / "server.json"
APP_ID = "schoolsvs-hybrid"


def stop() -> bool:
    if not SERVER_INFO.exists():
        return False
    try:
        info = json.loads(SERVER_INFO.read_text(encoding="utf-8"))
        port = int(info.get("port") or 0)
        if info.get("appId") != APP_ID or port <= 0:
            return False
        health_url = f"http://127.0.0.1:{port}/api/health"
        with request.urlopen(health_url, timeout=1.5) as res:
            health = json.loads(res.read().decode("utf-8"))
        if health.get("appId") != APP_ID:
            return False
        req = request.Request(f"http://127.0.0.1:{port}/api/shutdown", data=b"{}", headers={"Content-Type":"application/json"}, method="POST")
        with request.urlopen(req, timeout=2.0) as res:
            return 200 <= res.status < 300
    except Exception:
        return False


if __name__ == "__main__":
    stop()
