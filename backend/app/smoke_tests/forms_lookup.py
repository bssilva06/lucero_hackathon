from __future__ import annotations

import json

from app.retrieval import lookup_uscis_form


def main() -> int:
    print("Lucero USCIS form lookup smoke test")
    print("-----------------------------------")

    for form_number in ["I-601A", "I-130"]:
        payload = lookup_uscis_form(form_number)
        if not payload.get("found"):
            print(f"FAIL {form_number} was not found in the curated forms collection.")
            print(json.dumps(payload, indent=2, sort_keys=True)[:2_000])
            return 1

        form = payload.get("form")
        if not isinstance(form, dict):
            print(f"FAIL {form_number} response did not include a form object.")
            return 1

        if str(form.get("form_id", "")).startswith("fixture-"):
            print(f"FAIL {form_number} returned a fixture form record.")
            return 1

        source_urls = form.get("source_urls", {})
        if not isinstance(source_urls, dict) or not str(source_urls.get("form_page", "")).startswith(
            "https://www.uscis.gov/"
        ):
            print(f"FAIL {form_number} did not include a USCIS form page URL.")
            print(json.dumps(form, indent=2, sort_keys=True)[:2_000])
            return 1

        fee_entries = form.get("fee_entries", [])
        if not isinstance(fee_entries, list) or not fee_entries:
            print(f"FAIL {form_number} did not include fee entries.")
            print(json.dumps(form, indent=2, sort_keys=True)[:2_000])
            return 1

        if not all(
            isinstance(entry, dict) and entry.get("section_citation") == "USCIS G-1055"
            for entry in fee_entries
        ):
            print(f"FAIL {form_number} fee entries did not cite USCIS G-1055.")
            print(json.dumps(fee_entries, indent=2, sort_keys=True)[:2_000])
            return 1

        print(
            f"PASS {form_number}: {form.get('title')} | "
            f"fees={len(fee_entries)} | edition={form.get('edition_date')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
