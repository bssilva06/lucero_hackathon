from __future__ import annotations

import json
from urllib.request import Request, urlopen

from app.config import load_settings
from app.smoke_tests.server import run_backend_server


PROMPT = "Walk me through the I-601A timeline for a Mexican spouse going to CDJ."


def main() -> int:
    settings = load_settings()
    host = "127.0.0.1"
    port = 8080

    print("Lucero CDJ timeline API smoke test")
    print("----------------------------------")
    print(f"Model: {settings.gemini_reasoning_model}")

    try:
        with run_backend_server(host=host, port=port) as base_url:
            payload = _post_json(
                f"{base_url}/api/chat",
                {
                    "message": PROMPT,
                    "session_id": "smoke_cdj_timeline_session",
                    "user_id": "smoke_cdj_timeline_user",
                },
            )
    except Exception as exc:
        print("FAIL CDJ timeline endpoint did not respond cleanly.")
        print(f"Reason: {exc}")
        return 1

    response_text = str(payload.get("response", "")).strip()
    tool_calls = payload.get("tool_calls", [])
    sources = payload.get("sources", [])

    if not response_text:
        print("FAIL CDJ timeline endpoint returned an empty response.")
        print(f"Payload: {json.dumps(payload, sort_keys=True)[:2_000]}")
        return 1

    tool_names = [
        str(call.get("name", ""))
        for call in tool_calls
        if isinstance(call, dict)
    ] if isinstance(tool_calls, list) else []
    for expected_tool in ["search_uscis_policy_manual", "lookup_consular_process"]:
        if expected_tool not in tool_names:
            print(f"FAIL Missing expected tool call: {expected_tool}")
            print(f"Tool names: {tool_names}")
            return 1

    if not isinstance(sources, list) or not sources:
        print("FAIL CDJ timeline endpoint returned no sources.")
        print(f"Payload: {json.dumps(payload, sort_keys=True)[:2_000]}")
        return 1

    citations = [
        str(source.get("section_citation", ""))
        for source in sources
        if isinstance(source, dict)
    ]
    if not any(citation.startswith("9 USCIS-PM H") for citation in citations):
        print("FAIL Sources did not include USCIS Policy Manual Part H.")
        print(f"Citations: {citations}")
        return 1
    if not any(citation.startswith("CDJ Post Instructions") for citation in citations):
        print("FAIL Sources did not include CDJ post instructions.")
        print(f"Citations: {citations}")
        return 1
    if not any(citation.startswith("NVC") for citation in citations):
        print("FAIL Sources did not include NVC records.")
        print(f"Citations: {citations}")
        return 1

    required_terms = ["I-601A", "provisional unlawful presence", "Ciudad Juarez", "CDJ", "NVC", "medical", "ASC"]
    missing_terms = [
        term for term in required_terms if term.casefold() not in response_text.casefold()
    ]
    if missing_terms:
        print("FAIL CDJ timeline response missed expected terms.")
        print(f"Missing: {missing_terms}")
        print(f"Response: {response_text}")
        return 1

    print("PASS CDJ timeline endpoint returned Policy Manual and CDJ/NVC sources.")
    print(f"Tool calls captured: {tool_names}")
    print(f"Citations: {citations}")
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
