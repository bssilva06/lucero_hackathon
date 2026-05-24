from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pymongo.operations import SearchIndexModel


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create Lucero Atlas Search indexes.")
    parser.add_argument("--no-wait", action="store_true", help="Create missing indexes without waiting.")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    settings = load_settings()
    print("Lucero Atlas Search index setup")
    print("-------------------------------")
    print(f"Database: {settings.mongo_db}")
    print(f"Collection: {settings.mongo_chunks_collection}")
    print(f"Vector index: {settings.vector_index}")
    print(f"Text index: {settings.fts_index}")

    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
        collection = client[settings.mongo_db][settings.mongo_chunks_collection]
        existing = _existing_search_indexes(collection)

        created = []
        if settings.vector_index in existing:
            print(f"SKIP Vector Search index already exists: {settings.vector_index}")
        else:
            collection.create_search_index(_vector_index_model(settings))
            created.append(settings.vector_index)
            print(f"CREATE Vector Search index requested: {settings.vector_index}")

        if settings.fts_index in existing:
            print(f"SKIP Atlas Search text index already exists: {settings.fts_index}")
        else:
            collection.create_search_index(_text_index_model(settings.fts_index))
            created.append(settings.fts_index)
            print(f"CREATE Atlas Search text index requested: {settings.fts_index}")

        if not args.no_wait:
            _wait_for_indexes(
                collection,
                {settings.vector_index, settings.fts_index},
                timeout_seconds=args.timeout_seconds,
            )
    except PyMongoError as exc:
        print("FAIL Atlas Search index setup failed.")
        print(f"Reason: {exc}")
        return 1
    finally:
        try:
            client.close()
        except UnboundLocalError:
            pass

    if created:
        print("PASS Requested missing Atlas Search indexes.")
    else:
        print("PASS Atlas Search indexes already existed.")
    return 0


def _existing_search_indexes(collection: Any) -> set[str]:
    return {str(index.get("name")) for index in collection.list_search_indexes()}


def _vector_index_model(settings: Any) -> SearchIndexModel:
    return SearchIndexModel(
        name=settings.vector_index,
        type="vectorSearch",
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": settings.vector_dimensions,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "status"},
                {"type": "filter", "path": "doc_type"},
                {"type": "filter", "path": "agency"},
                {"type": "filter", "path": "jurisdiction"},
                {"type": "filter", "path": "ingestion_run_id"},
            ]
        },
    )


def _text_index_model(index_name: str) -> SearchIndexModel:
    return SearchIndexModel(
        name=index_name,
        definition={
            "mappings": {
                "dynamic": False,
                "fields": {
                    "text": {"type": "string"},
                    "section_citation": {"type": "string"},
                    "doc_type": {"type": "string"},
                    "agency": {"type": "string"},
                    "status": {"type": "string"},
                },
            }
        },
    )


def _wait_for_indexes(
    collection: Any,
    expected_names: set[str],
    *,
    timeout_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, dict[str, Any]] = {}

    while time.monotonic() < deadline:
        latest = {
            str(index.get("name")): index
            for index in collection.list_search_indexes()
            if str(index.get("name")) in expected_names
        }

        for name in sorted(expected_names):
            index = latest.get(name)
            if not index:
                print(f"WAIT {name}: not visible yet")
                continue

            status = index.get("status", "unknown")
            queryable = index.get("queryable", False)
            print(f"WAIT {name}: status={status}, queryable={queryable}")

        if expected_names.issubset(latest) and all(
            _index_ready(index) for index in latest.values()
        ):
            print("PASS Atlas Search indexes are ready.")
            return

        time.sleep(5)

    statuses = ", ".join(
        f"{name}: status={index.get('status')}, queryable={index.get('queryable')}"
        for name, index in sorted(latest.items())
    )
    raise TimeoutError(f"Timed out waiting for Atlas Search indexes: {statuses or '(none)'}")


def _index_ready(index: dict[str, Any]) -> bool:
    status = str(index.get("status", "")).upper()
    queryable = index.get("queryable")
    if queryable is True:
        return True
    return status in {"READY", "STEADY"}


if __name__ == "__main__":
    raise SystemExit(main())
