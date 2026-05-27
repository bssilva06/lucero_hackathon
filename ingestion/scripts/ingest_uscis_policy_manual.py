from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import load_settings  # noqa: E402
from app.embeddings import embed_texts  # noqa: E402


BASE_URL = "https://www.uscis.gov"
TOC_URL = f"{BASE_URL}/policy-manual/table-of-contents"
PART_H_URL = f"{BASE_URL}/policy-manual/volume-9-part-h"
PART_B_URLS = [
    f"{BASE_URL}/policy-manual/volume-9-part-b-chapter-{chapter_number}"
    for chapter_number in range(1, 8)
]

USER_AGENT = (
    "LuceroResearchCoPilot/0.1 "
    "(local MVP ingestion; contact: repository operator; source verification)"
)
CHUNK_STRATEGY = "uscis-policy-manual-html-v1"
TARGET_WORDS = 450
MIN_WORDS = 25


@dataclass(frozen=True)
class ParsedPage:
    source_url: str
    source_id: str
    title: str
    volume: str
    part: str
    chapter: str | None
    base_citation: str
    sections: list["ParsedSection"]


@dataclass(frozen=True)
class ParsedSection:
    heading: str
    heading_level: int
    section_path: list[str]
    section_citation: str
    text: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest USCIS Policy Manual Vol. 9 Parts B and H.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and summarize without embeddings or Atlas writes.")
    parser.add_argument("--limit-pages", type=int, default=0, help="Limit fetched pages for parser debugging.")
    parser.add_argument("--run-id", default="", help="Override ingestion run id.")
    parser.add_argument(
        "--embedding-cache",
        default="",
        help="Path to a local JSON embedding cache. Defaults to tmp/uscis_policy_manual_embeddings_<model>_<dimensions>.json.",
    )
    args = parser.parse_args()

    settings = load_settings()
    fetched_at = datetime.now(UTC)
    ingestion_run_id = args.run_id or f"uscis-policy-manual-{fetched_at:%Y%m%d-%H%M%S}"

    print("Lucero USCIS Policy Manual ingestion")
    print("------------------------------------")
    print("Corpus: Volume 9 Part B + Volume 9 Part H")
    print(f"Ingestion run id: {ingestion_run_id}")

    try:
        page_urls = discover_page_urls(limit_pages=args.limit_pages)
        pages = [parse_policy_page(url, fetched_at=fetched_at) for url in page_urls]
    except Exception as exc:
        print("FAIL Could not fetch or parse USCIS Policy Manual pages.")
        print(f"Reason: {exc}")
        return 1

    chunks = build_chunks(pages, ingestion_run_id=ingestion_run_id, fetched_at=fetched_at)
    if not chunks:
        print("FAIL Parser produced zero chunks; refusing to continue.")
        return 1

    print(f"Pages parsed: {len(pages)}")
    print(f"Chunks built: {len(chunks)}")
    print("Sample citations: " + ", ".join(sorted({chunk["section_citation"] for chunk in chunks})[:8]))
    print()
    print("First chunk preview")
    print(f"- id: {chunks[0]['_id']}")
    print(f"- citation: {chunks[0]['section_citation']}")
    print(f"- words: {chunks[0]['token_count']}")
    print(f"- text: {chunks[0]['text'][:500]}")

    if args.dry_run:
        print()
        print("PASS Dry run completed without Atlas writes.")
        return 0

    cache_path = (
        Path(args.embedding_cache)
        if args.embedding_cache
        else default_embedding_cache_path(settings.google_embedding_model, settings.vector_dimensions)
    )
    try:
        embeddings = embed_chunks_with_cache(chunks, cache_path=cache_path, settings=settings)
    except Exception as exc:
        print("FAIL Google embedding request failed.")
        print(f"Reason: {exc}")
        return 1

    embedded_at = datetime.now(UTC).isoformat()
    operations = []
    for chunk, embedding in zip(chunks, embeddings, strict=True):
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
        print("FAIL Could not upsert USCIS Policy Manual chunks.")
        print(f"Reason: {exc}")
        return 1
    finally:
        try:
            client.close()
        except UnboundLocalError:
            pass

    print()
    print("PASS USCIS Policy Manual chunks embedded and upserted.")
    print(f"Embedding dimensions: {len(embeddings[0])}")
    print(f"Matched: {result.matched_count}")
    print(f"Modified: {result.modified_count}")
    print(f"Upserted: {len(result.upserted_ids)}")
    return 0


