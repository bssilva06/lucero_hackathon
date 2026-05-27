from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pymongo import MongoClient

from app.config import Settings, load_settings
from app.embeddings import embed_texts


DEFAULT_LIMIT = 5
DEFAULT_NUM_CANDIDATES = 50
VECTOR_WEIGHT = 0.65
TEXT_WEIGHT = 0.35


@dataclass(frozen=True)
class RetrievalFilters:
    status: str = "active"
    doc_type: str | None = None
    agency: str | None = None
    jurisdiction: str | None = None
    ingestion_run_id: str | None = None
    exclude_ingestion_run_ids: tuple[str, ...] = ()


def search_source_chunks(
    query: str,
    *,
    filters: RetrievalFilters | None = None,
    limit: int = DEFAULT_LIMIT,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Search source chunks with Google query embeddings and Atlas hybrid retrieval."""
    if not query.strip():
        raise ValueError("query must not be empty")

    settings = settings or load_settings()
    filters = filters or RetrievalFilters()
    query_vector = embed_texts(
        [query],
        project_id=settings.google_cloud_project,
        location=settings.google_cloud_location,
        model=settings.google_embedding_model,
        input_type="query",
        output_dimensionality=settings.vector_dimensions,
    )[0]

    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
    try:
        collection = client[settings.mongo_db][settings.mongo_chunks_collection]
        pipeline = (
            rank_fusion_pipeline(settings, query, query_vector, filters=filters, limit=limit)
            if settings.use_rank_fusion
            else vector_search_pipeline(settings, query_vector, filters=filters, limit=limit)
        )
        return [_normalize_result(result) for result in collection.aggregate(pipeline)]
    finally:
        client.close()


def search_uscis_policy_manual(
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Search active USCIS Policy Manual source chunks and return citation-ready results."""
    return search_uscis_policy_manual_chunks(query, limit=limit)


def lookup_uscis_form(form_number: str) -> dict[str, Any]:
    """Look up curated USCIS form facts such as fees, filing location, and edition date."""
    normalized_form_number = normalize_form_number(form_number)
    if not normalized_form_number:
        return {
            "query": form_number,
            "found": False,
            "error": "form_number must identify a USCIS form, such as I-601A or I-130",
        }

    settings = load_settings()
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
    try:
        collection = client[settings.mongo_db][settings.mongo_forms_collection]
        document = collection.find_one(
            {"form_number": normalized_form_number, "status": "active"},
            {
                "_id": 1,
                "form_number": 1,
                "title": 1,
                "edition_date": 1,
                "filing_methods": 1,
                "filing_location_summary": 1,
                "fee_entries": 1,
                "source_urls": 1,
                "section_citation": 1,
                "retrieval_date": 1,
                "content_hash": 1,
            },
        )
    finally:
        client.close()

    if not document:
        return {
            "query": form_number,
            "form_number": normalized_form_number,
            "found": False,
            "message": f"No active curated USCIS form record found for {normalized_form_number}.",
        }

    return {
        "query": form_number,
        "found": True,
        "form": {
            "form_id": str(document.get("_id", "")),
            "form_number": document.get("form_number"),
            "title": document.get("title"),
            "edition_date": document.get("edition_date"),
            "filing_methods": document.get("filing_methods", []),
            "filing_location_summary": document.get("filing_location_summary"),
            "fee_entries": document.get("fee_entries", []),
            "source_urls": document.get("source_urls", {}),
            "section_citation": document.get("section_citation"),
            "retrieval_date": document.get("retrieval_date"),
            "content_hash": document.get("content_hash"),
        },
    }


def normalize_form_number(value: str) -> str | None:
    compact = "".join(ch for ch in value.upper() if ch.isalnum())
    if compact.startswith("FORM"):
        compact = compact[4:]
    if not compact.startswith("I"):
        return None
    suffix = compact[1:]
    if not suffix:
        return None
    return f"I-{suffix}"


def check_visa_bulletin(
    category: str,
    country: str = "Mexico",
    month: str = "June",
    year: int = 2026,
) -> dict[str, Any]:
    """Look up curated Visa Bulletin data and USCIS chart selection for a category/country/month."""
    normalized_category = normalize_visa_category(category)
    normalized_country = normalize_country(country)
    normalized_month = month.strip().title()

    settings = load_settings()
    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
    try:
        collection = client[settings.mongo_db][settings.mongo_visa_bulletins_collection]
        document = collection.find_one(
            {
                "month": normalized_month,
                "year": int(year),
                "category": normalized_category,
                "country": normalized_country,
                "status": "active",
            },
            {"_id": 0},
        )
    finally:
        client.close()

    if not document:
        return {
            "found": False,
            "query": {
                "category": category,
                "country": country,
                "month": month,
                "year": year,
            },
            "message": (
                "No active curated Visa Bulletin record found for "
                f"{normalized_category} {normalized_country} {normalized_month} {year}."
            ),
        }

    return {
        "found": True,
        "query": {
            "category": category,
            "country": country,
            "month": month,
            "year": year,
        },
        "result": document,
    }


def normalize_visa_category(value: str) -> str:
    compact = value.upper().replace("-", "").replace(" ", "")
    if compact in {"F2A", "F2ASPOUSE", "F2ACHILD"}:
        return "F2A"
    return compact


def normalize_country(value: str) -> str:
    normalized = value.strip().title()
    if normalized in {"Mx", "México"}:
        return "Mexico"
    return normalized


def search_uscis_policy_manual_chunks(
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
    ingestion_run_id: str | None = None,
) -> dict[str, Any]:
    """Search active USCIS Policy Manual chunks with optional test-only run filtering."""
    settings = load_settings()
    filters = RetrievalFilters(
        status="active",
        doc_type="policy_manual",
        agency="USCIS",
        ingestion_run_id=ingestion_run_id,
        exclude_ingestion_run_ids=() if ingestion_run_id else ("fixture-smoke-test",),
    )
    results = search_source_chunks(query, filters=filters, limit=limit, settings=settings)
    return {
        "query": query,
        "retrieval_mode": "hybrid_rank_fusion" if settings.use_rank_fusion else "vector_search",
        "results": results,
    }


def vector_search_pipeline(
    settings: Settings,
    query_vector: list[float],
    *,
    filters: RetrievalFilters,
    limit: int,
) -> list[dict[str, Any]]:
    return [
        {
            "$vectorSearch": {
                "index": settings.vector_index,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": max(DEFAULT_NUM_CANDIDATES, limit * 10),
                "limit": limit,
                "filter": _vector_filter(filters),
            }
        },
        {"$match": _match_filter(filters)},
        {"$project": _projection(score_meta="vectorSearchScore")},
    ]


def text_search_pipeline(
    settings: Settings,
    query: str,
    *,
    filters: RetrievalFilters,
    limit: int,
) -> list[dict[str, Any]]:
    return [
        {
            "$search": {
                "index": settings.fts_index,
                "compound": {
                    "must": [
                        {
                            "text": {
                                "query": query,
                                "path": ["text", "section_citation"],
                            }
                        }
                    ],
                    "filter": [{"text": {"query": filters.status, "path": "status"}}],
                },
            }
        },
        {"$match": _match_filter(filters)},
        {"$limit": limit},
        {"$project": _projection(score_meta="searchScore")},
    ]


def rank_fusion_pipeline(
    settings: Settings,
    query: str,
    query_vector: list[float],
    *,
    filters: RetrievalFilters,
    limit: int,
) -> list[dict[str, Any]]:
    return [
        {
            "$rankFusion": {
                "input": {
                    "pipelines": {
                        "vector": vector_search_pipeline(
                            settings,
                            query_vector,
                            filters=filters,
                            limit=limit,
                        )[:-1],
                        "text": text_search_pipeline(
                            settings,
                            query,
                            filters=filters,
                            limit=limit,
                        )[:-1],
                    }
                },
                "combination": {"weights": {"vector": VECTOR_WEIGHT, "text": TEXT_WEIGHT}},
                "scoreDetails": True,
            }
        },
        {"$limit": limit},
        {"$project": _projection(score_meta="scoreDetails")},
    ]


def _vector_filter(filters: RetrievalFilters) -> dict[str, Any]:
    vector_filter: dict[str, Any] = {"status": filters.status}
    for field in ["doc_type", "agency", "jurisdiction", "ingestion_run_id"]:
        value = getattr(filters, field)
        if value:
            vector_filter[field] = value
    return vector_filter


def _match_filter(filters: RetrievalFilters) -> dict[str, Any]:
    match_filter: dict[str, Any] = {"status": filters.status}
    for field in ["doc_type", "agency", "jurisdiction", "ingestion_run_id"]:
        value = getattr(filters, field)
        if value:
            match_filter[field] = value
    if filters.exclude_ingestion_run_ids:
        match_filter["ingestion_run_id"] = {"$nin": list(filters.exclude_ingestion_run_ids)}
    return match_filter


def _projection(*, score_meta: str) -> dict[str, Any]:
    return {
        "_id": 1,
        "text": 1,
        "source_url": 1,
        "doc_id": 1,
        "doc_type": 1,
        "agency": 1,
        "jurisdiction": 1,
        "section_path": 1,
        "section_citation": 1,
        "version_label": 1,
        "effective_from": 1,
        "effective_to": 1,
        "retrieval_date": 1,
        "content_hash": 1,
        "score": {"$meta": score_meta},
    }


def _normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": str(result.get("_id", "")),
        "text": result.get("text", ""),
        "source_url": result.get("source_url"),
        "doc_id": result.get("doc_id"),
        "doc_type": result.get("doc_type"),
        "agency": result.get("agency"),
        "jurisdiction": result.get("jurisdiction"),
        "section_path": result.get("section_path", []),
        "section_citation": result.get("section_citation"),
        "version_label": result.get("version_label"),
        "effective_from": result.get("effective_from"),
        "effective_to": result.get("effective_to"),
        "retrieval_date": result.get("retrieval_date"),
        "content_hash": result.get("content_hash"),
        "score": result.get("score"),
    }
