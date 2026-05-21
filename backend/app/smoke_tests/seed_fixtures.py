from __future__ import annotations

from pymongo import MongoClient, ReplaceOne
from pymongo.errors import PyMongoError

from app.config import load_settings
from app.smoke_tests.fixtures import FIXTURE_SOURCE_CHUNKS


def main() -> int:
    settings = load_settings()

    print("Lucero Atlas fixture seed")
    print("-------------------------")
    print(f"Database: {settings.mongo_db}")
    print(f"Collection: {settings.mongo_chunks_collection}")
    print(f"Fixture chunks: {len(FIXTURE_SOURCE_CHUNKS)}")

    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
        collection = client[settings.mongo_db][settings.mongo_chunks_collection]
        result = collection.bulk_write(
            [
                ReplaceOne({"_id": chunk["_id"]}, chunk, upsert=True)
                for chunk in FIXTURE_SOURCE_CHUNKS
            ]
        )
        collection.create_index("ingestion_run_id")
        collection.create_index("status")
        collection.create_index("section_citation")
    except PyMongoError as exc:
        print("FAIL Could not seed Atlas fixtures.")
        print(f"Reason: {exc}")
        return 1
    finally:
        try:
            client.close()
        except UnboundLocalError:
            pass

    print("PASS Fixture chunks upserted.")
    print(f"Matched: {result.matched_count}")
    print(f"Modified: {result.modified_count}")
    print(f"Upserted: {len(result.upserted_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
