from __future__ import annotations

import argparse
import hashlib
import io
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag
from pymongo import MongoClient, ReplaceOne
from pymongo.errors import PyMongoError
from pypdf import PdfReader


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_settings  # noqa: E402


USER_AGENT = (
    "LuceroResearchCoPilot/0.1 "
    "(local MVP ingestion; contact: repository operator; source verification)"
)
G1055_URL = "https://www.uscis.gov/sites/default/files/document/forms/g-1055.pdf"
FORM_SOURCES = {
    "I-601A": {
        "page_url": "https://www.uscis.gov/i-601a",
        "instructions_url": "https://www.uscis.gov/sites/default/files/document/forms/i-601ainstr.pdf",
    },
    "I-130": {
        "page_url": "https://www.uscis.gov/i-130",
        "instructions_url": "https://www.uscis.gov/sites/default/files/document/forms/i-130instr.pdf",
    },
}


@dataclass(frozen=True)
class ParsedForm:
    form_number: str
    title: str
    edition_date: str | None
    filing_methods: list[str]
    filing_location_summary: str | None
    fee_entries: list[dict[str, Any]]
    source_urls: dict[str, str]


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest curated USCIS form lookup records.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and parse without Atlas writes.")
    args = parser.parse_args()

    fetched_at = datetime.now(UTC)
    print("Lucero USCIS forms ingestion")
    print("----------------------------")
    print(f"Forms: {', '.join(FORM_SOURCES)}")

    try:
        fee_schedule_text = fetch_pdf_text(G1055_URL)
        forms = [
            parse_form(form_number, sources, fee_schedule_text=fee_schedule_text)
            for form_number, sources in FORM_SOURCES.items()
        ]
    except Exception as exc:
        print("FAIL Could not fetch or parse USCIS form sources.")
        print(f"Reason: {exc}")
        return 1

    documents = [build_document(form, fetched_at=fetched_at) for form in forms]
    for document in documents:
        print()
        print(f"{document['form_number']}: {document['title']}")
        print(f"- edition date: {document.get('edition_date') or '(not parsed)'}")
        print(f"- filing methods: {', '.join(document.get('filing_methods') or []) or '(not parsed)'}")
        fee_summary = ", ".join(
            f"{entry.get('label')}: {entry.get('amount')}"
            for entry in document.get("fee_entries") or []
        )
        print(f"- fee entries: {fee_summary}")
        print(f"- form page: {document['source_urls']['form_page']}")
        if document.get("filing_location_summary"):
            print(f"- filing location: {str(document['filing_location_summary'])[:300]}")

    if args.dry_run:
        print()
        print("PASS Dry run completed without Atlas writes.")
        return 0

    settings = load_settings()
    try:
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10_000)
        collection = client[settings.mongo_db][settings.mongo_forms_collection]
        result = collection.bulk_write(
            [
                ReplaceOne({"_id": document["_id"]}, document, upsert=True)
                for document in documents
            ]
        )
        collection.create_index("form_number")
        collection.create_index("status")
    except PyMongoError as exc:
        print("FAIL Could not upsert USCIS form records.")
        print(f"Reason: {exc}")
        return 1
    finally:
        try:
            client.close()
        except UnboundLocalError:
            pass

    print()
    print("PASS USCIS form records upserted.")
    print(f"Matched: {result.matched_count}")
    print(f"Modified: {result.modified_count}")
    print(f"Upserted: {len(result.upserted_ids)}")
    return 0


def parse_form(
    form_number: str,
    sources: dict[str, str],
    *,
    fee_schedule_text: str,
) -> ParsedForm:
    soup = BeautifulSoup(fetch_bytes(sources["page_url"]).decode("utf-8", errors="replace"), "html.parser")
    root = content_root(soup)
    title = normalize_space((root.find("h1") or soup.find("h1") or soup.title).get_text(" "))
    page_text = normalize_space(root.get_text("\n"))
    edition_date = extract_edition_date(page_text)
    filing_methods = extract_filing_methods(page_text)
    filing_location_summary = extract_section(root, "Where to File") or extract_label_block(
        page_text,
        "Where to File",
        stop_labels=["Filing Fee", "Form Filing Tips", "Special Instructions"],
    )
    fee_entries = extract_fee_entries(fee_schedule_text, form_number)
    if not fee_entries:
        fee_entries = extract_fee_entries(page_text, form_number)
    if not fee_entries:
        raise RuntimeError(f"No fee entries parsed for {form_number}")

    return ParsedForm(
        form_number=form_number,
        title=title,
        edition_date=edition_date,
        filing_methods=filing_methods,
        filing_location_summary=filing_location_summary,
        fee_entries=fee_entries,
        source_urls={
            "form_page": sources["page_url"],
            "instructions_pdf": sources["instructions_url"],
            "fee_schedule_pdf": G1055_URL,
        },
    )


