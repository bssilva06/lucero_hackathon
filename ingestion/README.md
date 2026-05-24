# Ingestion

Source fetching, parsing, chunking, and MongoDB Atlas loading for the Lucero MVP corpus.

## MVP Source Corpus

- USCIS Policy Manual Vol. 9 Pt. B
- USCIS Policy Manual Vol. 9 Pt. C
- USCIS Policy Manual Vol. 6 Pt. B
- I-601A and I-130 instruction PDFs
- Last 3 Visa Bulletins
- Ciudad Juarez consular post information
- G-1055 fee schedule

## Design Notes

- Prefer structure-aware chunking by document headings and legal sections.
- Preserve source URL, section citation, retrieval date, effective date, content hash, and document status.
- Keep local fixtures small and non-secret so tests can run without Atlas access.

## Fixture Embedding Smoke Test

After adding `VOYAGE_API_KEY` to the repository `.env`, run:

```powershell
cd C:\Users\trash\Documents\Lucero
backend\.venv\Scripts\python.exe ingestion\scripts\embed_fixture_chunks.py
```

This generates Voyage embeddings for the synthetic fixture chunks and upserts them into the configured Atlas `chunks` collection with `embedding`, `embedding_model`, `embedding_provider`, and `embedded_at` fields.

## Atlas Search Index Setup

After fixture chunks have embeddings, create or confirm the Atlas Search indexes:

```powershell
cd C:\Users\trash\Documents\Lucero
backend\.venv\Scripts\python.exe ingestion\scripts\create_search_indexes.py
```

This creates the configured Vector Search index on `embedding` and a text Search index on `text` plus citation metadata if they do not already exist.

## Hybrid Retrieval Smoke Test

After creating indexes, run:

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\python.exe -m app.smoke_tests.hybrid_retrieval
```

This embeds a query with Voyage, runs `$vectorSearch`, `$search`, and `$rankFusion`, and expects the I-601A hardship fixture to rank first.

## USCIS Policy Manual Ingestion

Dry-run the first real corpus parser:

```powershell
cd C:\Users\trash\Documents\Lucero
backend\.venv\Scripts\python.exe ingestion\scripts\ingest_uscis_policy_manual.py --dry-run
```

Run live ingestion after the dry run succeeds:

```powershell
cd C:\Users\trash\Documents\Lucero
backend\.venv\Scripts\python.exe ingestion\scripts\ingest_uscis_policy_manual.py
```

This ingests USCIS Policy Manual Volume 9 Part B and Part H HTML pages, chunks by headings, embeds chunks with Voyage, and upserts them into Atlas.

Verify the real corpus retrieval path:

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\python.exe -m app.smoke_tests.real_policy_retrieval
```
