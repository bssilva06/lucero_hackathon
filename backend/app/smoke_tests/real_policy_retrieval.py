from __future__ import annotations

from app.retrieval import search_uscis_policy_manual


QUERY = "extreme hardship family ties I-601A"


def main() -> int:
    print("Lucero real USCIS Policy Manual retrieval smoke test")
    print("---------------------------------------------------")
    print(f"Query: {QUERY}")

    try:
        payload = search_uscis_policy_manual(QUERY, limit=5)
    except Exception as exc:
        print("FAIL Real Policy Manual retrieval failed.")
        print(f"Reason: {exc}")
        return 1

    results = payload.get("results", [])
    if not isinstance(results, list) or not results:
        print("FAIL Real Policy Manual retrieval returned no results.")
        return 1

    citations = [
        str(result.get("section_citation", ""))
        for result in results
        if isinstance(result, dict)
    ]
    chunk_ids = [str(result.get("chunk_id", "")) for result in results if isinstance(result, dict)]
    urls = [str(result.get("source_url", "")) for result in results if isinstance(result, dict)]

    for index, result in enumerate(results, start=1):
        if not isinstance(result, dict):
            continue
        print(
            f"{index}. {result.get('chunk_id')} | "
            f"{result.get('section_citation')} | {result.get('source_url')}"
        )

    if any(chunk_id.startswith("fixture-") for chunk_id in chunk_ids):
        print("FAIL Real Policy Manual retrieval returned fixture chunks.")
        return 1

    if not any(citation.startswith(("9 USCIS-PM B", "9 USCIS-PM H")) for citation in citations):
        print("FAIL Real Policy Manual retrieval did not return Volume 9 Part B/H citations.")
        return 1

    if not all(url.startswith("https://www.uscis.gov/policy-manual/") for url in urls):
        print("FAIL Real Policy Manual retrieval returned a non-USCIS Policy Manual URL.")
        return 1

    print("PASS Real USCIS Policy Manual retrieval returned cited USCIS chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