def embed_chunks_with_cache(
    chunks: list[dict[str, object]],
    *,
    cache_path: Path,
    settings: object,
) -> list[list[float]]:
    cache = load_embedding_cache(cache_path)
    embeddings: list[list[float]] = []
    cache_hits = 0

    print()
    print(f"Embedding cache: {cache_path}")
    print(f"Embedding model: {settings.google_embedding_model}")
    print(f"Embedding dimensions: {settings.vector_dimensions}")

    for index, chunk in enumerate(chunks, start=1):
        chunk_id = str(chunk["_id"])
        content_hash = str(chunk["content_hash"])
        cached_embedding = cached_chunk_embedding(
            cache,
            chunk_id=chunk_id,
            content_hash=content_hash,
            model=settings.google_embedding_model,
            dimensions=settings.vector_dimensions,
        )
        if cached_embedding is not None:
            cache_hits += 1
            embeddings.append(cached_embedding)
            print(f"EMBED {index}/{len(chunks)} cache hit: {chunk_id}", flush=True)
            continue

        print(f"EMBED {index}/{len(chunks)} request: {chunk_id}", flush=True)
        embedding = embed_texts(
            [str(chunk["text"])],
            project_id=settings.google_cloud_project,
            location=settings.google_cloud_location,
            model=settings.google_embedding_model,
            input_type="document",
            output_dimensionality=settings.vector_dimensions,
            request_delay_seconds=2,
        )[0]
        if len(embedding) != settings.vector_dimensions:
            raise RuntimeError(
                f"Unexpected embedding dimensions for {chunk_id}: "
                f"{len(embedding)} != {settings.vector_dimensions}"
            )
        embeddings.append(embedding)
        cache[chunk_id] = {
            "content_hash": content_hash,
            "embedding_model": settings.google_embedding_model,
            "embedding_provider": "google_vertex_ai",
            "dimensions": settings.vector_dimensions,
            "embedding": embedding,
        }
        save_embedding_cache(cache_path, cache)

    print(f"Embedding cache hits: {cache_hits}/{len(chunks)}")
    return embeddings


def default_embedding_cache_path(model: str, dimensions: int) -> Path:
    safe_model = re.sub(r"[^a-zA-Z0-9]+", "_", model).strip("_").lower()
    return ROOT_DIR / "tmp" / f"uscis_policy_manual_embeddings_{safe_model}_{dimensions}.json"


def load_embedding_cache(cache_path: Path) -> dict[str, dict[str, object]]:
    if not cache_path.exists():
        return {}
    with cache_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise RuntimeError(f"Embedding cache is not a JSON object: {cache_path}")
    return {
        str(key): value
        for key, value in data.items()
        if isinstance(value, dict)
    }


