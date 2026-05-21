from __future__ import annotations

from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from app.config import load_settings


SMOKE_COLLECTION = "_lucero_rankfusion_smoke"
SMOKE_MARKER = "rankfusion"


def main() -> int:
    settings = load_settings()

    print("Lucero MongoDB $rankFusion smoke test")
    print("------------------------------------")
    print(f"Database: {settings.mongo_db}")
    print(f"Collection: {SMOKE_COLLECTION}")

    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
        collection = client[settings.mongo_db][SMOKE_COLLECTION]
        collection.delete_many({"_smoke": SMOKE_MARKER})
        collection.insert_many(
            [
                {
                    "_id": "rankfusion-a",
                    "_smoke": SMOKE_MARKER,
                    "text": "i601a hardship waiver",
                    "text_rank": 1,
                    "recency_rank": 3,
                },
                {
                    "_id": "rankfusion-b",
                    "_smoke": SMOKE_MARKER,
                    "text": "cdj consular processing",
                    "text_rank": 2,
                    "recency_rank": 1,
                },
                {
                    "_id": "rankfusion-c",
                    "_smoke": SMOKE_MARKER,
                    "text": "visa bulletin",
                    "text_rank": 3,
                    "recency_rank": 2,
                },
            ]
        )

        results = list(collection.aggregate(_rank_fusion_pipeline()))
    except ServerSelectionTimeoutError as exc:
        print("FAIL Could not connect to MongoDB Atlas before timeout.")
        print(f"Reason: {exc}")
        return 1
    except PyMongoError as exc:
        print("FAIL $rankFusion stage was rejected.")
        print(f"Reason: {exc}")
        return 1
    finally:
        try:
            collection.delete_many({"_smoke": SMOKE_MARKER})
            client.close()
        except UnboundLocalError:
            pass

    if not results:
        print("FAIL $rankFusion executed but returned no documents.")
        return 1

    print("PASS $rankFusion stage executed.")
    print("Ranked result ids: " + ", ".join(str(doc["_id"]) for doc in results))
    return 0


def _rank_fusion_pipeline() -> list[dict[str, object]]:
    return [
        {
            "$rankFusion": {
                "input": {
                    "pipelines": {
                        "text_rank": [
                            {"$match": {"_smoke": SMOKE_MARKER}},
                            {"$sort": {"text_rank": 1}},
                            {"$limit": 3},
                        ],
                        "recency_rank": [
                            {"$match": {"_smoke": SMOKE_MARKER}},
                            {"$sort": {"recency_rank": 1}},
                            {"$limit": 3},
                        ],
                    }
                },
                "combination": {"weights": {"text_rank": 0.6, "recency_rank": 0.4}},
                "scoreDetails": True,
            }
        },
        {"$limit": 3},
        {"$project": {"_id": 1, "text": 1, "scoreDetails": {"$meta": "scoreDetails"}}},
    ]


if __name__ == "__main__":
    raise SystemExit(main())
