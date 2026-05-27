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

    print("Lucero Google fixture embedding seed")
    print("------------------------------------")
    print(f"Database: {settings.mongo_db}")
    print(f"Collection: {settings.mongo_chunks_collection}")
    print(f"Embedding model: {settings.google_embedding_model}")

    try:
        embeddings = embed_texts(
            [str(chunk["text"]) for chunk in FIXTURE_SOURCE_CHUNKS],
            project_id=settings.google_cloud_project,
            location=settings.google_cloud_location,
            model=settings.google_embedding_model,
            input_type="document",
            output_dimensionality=settings.vector_dimensions,
        )
    except ImportError:
        print("FAIL Missing Google Vertex AI package.")
        print("     Install backend dependencies again: python -m pip install -e .")
        return 1
    except Exception as exc:
        print("FAIL Google embedding request failed.")
        print(f"Reason: {exc}")
        return 1

    if len(embeddings) != len(FIXTURE_SOURCE_CHUNKS):
        print("FAIL Google Vertex AI returned an unexpected number of embeddings.")
        print(f"Expected: {len(FIXTURE_SOURCE_CHUNKS)}")
        print(f"Received: {len(embeddings)}")
        return 1

    embedded_at = datetime.now(UTC).isoformat()
    operations = []
    for chunk, embedding in zip(FIXTURE_SOURCE_CHUNKS, embeddings, strict=True):
        document = {
            **chunk,
            "embedding": embedding,
            "embedding_model": settings.google_embedding_model,
            "embedding_provider": "google_vertex_ai",
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
