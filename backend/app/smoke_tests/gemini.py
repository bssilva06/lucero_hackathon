from __future__ import annotations

from google import genai

from app.config import load_settings


DEFAULT_FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
]


def main() -> int:
    settings = load_settings()

    print("Lucero Phase 1 Gemini/Vertex smoke test")
    print("---------------------------------------")
    print(f"Project: {settings.google_cloud_project}")
    print(f"Location: {settings.google_cloud_location}")
    print(f"Model: {settings.gemini_reasoning_model}")
    print(f"Vertex AI mode: {settings.google_genai_use_vertexai}")

    client = genai.Client(
        vertexai=settings.google_genai_use_vertexai,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )

    models_to_try = _candidate_models(settings.gemini_reasoning_model)
    failures: list[tuple[str, Exception]] = []

    for model in models_to_try:
        try:
            response = client.models.generate_content(
                model=model,
                contents="Reply with exactly: Lucero Gemini smoke test passed",
            )
        except Exception as exc:
            failures.append((model, exc))
            reason = str(exc)
            if "PERMISSION_DENIED" in reason or "403" in reason:
                print("FAIL Gemini/Vertex permission denied.")
                print("Check that Application Default Credentials are set and Vertex AI API is enabled.")
                print(f"Reason: {exc}")
                return 1
            continue

        text = (response.text or "").strip()
        if not text:
            failures.append((model, RuntimeError("empty response")))
            continue

        print("PASS Gemini returned a response.")
        print(f"Working model: {model}")
        if model != settings.gemini_reasoning_model:
            print()
            print("Configured model was unavailable. Update `.env` to:")
            print(f"GEMINI_REASONING_MODEL={model}")
        print(f"Response: {text}")
        return 0

    print("FAIL No Gemini model candidate returned a usable response.")
    for model, exc in failures:
        print(f"- {model}: {exc}")
    return 1


def _candidate_models(configured_model: str) -> list[str]:
    candidates = [configured_model]
    for model in DEFAULT_FALLBACK_MODELS:
        if model not in candidates:
            candidates.append(model)
    return candidates


if __name__ == "__main__":
    raise SystemExit(main())
