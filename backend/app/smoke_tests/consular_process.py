from __future__ import annotations

from app.retrieval import lookup_consular_process


def main() -> int:
    print("Lucero consular process lookup smoke test")
    print("-----------------------------------------")

    payload = lookup_consular_process("I-601A timeline", post="CDJ")
    if not payload.get("found"):
        print("FAIL Consular process lookup did not find CDJ records.")
        print(f"Payload: {payload}")
        return 1

    records = payload.get("records", [])
    if not isinstance(records, list) or not records:
        print("FAIL Consular process lookup returned no records.")
        print(f"Payload: {payload}")
        return 1

    citations = [
        str(record.get("section_citation", ""))
        for record in records
        if isinstance(record, dict)
    ]
    if not any(citation.startswith("CDJ Post Instructions") for citation in citations):
        print("FAIL Consular process lookup did not include CDJ Post Instructions.")
        print(f"Citations: {citations}")
        return 1
    if not any(citation.startswith("NVC") for citation in citations):
        print("FAIL Consular process lookup did not include an NVC citation.")
        print(f"Citations: {citations}")
        return 1

    urls = []
    for record in records:
        if not isinstance(record, dict):
            continue
        source_urls = record.get("source_urls", {})
        if isinstance(source_urls, dict):
            urls.extend(str(url) for url in source_urls.values())
    if not urls or not all(url.startswith("https://travel.state.gov/") for url in urls):
        print("FAIL Consular process lookup returned non-DOS source URLs.")
        print(f"URLs: {urls}")
        return 1

    print("PASS Consular process lookup returned cited CDJ/NVC records.")
    print(f"Citations: {citations}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
