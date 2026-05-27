from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from pymongo import MongoClient, ReplaceOne
from pymongo.errors import PyMongoError

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_settings  # noqa: E402


JUNE_2026_DOS_URL = (
    "https://travel.state.gov/content/travel/en/legal/visa-law0/"
    "visa-bulletin/2026/visa-bulletin-for-june-2026.html"
)
USCIS_CHART_URL = "https://www.uscis.gov/visabulletininfo"


def main() -> int:
    settings = load_settings()
    retrieved_at = datetime.now(UTC).isoformat()
    documents = [june_2026_f2a_mexico(retrieved_at)]

    print("Lucero Visa Bulletin seed")
    print("-------------------------")
    for document in documents:
        print(
            f"{document['month']} {document['year']} {document['category']} "
            f"{document['country']}: final_action={document['final_action_date']}, "
            f"dates_for_filing={document['dates_for_filing']}, "
            f"uscis_chart={document['uscis_adjustment_chart']}"
        )

    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
        collection = client[settings.mongo_db][settings.mongo_visa_bulletins_collection]
        result = collection.bulk_write(
            [
                ReplaceOne({"_id": document["_id"]}, document, upsert=True)
                for document in documents
            ]
        )
        collection.create_index([("year", 1), ("month", 1), ("category", 1), ("country", 1)])
        collection.create_index("status")
    except PyMongoError as exc:
        print("FAIL Could not upsert Visa Bulletin records.")
        print(f"Reason: {exc}")
        return 1
    finally:
        try:
            client.close()
        except UnboundLocalError:
            pass

    print("PASS Visa Bulletin records upserted.")
    print(f"Matched: {result.matched_count}")
    print(f"Modified: {result.modified_count}")
    print(f"Upserted: {len(result.upserted_ids)}")
    return 0


def june_2026_f2a_mexico(retrieved_at: str) -> dict[str, Any]:
    basis = {
        "month": "June",
        "year": 2026,
        "category": "F2A",
        "country": "Mexico",
        "final_action_date": "01JAN24",
        "dates_for_filing": "C",
        "uscis_adjustment_chart": "Final Action Dates",
        "source_urls": {
            "dos_visa_bulletin": JUNE_2026_DOS_URL,
            "uscis_chart_selection": USCIS_CHART_URL,
        },
    }
    return {
        "_id": "visa-bulletin-2026-06-f2a-mexico",
        **basis,
        "is_current_under_uscis_chart": False,
        "final_action_is_current": False,
        "dates_for_filing_is_current": True,
        "section_citation": "DOS Visa Bulletin June 2026; USCIS Visa Bulletin Info",
        "summary": (
            "For June 2026, F2A Mexico is not current under the Final Action Dates chart "
            "because the final action date is 01JAN24. The Dates for Filing chart lists F2A "
            "Mexico as current, but USCIS adjustment-of-status filing uses the Final Action "
            "Dates chart for this curated record."
        ),
        "status": "active",
        "retrieval_date": retrieved_at,
        "content_hash": hashlib.sha256(repr(sorted(basis.items())).encode("utf-8")).hexdigest(),
    }


if __name__ == "__main__":
    raise SystemExit(main())
