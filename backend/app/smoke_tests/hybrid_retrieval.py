from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.config import load_settings
from app.embeddings import embed_texts
from app.retrieval import (
    RetrievalFilters,
    rank_fusion_pipeline,
    search_uscis_policy_manual_chunks,
    text_search_pipeline,
    vector_search_pipeline,
)


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

    try:
        query_vector = embed_texts(
            [QUERY],
            project_id=settings.google_cloud_project,
            location=settings.google_cloud_location,
            model=settings.google_embedding_model,
            input_type="query",
            output_dimensionality=settings.vector_dimensions,
        )[0]
    except Exception as exc:
        print("FAIL Could not embed retrieval query.")
        print(f"Reason: {exc}")
        return 1

    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
        collection = client[settings.mongo_db][settings.mongo_chunks_collection]

        filters = RetrievalFilters(status="active", ingestion_run_id="fixture-smoke-test")
        vector_results = list(
            collection.aggregate(
                vector_search_pipeline(settings, query_vector, filters=filters, limit=3)
            )
        )
        text_results = list(
            collection.aggregate(text_search_pipeline(settings, QUERY, filters=filters, limit=3))
        )
        hybrid_results = (
            list(
                collection.aggregate(
                    rank_fusion_pipeline(settings, QUERY, query_vector, filters=filters, limit=3)
                )
            )
            if settings.use_rank_fusion
            else []
        )
        policy_manual_payload = search_uscis_policy_manual_chunks(
            QUERY,
            limit=3,
            ingestion_run_id="fixture-smoke-test",
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
    checks.append(_check_payload("search_uscis_policy_manual", policy_manual_payload))

    return 0 if all(checks) else 1


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


def _check_payload(label: str, payload: dict[str, object]) -> bool:
    results = payload.get("results", [])
    if not isinstance(results, list):
        print(f"FAIL {label} returned non-list results.")
        return False

    ids = [str(result.get("chunk_id")) for result in results if isinstance(result, dict)]
    print(f"{label} result ids: {', '.join(ids) if ids else '(none)'}")
    if not ids or ids[0] != EXPECTED_TOP_FIXTURE:
        print(f"FAIL {label} top result was {ids[0] if ids else '(none)'}.")
        return False

    print(f"PASS {label} returned expected citation-ready top fixture.")
    return True


if __name__ == "__main__":
    raise SystemExit(main())
