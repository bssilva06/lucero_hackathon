# Backend

Python backend for the Lucero ADK agent, HTTP API, tool implementations, MongoDB MCP integration, and backend tests.

## Components

- ADK agent configuration and system prompt
- Function tools:
  - `search_uscis_policy_manual`
  - `lookup_uscis_form`
  - `check_visa_bulletin`
  - `format_legal_citation`
- Agent tool:
  - `translate_legal_es_en`
- MongoDB MCP toolset wiring
- API endpoint for the frontend

## Runtime

- Python 3.11+
- Dependency manager: `uv` preferred, `pip` acceptable as fallback

## Environment

The backend reads configuration from the repository `.env`. Important retrieval settings:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_EMBEDDING_MODEL=gemini-embedding-001
LUCERO_VECTOR_INDEX=vector_google_embedding_index
LUCERO_VECTOR_DIMENSIONS=3072
LUCERO_FTS_INDEX=fts_index
```

MongoDB Atlas settings must include `MONGO_URI` and `MDB_MCP_CONNECTION_STRING`.

## Running

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/health
```

## Smoke Tests

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m app.smoke_tests.env
.\.venv\Scripts\python.exe -m app.smoke_tests.hybrid_retrieval
.\.venv\Scripts\python.exe -m app.smoke_tests.real_policy_retrieval
.\.venv\Scripts\python.exe -m app.smoke_tests.forms_lookup
.\.venv\Scripts\python.exe -m app.smoke_tests.api_chat_sources
```

Do not run server-starting smoke tests in parallel; they bind to port `8080`.
