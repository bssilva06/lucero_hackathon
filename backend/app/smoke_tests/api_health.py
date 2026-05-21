from __future__ import annotations

import json
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

from app.config import load_settings


def main() -> int:
    load_settings()
    host = "127.0.0.1"
    port = 8080
    url = f"http://{host}:{port}/api/health"
    passed = False

    print("Lucero Phase 2 FastAPI health smoke test")
    print("----------------------------------------")
    print(f"Starting backend at {url}")

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        payload = _wait_for_health(url)
        passed = True
        print("PASS FastAPI health endpoint responded.")
        print(f"Response: {json.dumps(payload, sort_keys=True)}")
        return 0
    except Exception as exc:
        print("FAIL FastAPI health endpoint did not respond cleanly.")
        print(f"Reason: {exc}")
        return 1
    finally:
        process.terminate()
        try:
            _, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            _, stderr = process.communicate(timeout=5)

        if not passed and process.returncode not in {0, None} and stderr:
            print()
            print("Server stderr tail:")
            print(stderr[-2_000:])


def _wait_for_health(url: str) -> dict[str, object]:
    deadline = time.monotonic() + 45
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                body = response.read().decode("utf-8")
                if response.status != 200:
                    raise RuntimeError(f"Unexpected HTTP status: {response.status}")
                return json.loads(body)
        except (URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            time.sleep(1)

    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


if __name__ == "__main__":
    raise SystemExit(main())
