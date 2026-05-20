from __future__ import annotations

from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from app.config import load_settings


def main() -> int:
    settings = load_settings()

    print("Lucero Phase 1 MongoDB Atlas smoke test")
    print("---------------------------------------")

    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
        server_info = client.server_info()
        db = client[settings.mongo_db]
        collections = sorted(db.list_collection_names())
    except ServerSelectionTimeoutError as exc:
        print("FAIL Could not connect to MongoDB Atlas before timeout.")
        print(f"Reason: {exc}")
        return 1
    except PyMongoError as exc:
        print("FAIL MongoDB Atlas command failed.")
        print(f"Reason: {exc}")
        return 1

    print("PASS Connected to MongoDB Atlas")
    print(f"Server version: {server_info.get('version', 'unknown')}")
    print(f"Database: {settings.mongo_db}")
    print(f"Collections found: {', '.join(collections) if collections else '(none yet)'}")

    print()
    print("Configured collections")
    print(f"- chunks: {settings.mongo_chunks_collection}")
    print(f"- forms: {settings.mongo_forms_collection}")
    print(f"- visa bulletins: {settings.mongo_visa_bulletins_collection}")
    print(f"- query logs: {settings.mongo_query_logs_collection}")

    if settings.use_rank_fusion:
        print()
        print("NOTE $rankFusion support still needs an Atlas Search/vector index smoke test.")
        print("     This connection test only confirms the cluster is reachable.")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
