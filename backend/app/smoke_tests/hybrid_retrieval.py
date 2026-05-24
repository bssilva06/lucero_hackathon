from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.config import load_settings
from app.embeddings import embed_texts


EXPECTED_TOP_FIXTURE = "fixture-i601a-hardship"
QUERY = "extreme hardship family ties provisional unlawful presence waiver"


def main() -> int:
    settings = load_settings()

    print("Lucero hybrid retrieval smoke test")
    print("----------------------------------")
    print(f"Database: {settings.mongo_db}")
    print(f"Collection: {settings.mongo_chunks_collection}")
    print(f"Vector index: {settings.vector_index}")
    print(f"Text index: {settings.fts_index}")

    if not settings.voyage_api_key:
        print("FAIL Missing VOYAGE_API_KEY.")
        return 1

    try:
        query_vector = embed_texts(
            [QUERY],
            api_key=settings.voyage_api_key,
            model=settings.voyage_embedding_model,
            input_type="query",
        )[0]
    except Exception as exc:
        print("FAIL Could not embed retrieval query.")
        print(f"Reason: {exc}")
        return 1

    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
        collection = client[settings.mongo_db][settings.mongo_chunks_collection]

        vector_results = list(collection.aggregate(_vector_pipeline(settings, query_vector)))
        text_results = list(collection.aggregate(_text_pipeline(settings)))
        hybrid_results = (
            list(collection.aggregate(_rank_fusion_pipeline(settings, query_vector)))
            if settings.use_rank_fusion
            else []
        )
    except PyMongoError as exc:
        print("FAIL Retrieval smoke test failed.")
        print(f"Reason: {exc}")
        return 1
    finally:
        try:
            client.close()
        except UnboundLocalError:
            pass

    checks = [
        _check_results("Vector", vector_results),
        _check_results("Text", text_results),
    ]
    if settings.use_rank_fusion:
        checks.append(_check_results("Hybrid $rankFusion", hybrid_results))

    return 0 if all(checks) else 1


def _vector_pipeline(settings: Any, query_vector: list[float]) -> list[dict[str, Any]]:
    return [
        {
            "$vectorSearch": {
                "index": settings.vector_index,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": 20,
                "limit": 3,
                "filter": {"status": "active", "ingestion_run_id": "fixture-smoke-test"},
            }
        },
        {"$project": _projection(score_meta="vectorSearchScore")},
    ]


def _text_pipeline(settings: Any) -> list[dict[str, Any]]:
    return [
        {
            "$search": {
                "index": settings.fts_index,
                "compound": {
                    "must": [{"text": {"query": QUERY, "path": "text"}}],
                    "filter": [
                        {"text": {"query": "active", "path": "status"}},
                    ],
                },
            }
        },
        {"$match": {"ingestion_run_id": "fixture-smoke-test"}},
        {"$limit": 3},
        {"$project": _projection(score_meta="searchScore")},
    ]


def _rank_fusion_pipeline(settings: Any, query_vector: list[float]) -> list[dict[str, Any]]:
    return [
        {
            "$rankFusion": {
                "input": {
                    "pipelines": {
                        "vector": _vector_pipeline(settings, query_vector)[:-1],
                        "text": _text_pipeline(settings)[:-1],
                    }
                },
                "combination": {"weights": {"vector": 0.65, "text": 0.35}},
                "scoreDetails": True,
            }
        },
        {"$limit": 3},
        {"$project": _projection(score_meta="scoreDetails")},
    ]


def _projection(*, score_meta: str) -> dict[str, Any]:
    return {
        "_id": 1,
        "section_citation": 1,
        "text": 1,
        "score": {"$meta": score_meta},
    }


def _check_results(label: str, results: list[dict[str, Any]]) -> bool:
    ids = [str(result["_id"]) for result in results]
    print(f"{label} result ids: {', '.join(ids) if ids else '(none)'}")

    if not ids:
        print(f"FAIL {label} retrieval returned no results.")
        return False

    if ids[0] != EXPECTED_TOP_FIXTURE:
        print(f"FAIL {label} retrieval top result was {ids[0]}, expected {EXPECTED_TOP_FIXTURE}.")
        return False

    print(f"PASS {label} retrieval returned expected top fixture.")
    return True


if __name__ == "__main__":
    raise SystemExit(main())