def save_embedding_cache(cache_path: Path, cache: dict[str, dict[str, object]]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_suffix(f"{cache_path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(cache, handle)
    temp_path.replace(cache_path)


def cached_chunk_embedding(
    cache: dict[str, dict[str, object]],
    *,
    chunk_id: str,
    content_hash: str,
    model: str,
    dimensions: int,
) -> list[float] | None:
    entry = cache.get(chunk_id)
    if not entry:
        return None
    if entry.get("content_hash") != content_hash:
        return None
    if entry.get("embedding_model") != model:
        return None
    if entry.get("dimensions") != dimensions:
        return None
    embedding = entry.get("embedding")
    if not isinstance(embedding, list) or len(embedding) != dimensions:
        return None
    return [float(value) for value in embedding]


def discover_page_urls(*, limit_pages: int = 0) -> list[str]:
    part_h_links = discover_part_h_urls()
    urls = [*PART_B_URLS, *part_h_links]
    deduped = list(dict.fromkeys(urls))
    if limit_pages:
        return deduped[:limit_pages]
    return deduped


def discover_part_h_urls() -> list[str]:
    urls = {PART_H_URL}
    for url in [PART_H_URL, TOC_URL]:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = str(anchor["href"])
            absolute_url = urljoin(BASE_URL, href).split("#", 1)[0]
            parsed = urlparse(absolute_url)
            if parsed.netloc != "www.uscis.gov":
                continue
            if re.search(r"/policy-manual/volume-9-part-h(?:-chapter-\d+)?$", parsed.path):
                urls.add(absolute_url)
    return sorted(urls, key=_policy_url_sort_key)


def parse_policy_page(url: str, *, fetched_at: datetime) -> ParsedPage:
    soup = BeautifulSoup(fetch_html(url), "html.parser")
    root = content_root(soup)
    title = normalize_space((root.find("h1") or soup.find("h1") or soup.title).get_text(" "))
    source_id, volume, part, chapter, base_citation = policy_metadata(url)
    sections = parse_sections(root, title, volume, part, chapter, base_citation)

    if not sections:
        raise RuntimeError(f"No sections parsed from {url}")

    return ParsedPage(
        source_url=url,
        source_id=source_id,
        title=title,
        volume=volume,
        part=part,
        chapter=chapter,
        base_citation=base_citation,
        sections=sections,
    )


def fetch_html(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=30,
    )
    response.raise_for_status()
    if "text/html" not in response.headers.get("content-type", ""):
        raise RuntimeError(f"Expected HTML from {url}, got {response.headers.get('content-type')}")
    return response.text


def content_root(soup: BeautifulSoup) -> Tag:
    for tag in soup(["script", "style", "noscript", "svg", "form", "nav", "header", "footer", "aside"]):
        tag.decompose()

    for selector in ["article", "main", "[role='main']", ".field--name-body"]:
        root = soup.select_one(selector)
        if root:
            return root

    body = soup.body
    if not body:
        raise RuntimeError("USCIS page did not contain a body element")
    return body


def parse_sections(
    root: Tag,
    title: str,
    volume: str,
    part: str,
    chapter: str | None,
    base_citation: str,
) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    current_heading = title
    current_level = 1
    current_text_parts: list[str] = []
    current_path = section_path(volume, part, chapter, current_heading)
    current_citation = base_citation

    for element in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "table"]):
        text = normalize_space(element.get_text(" "))
        if not text or should_skip_text(text):
            continue

        if element.name in {"h1", "h2", "h3", "h4"}:
            flush_section(
                sections,
                current_heading,
                current_level,
                current_path,
                current_citation,
                current_text_parts,
            )
            current_heading = text
            current_level = int(element.name[1])
            current_text_parts = []
            current_path = section_path(volume, part, chapter, current_heading)
            current_citation = section_citation(base_citation, current_heading)
            continue

        current_text_parts.append(text)

    flush_section(
        sections,
        current_heading,
        current_level,
        current_path,
        current_citation,
        current_text_parts,
    )
    return sections


def flush_section(
    sections: list[ParsedSection],
    heading: str,
    level: int,
    path: list[str],
    citation: str,
    text_parts: list[str],
) -> None:
    text = normalize_space("\n\n".join(text_parts))
    if word_count(text) < MIN_WORDS:
        return
    sections.append(
        ParsedSection(
            heading=heading,
            heading_level=level,
            section_path=path,
            section_citation=citation,
            text=text,
        )
    )


