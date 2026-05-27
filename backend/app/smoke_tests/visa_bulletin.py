from __future__ import annotations

import json

from app.retrieval import check_visa_bulletin


def main() -> int:
    print("Lucero Visa Bulletin smoke test")
    print("-------------------------------")
    payload = check_visa_bulletin("F2A", country="Mexico", month="June", year=2026)
    if not payload.get("found"):
        print("FAIL Visa Bulletin record was not found.")
        print(json.dumps(payload, indent=2, sort_keys=True)[:2_000])
        return 1

    result = payload.get("result")
    if not isinstance(result, dict):
        print("FAIL Visa Bulletin payload did not include a result object.")
        return 1

    checks = {
        "category": result.get("category") == "F2A",
        "country": result.get("country") == "Mexico",
        "final_action_date": result.get("final_action_date") == "01JAN24",
        "dates_for_filing": result.get("dates_for_filing") == "C",
        "uscis_adjustment_chart": result.get("uscis_adjustment_chart") == "Final Action Dates",
        "not_current_under_uscis_chart": result.get("is_current_under_uscis_chart") is False,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print("FAIL Visa Bulletin record did not match expected June 2026 F2A Mexico facts.")
        print(f"Failed checks: {', '.join(failed)}")
        print(json.dumps(result, indent=2, sort_keys=True)[:2_000])
        return 1

    print(
        "PASS June 2026 F2A Mexico: "
        f"final_action={result['final_action_date']}, "
        f"dates_for_filing={result['dates_for_filing']}, "
        f"uscis_chart={result['uscis_adjustment_chart']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
