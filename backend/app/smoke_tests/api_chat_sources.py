from __future__ import annotations

import json
from urllib.request import Request, urlopen

from app.config import load_settings
from app.smoke_tests.server import run_backend_server


def main() -> int:
    settings = load_settings()
    host = "127.0.0.1"
    port = 8080

    print("Lucero FastAPI chat sources smoke test")
    print("--------------------------------------")
    print(f"Model: {settings.gemini_reasoning_model}")
    print("Starting backend and forcing canonical Policy Manual retrieval.")

    try:
        with run_backend_server(host=host, port=port) as base_url:
            payload = _post_json(
                f"{base_url}/api/chat",
                {
                    "message": (
                        "Call search_uscis_policy_manual with query "
                        "'extreme hardship family ties I-601A' and limit 3. "
                        "Use the retrieved results to answer in two sentences, citing the section citations."
                    ),
                    "session_id": "smoke_sources_session",
                    "user_id": "smoke_sources_user",
                },
            )
    except Exception as exc:
        print("FAIL FastAPI chat sources endpoint did not respond cleanly.")
        print(f"Reason: {exc}")
        return 1

    response_text = str(payload.get("response", "")).strip()
    tool_calls = payload.get("tool_calls", [])
    sources = payload.get("sources", [])

    if not response_text:
        print("FAIL Chat sources endpoint returned an empty response.")
        print(f"Payload: {json.dumps(payload, sort_keys=True)[:2_000]}")
        return 1

    if not isinstance(tool_calls, list) or not any(
        isinstance(call, dict) and call.get("name") == "search_uscis_policy_manual"
        for call in tool_calls
    ):
        print("FAIL Chat sources did not capture search_uscis_policy_manual tool call.")
        print(f"Tool calls: {json.dumps(tool_calls, sort_keys=True)[:2_000]}")
        return 1

    if not isinstance(sources, list) or not sources:
        print("FAIL Chat sources response did not include structured sources.")
        print(f"Payload: {json.dumps(payload, sort_keys=True)[:2_000]}")
        return 1

    first_source = sources[0]
    if not isinstance(first_source, dict):
        print("FAIL First source was not an object.")
        return 1

    citation = str(first_source.get("section_citation", ""))
    chunk_id = str(first_source.get("chunk_id", ""))
    source_url = str(first_source.get("source_url", ""))

    if not citation.startswith(("9 USCIS-PM B", "9 USCIS-PM H")):
        print("FAIL First source did not include a real USCIS Policy Manual citation.")
        print(f"First source: {json.dumps(first_source, sort_keys=True)[:2_000]}")
        return 1

    if chunk_id.startswith("fixture-"):
        print("FAIL Chat sources returned a fixture chunk.")
        print(f"First source: {json.dumps(first_source, sort_keys=True)[:2_000]}")
        return 1

    if not source_url.startswith("https://www.uscis.gov/policy-manual/"):
        print("FAIL First source did not include a USCIS Policy Manual URL.")
        print(f"First source: {json.dumps(first_source, sort_keys=True)[:2_000]}")
        return 1

    source_ids = [
        str(source.get("chunk_id"))
        for source in sources
        if isinstance(source, dict) and source.get("chunk_id")
    ]
    if len(source_ids) != len(set(source_ids)):
        print("FAIL Chat sources returned duplicate chunk ids.")
        print(f"Source ids: {source_ids}")
        return 1

    print("PASS FastAPI chat returned structured citation sources.")
    print(f"Tool calls captured: {[call.get('name') for call in tool_calls if isinstance(call, dict)]}")
    print(f"Sources captured: {len(sources)}")
    print(f"First source: {chunk_id} | {citation} | {source_url}")
    print(f"Response: {response_text}")
    return 0


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=240) as response:
        body = response.read().decode("utf-8")
        if response.status != 200:
            raise RuntimeError(f"Unexpected HTTP status: {response.status}: {body}")
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise RuntimeError("Expected JSON object response")
        return parsed


if __name__ == "__main__":
    raise SystemExit(main())