def build_chunks(
    pages: list[ParsedPage],
    *,
    ingestion_run_id: str,
    fetched_at: datetime,
) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    for page in pages:
        page_chunk_index = 0
        for section in page.sections:
            for part_index, chunk_text in enumerate(split_section_text(section.text), start=1):
                page_chunk_index += 1
                content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                chunk_id = stable_chunk_id(page.source_id, section.section_citation, part_index, content_hash)
                chunks.append(
                    {
                        "_id": chunk_id,
                        "text": chunk_text,
                        "source_url": page.source_url,
                        "doc_id": page.source_id,
                        "doc_type": "policy_manual",
                        "agency": "USCIS",
                        "jurisdiction": "federal",
                        "section_path": section.section_path,
                        "section_citation": section.section_citation,
                        "parent_doc_id": page.source_id,
                        "chunk_index": page_chunk_index,
                        "chunk_strategy": CHUNK_STRATEGY,
                        "token_count": word_count(chunk_text),
                        "version_label": f"uscis-html-{fetched_at:%Y-%m-%d}",
                        "effective_from": None,
                        "effective_to": None,
                        "status": "active",
                        "superseded_by": None,
                        "retrieval_date": fetched_at.isoformat(),
                        "content_hash": content_hash,
                        "ingestion_run_id": ingestion_run_id,
                    }
                )
    return chunks


def split_section_text(text: str) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for paragraph in paragraphs:
        paragraph_words = word_count(paragraph)
        if paragraph_words > TARGET_WORDS:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_words = 0
            chunks.extend(split_long_text(paragraph))
            continue

        if current and current_words + paragraph_words > TARGET_WORDS:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_words = paragraph_words
        else:
            current.append(paragraph)
            current_words += paragraph_words

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def split_long_text(text: str) -> list[str]:
    words = text.split()
    return [
        " ".join(words[start : start + TARGET_WORDS])
        for start in range(0, len(words), TARGET_WORDS)
    ]


def policy_metadata(url: str) -> tuple[str, str, str, str | None, str]:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    match = re.match(r"volume-(\d+)-part-([a-z])(?:-chapter-(\d+))?$", slug)
    if not match:
        raise RuntimeError(f"Unexpected USCIS Policy Manual URL slug: {slug}")

    volume_number = match.group(1)
    part_letter = match.group(2).upper()
    chapter_number = match.group(3)
    volume = f"Volume {volume_number}"
    part = f"Part {part_letter}"
    chapter = f"Chapter {chapter_number}" if chapter_number else None
    source_id = f"uscis-policy-manual-vol{volume_number}-pt{part_letter.lower()}"
    if chapter_number:
        source_id = f"{source_id}-ch{chapter_number}"
    citation = f"{volume_number} USCIS-PM {part_letter}"
    if chapter_number:
        citation = f"{citation}.{chapter_number}"
    return source_id, volume, part, chapter, citation


def section_path(volume: str, part: str, chapter: str | None, heading: str) -> list[str]:
    path = [volume, part]
    if chapter:
        path.append(chapter)
    if heading:
        path.append(heading)
    return path


def section_citation(base_citation: str, heading: str) -> str:
    match = re.match(r"^([A-Z])\.\s+", heading)
    if match:
        return f"{base_citation}.{match.group(1)}"
    return base_citation


def stable_chunk_id(source_id: str, citation: str, part_index: int, content_hash: str) -> str:
    key = f"{source_id}:{citation}:{part_index}:{content_hash[:16]}"
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", key).strip("-").lower()
    return normalized[:180]


def normalize_space(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    value = value.replace("\xa0", " ")
    return value.strip()


def word_count(value: str) -> int:
    return len(re.findall(r"\b\w+\b", value))


def should_skip_text(text: str) -> bool:
    lowered = text.lower()
    if lowered in {"guidance", "resources", "appendices", "updates"}:
        return True
    if lowered.startswith("alert:"):
        return True
    return False


def _policy_url_sort_key(url: str) -> tuple[int, str]:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    match = re.search(r"chapter-(\d+)$", slug)
    if match:
        return (int(match.group(1)), url)
    return (0, url)


if __name__ == "__main__":
    raise SystemExit(main())
