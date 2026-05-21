from __future__ import annotations

import json

from app.config import load_settings
from app.smoke_tests.server import run_backend_server, wait_for_json


def main() -> int:
    load_settings()
    host = "127.0.0.1"
    port = 8080
    url = f"http://{host}:{port}/api/health"
    passed = False

    print("Lucero Phase 2 FastAPI health smoke test")
    print("----------------------------------------")
    print(f"Starting backend at {url}")

    try:
        with run_backend_server(host=host, port=port):
            payload = wait_for_json(url)
            passed = True
            print("PASS FastAPI health endpoint responded.")
            print(f"Response: {json.dumps(payload, sort_keys=True)}")
        return 0
    except Exception as exc:
        print("FAIL FastAPI health endpoint did not respond cleanly.")
        print(f"Reason: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
