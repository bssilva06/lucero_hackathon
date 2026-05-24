from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_settings  # noqa: E402
from app.embeddings import embed_texts  # noqa: E402
from app.smoke_tests.fixtures import FIXTURE_SOURCE_CHUNKS  # noqa: E402


def main() -> int:
    settings = load_settings()

    print("Lucero Voyage fixture embedding seed")
    print("------------------------------------")
    print(f"Database: {settings.mongo_db}")
    print(f"Collection: {settings.mongo_chunks_collection}")
    print(f"Embedding model: {settings.voyage_embedding_model}")

    if not settings.voyage_api_key:
        print("FAIL Missing VOYAGE_API_KEY.")
        print("     Create a Voyage model API key and add it to the repository .env file.")
        return 1

    try:
        embeddings = embed_texts(
            [str(chunk["text"]) for chunk in FIXTURE_SOURCE_CHUNKS],
            api_key=settings.voyage_api_key,
            model=settings.voyage_embedding_model,
            input_type="document",
        )
    except ImportError:
        print("FAIL Missing voyageai package.")
        print("     Install backend dependencies again: python -m pip install -e .")
        return 1
    except Exception as exc:
        print("FAIL Voyage embedding request failed.")
        print(f"Reason: {exc}")
        return 1

    if len(embeddings) != len(FIXTURE_SOURCE_CHUNKS):
        print("FAIL Voyage returned an unexpected number of embeddings.")
        print(f"Expected: {len(FIXTURE_SOURCE_CHUNKS)}")
        print(f"Received: {len(embeddings)}")
        return 1

    embedded_at = datetime.now(UTC).isoformat()
    operations = []
    for chunk, embedding in zip(FIXTURE_SOURCE_CHUNKS, embeddings, strict=True):
        document = {
            **chunk,
            "embedding": embedding,
            "embedding_model": settings.voyage_embedding_model,
            "embedding_provider": "voyageai",
            "embedded_at": embedded_at,
        }
        operations.append(UpdateOne({"_id": document["_id"]}, {"$set": document}, upsert=True))

    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
        collection = client[settings.mongo_db][settings.mongo_chunks_collection]
        result = collection.bulk_write(operations)
    except PyMongoError as exc:
        print("FAIL Could not upsert embedded fixture chunks.")
        print(f"Reason: {exc}")
        return 1
    finally:
        try:
            client.close()
        except UnboundLocalError:
            pass

    print("PASS Embedded fixture chunks upserted.")
    print(f"Embedding dimensions: {len(embeddings[0])}")
    print(f"Matched: {result.matched_count}")
    print(f"Modified: {result.modified_count}")
    print(f"Upserted: {len(result.upserted_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
