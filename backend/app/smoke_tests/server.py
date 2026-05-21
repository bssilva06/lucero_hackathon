from __future__ import annotations

import json
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.error import URLError
from urllib.request import urlopen


@contextmanager
def run_backend_server(host: str = "127.0.0.1", port: int = 8080) -> Iterator[str]:
    base_url = f"http://{host}:{port}"
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
    healthy = False

    try:
        wait_for_json(f"{base_url}/api/health")
        healthy = True
        yield base_url
    finally:
        process.terminate()
        try:
            _, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            _, stderr = process.communicate(timeout=5)

        if not healthy and process.returncode not in {0, None} and stderr:
            print()
            print("Server stderr tail:")
            print(stderr[-2_000:])


def wait_for_json(url: str, *, timeout_seconds: int = 45) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
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
