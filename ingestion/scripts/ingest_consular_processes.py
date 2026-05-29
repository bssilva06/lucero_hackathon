from __future__ import annotations

import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pymongo import MongoClient, ReplaceOne
from pymongo.errors import PyMongoError


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_settings  # noqa: E402


CDJ_POST_URL = (
    "https://travel.state.gov/content/travel/en/us-visas/Supplements/"
    "Supplements_by_Post/CDJ-Ciudad-Juarez.html"
)
NVC_SUBMIT_DOCS_URL = (
    "https://travel.state.gov/content/visas/en/immigrate/immigrant-process/"
    "documents/Submit_documents.html"
)
NVC_INTERVIEW_PREP_URL = (
    "https://travel.state.gov/content/travel/en/us-visas/immigrate/"
    "the-immigrant-visa-process/step-10-prepare-for-the-interview.html.html"
)
NVC_APPLICANT_INTERVIEW_URL = (
    "https://travel.state.gov/content/travel/en/us-visas/immigrate/"
    "the-immigrant-visa-process/step-10-prepare-for-the-interview/"
    "step-11-applicant-interview.html.html"
)


def main() -> int:
    settings = load_settings()
    retrieved_at = datetime.now(UTC).isoformat()
    documents = consular_process_documents(retrieved_at)

    print("Lucero consular process seed")
    print("----------------------------")
    for document in documents:
        print(f"{document['_id']}: {document['section_citation']}")

    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
        collection = client[settings.mongo_db][settings.mongo_consular_processes_collection]
        result = collection.bulk_write(
            [
                ReplaceOne({"_id": document["_id"]}, document, upsert=True)
                for document in documents
            ]
        )
        collection.create_index([("post", 1), ("status", 1), ("sort_order", 1)])
        collection.create_index("section_citation")
    except PyMongoError as exc:
        print("FAIL Could not upsert consular process records.")
        print(f"Reason: {exc}")
        return 1
    finally:
        try:
            client.close()
        except UnboundLocalError:
            pass

    print("PASS Consular process records upserted.")
    print(f"Matched: {result.matched_count}")
    print(f"Modified: {result.modified_count}")
    print(f"Upserted: {len(result.upserted_ids)}")
    return 0


