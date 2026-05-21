from __future__ import annotations

import json
from urllib.request import Request, urlopen

from app.config import load_settings
from app.smoke_tests.server import run_backend_server


def main() -> int:
    settings = load_settings()
    host = "127.0.0.1"
    port = 8080

    print("Lucero Phase 2 FastAPI chat retrieval smoke test")
    print("------------------------------------------------")
    print(f"Model: {settings.gemini_reasoning_model}")
    print("Starting backend and asking about the fixture corpus.")

    try:
        with run_backend_server(host=host, port=port) as base_url:
            payload = _post_json(
                f"{base_url}/api/chat",
                {
                    "message": (
                        "Use the MongoDB find tool with database lucero and collection chunks. "
                        "Use this exact filter: "
                        '{"ingestion_run_id":"fixture-smoke-test","status":"active"}. '
                        "Return one result. Include its exact section_citation and copy one exact "
                        "short phrase from its text field."
                    ),
                    "session_id": "smoke_retrieval_session",
                    "user_id": "smoke_retrieval_user",
                },
            )
    except Exception as exc:
        print("FAIL FastAPI chat retrieval endpoint did not respond cleanly.")
        print(f"Reason: {exc}")
        return 1

    response_text = str(payload.get("response", "")).strip()
    tool_calls = payload.get("tool_calls", [])

    if not response_text:
        print("FAIL Chat retrieval endpoint returned an empty response.")
        print(f"Payload: {json.dumps(payload, sort_keys=True)[:2_000]}")
        return 1

    if not isinstance(tool_calls, list) or not tool_calls:
        print("FAIL Chat retrieval did not capture any MCP tool calls.")
        print(f"Response: {response_text}")
        print(f"Payload: {json.dumps(payload, sort_keys=True)[:2_000]}")
        return 1

    tool_names = [str(call.get("name", "")) for call in tool_calls if isinstance(call, dict)]
    if not any(name in {"find", "aggregate", "collection-schema", "collection-indexes"} for name in tool_names):
        print("FAIL Chat retrieval did not capture expected MongoDB MCP tool names.")
        print(f"Tool names: {tool_names}")
        return 1

    if "could not find" in response_text.lower() or "no active documents" in response_text.lower():
        print("FAIL Chat response said no fixture documents were found.")
        print(f"Response: {response_text}")
        print(f"Tool names: {tool_names}")
        print(f"Payload: {json.dumps(payload, sort_keys=True)[:2_000]}")
        return 1

    expected_markers = {"9 USCIS-PM B.5", "USCIS G-1055", "CDJ Post Info"}
    if not any(marker in response_text for marker in expected_markers):
        print("FAIL Chat response did not include a known fixture section citation.")
        print(f"Response: {response_text}")
        print(f"Tool names: {tool_names}")
        print(f"Payload: {json.dumps(payload, sort_keys=True)[:2_000]}")
        return 1

    exact_fixture_phrases = {
        "Extreme hardship factors for a provisional unlawful presence waiver",
        "family ties",
        "paper filing and online filing",
        "National Visa Center document collection instructions",
    }
    if not any(phrase in response_text for phrase in exact_fixture_phrases):
        print("FAIL Chat response did not include an exact phrase from a fixture text field.")
        print(f"Response: {response_text}")
        print(f"Tool names: {tool_names}")
        print(f"Payload: {json.dumps(payload, sort_keys=True)[:2_000]}")
        return 1

    print("PASS FastAPI chat retrieval returned a grounded response.")
    print(f"Tool calls captured: {', '.join(tool_names)}")
    print(f"Response: {response_text}")
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
