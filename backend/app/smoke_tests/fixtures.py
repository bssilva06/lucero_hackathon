from __future__ import annotations

from datetime import UTC, datetime


FIXTURE_SOURCE_CHUNKS = [
    {
        "_id": "fixture-i601a-hardship",
        "text": (
            "Extreme hardship factors for a provisional unlawful presence waiver may include "
            "family ties, medical conditions, financial impact, country conditions, and other "
            "hardship considerations affecting a qualifying relative."
        ),
        "source_url": "https://example.test/uscis-policy-manual/volume-9-part-b",
        "doc_id": "fixture-pm-vol9-ptb",
        "doc_type": "policy_manual",
        "agency": "USCIS",
        "jurisdiction": "federal",
        "section_path": ["Volume 9", "Part B", "Chapter 5"],
        "section_citation": "9 USCIS-PM B.5",
        "parent_doc_id": "fixture-pm-vol9-ptb",
        "chunk_index": 1,
        "chunk_strategy": "fixture-v1",
        "token_count": 34,
        "version_label": "fixture-2026-05-20",
        "effective_from": "2026-05-20",
        "effective_to": None,
        "status": "active",
        "superseded_by": None,
        "retrieval_date": datetime.now(UTC).isoformat(),
        "content_hash": "fixture:i601a-hardship",
        "ingestion_run_id": "fixture-smoke-test",
    },
    {
        "_id": "fixture-i130-fee",
        "text": (
            "Form I-130 fee fixture: paper filing and online filing may have different fees. "
            "Use the current G-1055 fee schedule before relying on any fee amount."
        ),
        "source_url": "https://example.test/uscis/g-1055",
        "doc_id": "fixture-g-1055",
        "doc_type": "fee_schedule",
        "agency": "USCIS",
        "jurisdiction": "federal",
        "section_path": ["G-1055", "I-130"],
        "section_citation": "USCIS G-1055",
        "parent_doc_id": "fixture-g-1055",
        "chunk_index": 2,
        "chunk_strategy": "fixture-v1",
        "token_count": 28,
        "version_label": "fixture-2026-05-20",
        "effective_from": "2026-05-20",
        "effective_to": None,
        "status": "active",
        "superseded_by": None,
        "retrieval_date": datetime.now(UTC).isoformat(),
        "content_hash": "fixture:i130-fee",
        "ingestion_run_id": "fixture-smoke-test",
    },
    {
        "_id": "fixture-cdj-processing",
        "text": (
            "Ciudad Juarez consular processing fixture: applicants should follow National Visa "
            "Center document collection instructions and post-specific interview preparation."
        ),
        "source_url": "https://example.test/cdj-consular-processing",
        "doc_id": "fixture-cdj-post-info",
        "doc_type": "fam",
        "agency": "DOS",
        "jurisdiction": "federal",
        "section_path": ["Ciudad Juarez", "Post Information"],
        "section_citation": "CDJ Post Info",
        "parent_doc_id": "fixture-cdj-post-info",
        "chunk_index": 3,
        "chunk_strategy": "fixture-v1",
        "token_count": 24,
        "version_label": "fixture-2026-05-20",
        "effective_from": "2026-05-20",
        "effective_to": None,
        "status": "active",
        "superseded_by": None,
        "retrieval_date": datetime.now(UTC).isoformat(),
        "content_hash": "fixture:cdj-processing",
        "ingestion_run_id": "fixture-smoke-test",
    },
]
