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
