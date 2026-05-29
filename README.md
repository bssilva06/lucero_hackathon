# Lucero

Bilingual research co-pilot for immigration legal teams, focused on I-601A provisional unlawful presence waivers and Ciudad Juarez consular processing.

Lucero is designed as a citation-first AI research tool for licensed immigration practitioners. It retrieves primary-source immigration authority from MongoDB Atlas, uses Google ADK and Gemini to synthesize answers, and presents every factual claim with source metadata.

## MVP Stack

- Backend: Python, Google Agent Development Kit, Gemini
- Database: MongoDB Atlas
- Retrieval: Google Vertex AI `gemini-embedding-001` embeddings in MongoDB Atlas, `$rankFusion` when available, `$vectorSearch` fallback
- MCP: official MongoDB MCP server
- Frontend: React, Vite, Tailwind CSS
- Deployment: Cloud Run, with secrets in Google Secret Manager

## Repository Layout

```text
.
├── backend/       # ADK agent, API server, tools, backend tests
├── frontend/      # React/Vite/Tailwind app
├── ingestion/     # Source fetching, parsing, chunking, Atlas loading
├── evals/         # MVP acceptance prompts and evaluation harness
├── docs/          # Architecture, demo script, implementation notes
├── AGENT.md       # Codex project memory and progress tracker
└── lucero-prd-v1.1-updated.md
```

## Getting Started

Local development uses a backend virtual environment, MongoDB Atlas, Google Vertex AI/Gemini credentials, and the Vite frontend.

1. Copy `.env.example` to `.env` and set Google Cloud, MongoDB Atlas, and MCP connection values.
2. Install backend dependencies:

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\python.exe -m pip install -e .
```

3. Confirm or create Atlas Search indexes:

```powershell
cd C:\Users\trash\Documents\Lucero
backend\.venv\Scripts\python.exe ingestion\scripts\create_search_indexes.py
```

4. Run the backend:

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

5. Run the frontend:

```powershell
cd C:\Users\trash\Documents\Lucero\frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Current Corpus

- USCIS Policy Manual Volume 9 Part B and Part H are ingested as Atlas `chunks` with 3072-dimensional Google Vertex AI embeddings.
- USCIS Form I-601A, Form I-130, and G-1055 fee metadata are ingested as curated Atlas `forms` records.
- CDJ post instructions and NVC consular-processing timeline facts are ingested as curated Atlas `consular_processes` records.
- Runtime retrieval uses `vector_google_embedding_index` plus `fts_index`.

Useful checks:

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\python.exe -m app.smoke_tests.real_policy_retrieval
.\.venv\Scripts\python.exe -m app.smoke_tests.forms_lookup
.\.venv\Scripts\python.exe -m app.smoke_tests.consular_process
.\.venv\Scripts\python.exe -m app.smoke_tests.api_chat_sources
.\.venv\Scripts\python.exe -m app.smoke_tests.api_chat_cdj_timeline
```

Run focused MVP evals from the repository root:

```powershell
backend\.venv\Scripts\python.exe evals\run_mvp_evals.py --case hardship-evidence --timeout-seconds 90
```

The eval runner restarts the backend per case by default for reliable batch results.

## Safety Posture

Lucero is not legal advice and is not a consumer immigration guide. It is a research and drafting aid for licensed immigration practitioners. Outputs must be verified against retrieved source authority before use in a client matter.

## License

Apache-2.0.