def build_document(form: ParsedForm, *, fetched_at: datetime) -> dict[str, Any]:
    content_basis = {
        "form_number": form.form_number,
        "title": form.title,
        "edition_date": form.edition_date,
        "filing_methods": form.filing_methods,
        "filing_location_summary": form.filing_location_summary,
        "fee_entries": form.fee_entries,
        "source_urls": form.source_urls,
    }
    content_hash = hashlib.sha256(repr(sorted(content_basis.items())).encode("utf-8")).hexdigest()
    return {
        "_id": f"uscis-form-{form.form_number.lower()}",
        "form_number": form.form_number,
        "title": form.title,
        "edition_date": form.edition_date,
        "filing_methods": form.filing_methods,
        "filing_location_summary": form.filing_location_summary,
        "fee_entries": form.fee_entries,
        "source_urls": form.source_urls,
        "section_citation": "USCIS G-1055",
        "agency": "USCIS",
        "jurisdiction": "federal",
        "doc_type": "form_lookup",
        "status": "active",
        "retrieval_date": fetched_at.isoformat(),
        "content_hash": content_hash,
    }


def fetch_bytes(url: str) -> bytes:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,*/*"},
        timeout=45,
    )
    response.raise_for_status()
    return response.content


def fetch_pdf_text(url: str) -> str:
    reader = PdfReader(io.BytesIO(fetch_bytes(url)))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def content_root(soup: BeautifulSoup) -> Tag:
    for tag in soup(["script", "style", "noscript", "svg", "form", "nav", "header", "footer", "aside"]):
        tag.decompose()
    for selector in ["article", "main", "[role='main']", ".field--name-body"]:
        root = soup.select_one(selector)
        if root:
            return root
    if not soup.body:
        raise RuntimeError("USCIS page did not contain a body element")
    return soup.body


def extract_edition_date(text: str) -> str | None:
    match = re.search(r"Edition Date\s+([0-9]{2}/[0-9]{2}/[0-9]{2,4})", text, re.IGNORECASE)
    return match.group(1) if match else None


def extract_filing_methods(text: str) -> list[str]:
    methods: list[str] = []
    lowered = text.lower()
    if "online" in lowered:
        methods.append("online")
    if "by mail" in lowered or "mail your" in lowered or "paper" in lowered:
        methods.append("paper")
    return methods


def extract_section(root: Tag, heading_text: str) -> str | None:
    heading = None
    for candidate in root.find_all(["h2", "h3", "h4"]):
        if normalize_space(candidate.get_text(" ")).lower() == heading_text.lower():
            heading = candidate
            break
    if not heading:
        return None

    parts: list[str] = []
    for sibling in heading.find_all_next():
        if sibling.name in {"h2", "h3", "h4"} and sibling is not heading:
            break
        if sibling.name in {"p", "li", "table"}:
            text = normalize_space(sibling.get_text(" "))
            if text:
                parts.append(text)
    return normalize_space("\n\n".join(parts)) or None


def extract_label_block(text: str, label: str, *, stop_labels: list[str]) -> str | None:
    start = text.lower().find(label.lower())
    if start < 0:
        return None
    content_start = start + len(label)
    stop_positions = [
        position
        for stop_label in stop_labels
        if (position := text.lower().find(stop_label.lower(), content_start)) >= 0
    ]
    content_end = min(stop_positions) if stop_positions else min(len(text), content_start + 1_500)
    block = normalize_space(text[content_start:content_end])
    return block or None


def extract_fee_entries(text: str, form_number: str) -> list[dict[str, Any]]:
    block = extract_fee_block(text, form_number)
    if not block:
        return []

    paper_match = re.search(r"Paper Filing:\s*(\$\s?\d[\d,]*)", block, re.IGNORECASE)
    online_match = re.search(r"Online Filing:\s*(\$\s?\d[\d,]*)", block, re.IGNORECASE)
    if paper_match or online_match:
        entries = []
        if online_match:
            entries.append(fee_entry("online filing fee", online_match.group(1)))
        if paper_match:
            entries.append(fee_entry("paper filing fee", paper_match.group(1)))
        return entries

    general_match = re.search(r"General filing(?:, unless noted below\.)?\s*(\$\s?\d[\d,]*)", block, re.IGNORECASE)
    if general_match:
        return [fee_entry("filing fee", general_match.group(1))]

    return []


def extract_fee_block(text: str, form_number: str) -> str | None:
    row_match = re.search(rf"(?m)^{re.escape(form_number)}\s*$", text)
    if not row_match:
        return None
    next_row = re.search(r"(?m)^I-\d+[A-Z]?\s*$", text[row_match.end() :])
    end = row_match.end() + next_row.start() if next_row else min(len(text), row_match.start() + 1_500)
    return text[row_match.start() : end]


def fee_entry(label: str, amount: str) -> dict[str, Any]:
    return {
        "label": label,
        "amount": amount.replace(" ", ""),
        "section_citation": "USCIS G-1055",
        "source_url": G1055_URL,
    }


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


if __name__ == "__main__":
    raise SystemExit(main())
