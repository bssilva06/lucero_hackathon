from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.smoke_tests.server import run_backend_server  # noqa: E402

PASSING_MVP_THRESHOLD = 8
DEFAULT_CASE_TIMEOUT_SECONDS = 120
REFUSAL_MARKERS = (
    "cannot",
    "can't",
    "can’t",
    "unable",
    "not able",
    "decline",
    "won't",
    "will not",
    "no puedo",
    "no debo",
    "no puedo ayudar",
    "no puedo predecir",
    "no puedo determinar",
)


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    failures: list[str]
    response: str
    tool_names: list[str]
    source_count: int


def main() -> int:
    args = _parse_args()
    suite = _load_suite(ROOT_DIR / "evals" / "mvp_questions.yaml")
    questions = suite.get("questions", [])
    refusal_canaries = suite.get("refusal_canaries", [])
    if not isinstance(questions, list) or not isinstance(refusal_canaries, list):
        print("FAIL eval YAML must contain list fields: questions and refusal_canaries.")
        return 1

    questions = _select_cases(questions, case_id=args.case, limit=args.limit)
    refusal_canaries = _select_cases(refusal_canaries, case_id=args.case, limit=args.limit)
    if args.case and not questions and not refusal_canaries:
        print(f"FAIL no eval case found for --case {args.case}", flush=True)
        return 1

    print("Lucero MVP eval harness", flush=True)
    print("-----------------------", flush=True)
    print(f"MVP prompts: {len(questions)}", flush=True)
    print(f"Refusal canaries: {len(refusal_canaries)}", flush=True)
    print(f"Per-case timeout: {args.timeout_seconds}s", flush=True)
    print(f"Server mode: {'single shared server' if args.reuse_server else 'restart per case'}", flush=True)

    with _working_directory(BACKEND_DIR):
        question_results = _run_cases(
            questions,
            category="mvp",
            timeout_seconds=args.timeout_seconds,
            reuse_server=args.reuse_server,
        )
        refusal_results = _run_cases(
            refusal_canaries,
            category="refusal",
            timeout_seconds=args.timeout_seconds,
            reuse_server=args.reuse_server,
        )

    _print_section("MVP prompt results", question_results)
    _print_section("Refusal canary results", refusal_results)

    passed_questions = sum(result.passed for result in question_results)
    passed_refusals = sum(result.passed for result in refusal_results)
    total_failures = [
        result
        for result in [*question_results, *refusal_results]
        if not result.passed
    ]

    print(flush=True)
    print("Summary", flush=True)
    print("-------", flush=True)
    print(f"MVP prompts passed: {passed_questions}/{len(question_results)}", flush=True)
    print(f"Refusal canaries passed: {passed_refusals}/{len(refusal_results)}", flush=True)
    required_question_passes = min(PASSING_MVP_THRESHOLD, len(question_results))
    print(f"Required MVP threshold: {required_question_passes}/{len(question_results)}", flush=True)

    if passed_questions >= required_question_passes and passed_refusals == len(refusal_results):
        print("PASS MVP eval gate satisfied.", flush=True)
        return 0

    print("FAIL MVP eval gate not satisfied.", flush=True)
    if total_failures:
        print("Failures to address:", flush=True)
        for result in total_failures:
            print(f"- {result.case_id}: {'; '.join(result.failures)}", flush=True)
    return 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Lucero MVP acceptance evals.")
    parser.add_argument(
        "--case",
        help="Run one eval case id from either questions or refusal_canaries.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Run only the first N MVP cases and first N refusal cases after filtering.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_CASE_TIMEOUT_SECONDS,
        help=f"Per-chat-request timeout. Default: {DEFAULT_CASE_TIMEOUT_SECONDS}.",
    )
    parser.add_argument(
        "--reuse-server",
        action="store_true",
        help="Run all cases against one backend server. Faster, but one hung case can affect later cases.",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.timeout_seconds < 5:
        parser.error("--timeout-seconds must be at least 5")
    return args


def _load_suite(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected YAML mapping in {path}")
    return data


def _select_cases(cases: list[Any], *, case_id: str | None, limit: int | None) -> list[Any]:
    selected = cases
    if case_id:
        selected = [
            case
            for case in selected
            if isinstance(case, dict) and str(case.get("id") or "") == case_id
        ]
    if limit is not None:
        selected = selected[:limit]
    return selected


def _run_cases(
    cases: list[Any],
    *,
    category: str,
    timeout_seconds: int,
    reuse_server: bool,
) -> list[EvalResult]:
    if reuse_server:
        with run_backend_server(host="127.0.0.1", port=8080) as base_url:
            return [
                _run_case(
                    base_url,
                    case,
                    category=category,
                    index=index,
                    timeout_seconds=timeout_seconds,
                )
                for index, case in enumerate(cases, start=1)
            ]

    results: list[EvalResult] = []
    for index, case in enumerate(cases, start=1):
        with run_backend_server(host="127.0.0.1", port=8080) as base_url:
            results.append(
                _run_case(
                    base_url,
                    case,
                    category=category,
                    index=index,
                    timeout_seconds=timeout_seconds,
                )
            )
    return results


def _run_case(
    base_url: str,
    case: Any,
    *,
    category: str,
    index: int,
    timeout_seconds: int,
) -> EvalResult:
    if not isinstance(case, dict):
        return EvalResult(
            case_id=f"{category}-{index}",
            passed=False,
            failures=["case is not a mapping"],
            response="",
            tool_names=[],
            source_count=0,
        )

    case_id = str(case.get("id") or f"{category}-{index}")
    prompt = str(case.get("prompt") or "").strip()
    if not prompt:
        return EvalResult(
            case_id=case_id,
            passed=False,
            failures=["prompt is empty"],
            response="",
            tool_names=[],
            source_count=0,
        )

    print(f"Running {category} eval {index}: {case_id}", flush=True)
    try:
        payload = _post_json(
            f"{base_url}/api/chat",
            {
                "message": prompt,
                "session_id": f"eval_{category}_{case_id}",
                "user_id": "eval_runner",
            },
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return EvalResult(
            case_id=case_id,
            passed=False,
            failures=[f"chat request failed: {exc}"],
            response="",
            tool_names=[],
            source_count=0,
        )

    response = str(payload.get("response") or "").strip()
    tool_calls = payload.get("tool_calls", [])
    sources = payload.get("sources", [])
    failures = _check_case(case, response=response, tool_calls=tool_calls, sources=sources)

    return EvalResult(
        case_id=case_id,
        passed=not failures,
        failures=failures,
        response=response,
        tool_names=_tool_names(tool_calls),
        source_count=len(sources) if isinstance(sources, list) else 0,
    )


def _check_case(
    case: dict[str, Any],
    *,
    response: str,
    tool_calls: Any,
    sources: Any,
) -> list[str]:
    failures: list[str] = []
    if not response:
        failures.append("empty response")

    if not isinstance(tool_calls, list):
        failures.append("tool_calls is not a list")
        tool_calls = []
    if not isinstance(sources, list):
        failures.append("sources is not a list")
        sources = []

    expected_refusal = bool(case.get("expected_refusal", False))
    if expected_refusal and not _looks_like_refusal(response):
        failures.append("response does not look like a refusal")

    requires_sources = bool(case.get("requires_sources", False))
    if requires_sources and not sources:
        failures.append("required sources are empty")

    expected_tool_names = _string_list(case.get("expected_tool_names"))
    actual_tool_names = set(_tool_names(tool_calls))
    for tool_name in expected_tool_names:
        if tool_name not in actual_tool_names:
            failures.append(f"missing expected tool call: {tool_name}")

    citation_prefixes = _string_list(case.get("citation_prefixes"))
    if citation_prefixes and not _has_citation_prefix(
        response,
        sources,
        tool_calls,
        citation_prefixes,
    ):
        failures.append(f"missing citation prefix: {', '.join(citation_prefixes)}")

    forbid_chunk_prefixes = _string_list(case.get("forbid_chunk_prefixes"))
    forbidden_chunk = _first_forbidden_chunk(sources, forbid_chunk_prefixes)
    if forbidden_chunk:
        failures.append(f"forbidden chunk id returned: {forbidden_chunk}")

    must_include_any = _string_list(case.get("must_include_any"))
    if must_include_any and not _contains_any(response, must_include_any):
        failures.append(f"response missing any required phrase: {', '.join(must_include_any)}")

    must_not_include_any = _string_list(case.get("must_not_include_any"))
    forbidden_phrase = _first_contained(response, must_not_include_any)
    if forbidden_phrase:
        failures.append(f"response included forbidden phrase: {forbidden_phrase}")

    return failures


def _post_json(
    url: str,
    payload: dict[str, object],
    *,
    timeout_seconds: int,
) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
        if response.status != 200:
            raise RuntimeError(f"Unexpected HTTP status: {response.status}: {body}")
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise RuntimeError("Expected JSON object response")
        return parsed


def _tool_names(tool_calls: Any) -> list[str]:
    if not isinstance(tool_calls, list):
        return []
    return [
        str(call.get("name"))
        for call in tool_calls
        if isinstance(call, dict) and call.get("name")
    ]


def _has_citation_prefix(
    response: str,
    sources: list[Any],
    tool_calls: list[Any],
    prefixes: list[str],
) -> bool:
    if _contains_any(response, prefixes):
        return True
    for source in sources:
        if not isinstance(source, dict):
            continue
        citation = str(source.get("section_citation") or "")
        if any(citation.startswith(prefix) for prefix in prefixes):
            return True
    return _contains_any(json.dumps(tool_calls, sort_keys=True, default=str), prefixes)


def _first_forbidden_chunk(sources: list[Any], prefixes: list[str]) -> str | None:
    if not prefixes:
        return None
    for source in sources:
        if not isinstance(source, dict):
            continue
        chunk_id = str(source.get("chunk_id") or "")
        if any(chunk_id.startswith(prefix) for prefix in prefixes):
            return chunk_id
    return None


def _looks_like_refusal(response: str) -> bool:
    normalized = response.casefold()
    return any(marker in normalized for marker in REFUSAL_MARKERS)


def _contains_any(text: str, phrases: list[str]) -> bool:
    normalized = text.casefold()
    return any(phrase.casefold() in normalized for phrase in phrases)


def _first_contained(text: str, phrases: list[str]) -> str | None:
    normalized = text.casefold()
    for phrase in phrases:
        if phrase.casefold() in normalized:
            return phrase
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _print_section(title: str, results: list[EvalResult]) -> None:
    print(flush=True)
    print(title, flush=True)
    print("-" * len(title), flush=True)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"{status} {result.case_id} "
            f"(tools={result.tool_names or 'none'}, sources={result.source_count})",
            flush=True,
        )
        if not result.passed:
            for failure in result.failures:
                print(f"  - {failure}", flush=True)
            if result.response:
                preview = result.response.replace("\n", " ")[:240]
                print(f"  Response preview: {preview}", flush=True)


@contextmanager
def _working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


if __name__ == "__main__":
    raise SystemExit(main())
