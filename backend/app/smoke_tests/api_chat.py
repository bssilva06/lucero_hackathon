from __future__ import annotations

import json
from urllib.request import Request, urlopen

from app.config import load_settings
from app.smoke_tests.server import run_backend_server


def main() -> int:
    settings = load_settings()
    host = "127.0.0.1"
    port = 8080

    print("Lucero Phase 2 FastAPI chat smoke test")
    print("--------------------------------------")
    print(f"Model: {settings.gemini_reasoning_model}")
    print("Starting backend and posting a non-legal diagnostic chat request.")

    try:
        with run_backend_server(host=host, port=port) as base_url:
            payload = _post_json(
                f"{base_url}/api/chat",
                {
                    "message": (
                        "Health check only. Reply with exactly: Lucero chat smoke test passed"
                    ),
                    "session_id": "smoke_chat_session",
                    "user_id": "smoke_chat_user",
                },
            )
    except Exception as exc:
        print("FAIL FastAPI chat endpoint did not respond cleanly.")
        print(f"Reason: {exc}")
        return 1

    response_text = str(payload.get("response", "")).strip()
    if not response_text:
        print("FAIL Chat endpoint returned an empty response.")
        print(f"Payload: {json.dumps(payload, sort_keys=True)[:2_000]}")
        return 1

    print("PASS FastAPI chat endpoint returned a response.")
    print(f"Response: {response_text}")

    tool_calls = payload.get("tool_calls", [])
    if isinstance(tool_calls, list):
        print(f"Tool calls captured: {len(tool_calls)}")

    return 0


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        body = response.read().decode("utf-8")
        if response.status != 200:
            raise RuntimeError(f"Unexpected HTTP status: {response.status}: {body}")
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise RuntimeError("Expected JSON object response")
        return parsed


if __name__ == "__main__":
    raise SystemExit(main())