def consular_process_documents(retrieved_at: str) -> list[dict[str, Any]]:
    return [
        build_document(
            record_id="consular-process-cdj-post-instructions",
            sort_order=10,
            title="U.S. Consulate General Ciudad Juarez immigrant visa instructions",
            section_citation="CDJ Post Instructions",
            summary=(
                "CDJ instructs immigrant visa applicants not to make travel plans to depart "
                "Ciudad Juarez or enter the United States until adjudication is complete. "
                "Applicants should register the appointment, complete ASC photos/fingerprints "
                "before the consular interview, schedule a medical exam in Mexico, complete "
                "the pre-interview checklist, and review interview guidelines."
            ),
            timeline_steps=[
                step(
                    "Register the appointment online so passport and visa-package return can be arranged by DHL.",
                    "CDJ Post Instructions",
                    CDJ_POST_URL,
                ),
                step(
                    "Schedule ASC photos and fingerprints before the Consulate interview.",
                    "CDJ Post Instructions",
                    CDJ_POST_URL,
                ),
                step(
                    "Schedule and attend the medical examination in Mexico at least three days before the interview.",
                    "CDJ Post Instructions",
                    CDJ_POST_URL,
                ),
                step(
                    "Bring required original documents and checklist items to the interview.",
                    "CDJ Post Instructions",
                    CDJ_POST_URL,
                ),
            ],
            source_urls={"cdj_post_instructions": CDJ_POST_URL},
            retrieved_at=retrieved_at,
        ),
        build_document(
            record_id="consular-process-nvc-submit-documents",
            sort_order=20,
            title="NVC upload and submit scanned documents",
            section_citation="NVC Submit Documents",
            summary=(
                "After uploading required Affidavit of Support and civil documents in CEAC, "
                "the applicant presses Submit Documents and the case is placed in line for "
                "National Visa Center review. If NVC finds the required fees, application, "
                "Affidavit of Support, and supporting documents complete, NVC sends a "
                "documentarily-complete notice and works with the appropriate embassy or "
                "consulate to schedule an appointment."
            ),
            timeline_steps=[
                step(
                    "Upload required financial and civil documents in CEAC and press Submit Documents.",
                    "NVC Submit Documents",
                    NVC_SUBMIT_DOCS_URL,
                ),
                step(
                    "If corrections are required, update CEAC and resubmit the case for review.",
                    "NVC Submit Documents",
                    NVC_SUBMIT_DOCS_URL,
                ),
                step(
                    "When documentarily complete, NVC works with the appropriate U.S. Embassy or Consulate to schedule an appointment.",
                    "NVC Submit Documents",
                    NVC_SUBMIT_DOCS_URL,
                ),
            ],
            source_urls={"nvc_submit_documents": NVC_SUBMIT_DOCS_URL},
            retrieved_at=retrieved_at,
        ),
        build_document(
            record_id="consular-process-nvc-interview-prep",
            sort_order=30,
            title="NVC interview preparation",
            section_citation="NVC Interview Preparation",
            summary=(
                "After NVC schedules the visa interview and sends the appointment letter, "
                "applicants must complete the medical examination with an approved physician, "
                "register for courier or post-specific instructions, and gather original or "
                "certified civil documents for the interview."
            ),
            timeline_steps=[
                step(
                    "After NVC sends the appointment letter, complete the required medical exam before the interview date.",
                    "NVC Interview Preparation",
                    NVC_INTERVIEW_PREP_URL,
                ),
                step(
                    "Register for courier service or follow the post-specific pre-interview instructions.",
                    "NVC Interview Preparation",
                    NVC_INTERVIEW_PREP_URL,
                ),
                step(
                    "Gather original or certified civil documents, photographs, and other interview documents.",
                    "NVC Interview Preparation",
                    NVC_INTERVIEW_PREP_URL,
                ),
            ],
            source_urls={"nvc_interview_preparation": NVC_INTERVIEW_PREP_URL},
            retrieved_at=retrieved_at,
        ),
        build_document(
            record_id="consular-process-nvc-applicant-interview",
            sort_order=40,
            title="NVC applicant interview",
            section_citation="NVC Applicant Interview",
            summary=(
                "At the immigrant visa interview, the applicant brings the DS-260 confirmation "
                "page and required original or certified civil documents. A consular officer "
                "interviews the applicant and accompanying qualifying family members, determines "
                "visa eligibility, and takes ink-free digital fingerprints."
            ),
            timeline_steps=[
                step(
                    "Attend the scheduled interview with the printed DS-260 confirmation page.",
                    "NVC Applicant Interview",
                    NVC_APPLICANT_INTERVIEW_URL,
                ),
                step(
                    "Bring required original or certified civil documents and translations when required.",
                    "NVC Applicant Interview",
                    NVC_APPLICANT_INTERVIEW_URL,
                ),
                step(
                    "Do not make permanent financial commitments or travel arrangements until the immigrant visa is received.",
                    "NVC Applicant Interview",
                    NVC_APPLICANT_INTERVIEW_URL,
                ),
            ],
            source_urls={"nvc_applicant_interview": NVC_APPLICANT_INTERVIEW_URL},
            retrieved_at=retrieved_at,
        ),
    ]


def build_document(
    *,
    record_id: str,
    sort_order: int,
    title: str,
    section_citation: str,
    summary: str,
    timeline_steps: list[dict[str, str]],
    source_urls: dict[str, str],
    retrieved_at: str,
) -> dict[str, Any]:
    basis = {
        "post": "CDJ",
        "title": title,
        "section_citation": section_citation,
        "summary": summary,
        "timeline_steps": timeline_steps,
        "source_urls": source_urls,
    }
    return {
        "_id": record_id,
        **basis,
        "sort_order": sort_order,
        "agency": "DOS",
        "jurisdiction": "federal",
        "doc_type": "consular_process",
        "status": "active",
        "retrieval_date": retrieved_at,
        "content_hash": hashlib.sha256(repr(sorted(basis.items())).encode("utf-8")).hexdigest(),
    }


def step(text: str, citation: str, source_url: str) -> dict[str, str]:
    return {
        "text": text,
        "section_citation": citation,
        "source_url": source_url,
    }


if __name__ == "__main__":
    raise SystemExit(main())
