# Phase 1 Smoke Tests

These checks verify the local credentials and MongoDB Atlas setup without committing secrets.

## Prerequisites

- `.env` exists at the repository root.
- Google Cloud CLI is installed and authenticated.
- MongoDB Atlas cluster is created.
- Atlas database user exists.
- Your current IP is on the Atlas Network Access list.
- Node.js 20+ is installed for `npx` and the MongoDB MCP server.
- `mongodb-mcp-server` has been installed ahead of time so `npx --no-install` can launch it without package-manager output on stdio.

## Install Backend Dependencies

From the repository root:

```powershell
cd C:\Users\trash\Documents\Lucero\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Environment Check

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\Activate.ps1
python -m app.smoke_tests.env
```

## Atlas Connectivity Check

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\Activate.ps1
python -m app.smoke_tests.atlas
```

## MongoDB MCP Launch Check

This command uses the configured MCP launcher. By default, Lucero uses `npx --no-install mongodb-mcp-server --readOnly` to avoid first-run package-manager warnings corrupting MCP stdio.

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\Activate.ps1
python -m app.smoke_tests.mcp
```

## Atlas Fixture Seed

This inserts a tiny deterministic fixture corpus into the configured `chunks` collection. The documents are synthetic and are only for connectivity/tooling verification.

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\Activate.ps1
python -m app.smoke_tests.seed_fixtures
```

## MongoDB MCP Retrieval Check

Run this after seeding fixtures. It calls the MongoDB MCP `find` and `aggregate` tools against the fixture documents.

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\Activate.ps1
python -m app.smoke_tests.mcp_retrieval
```

## Gemini / Vertex Check

The smoke test tries `GEMINI_REASONING_MODEL` first. If that model is unavailable in the configured Vertex region, it tries current stable fallback candidates and prints the `.env` value to use.

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\Activate.ps1
python -m app.smoke_tests.gemini
```

## FastAPI Health Check

This starts the backend on `127.0.0.1:8080`, waits for `/api/health`, then shuts the process down.

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\Activate.ps1
python -m app.smoke_tests.api_health
```

## FastAPI Chat Check

This starts the backend, posts a non-legal diagnostic request to `/api/chat`, then shuts the process down. Run this only after `python -m app.smoke_tests.gemini` confirms the configured model works.

```powershell
cd C:\Users\trash\Documents\Lucero\backend
.\.venv\Scripts\Activate.ps1
python -m app.smoke_tests.api_chat
```

## Expected Result

- `env` should show `PASS` for all required variables.
- `atlas` should connect and print the server version.
- `mcp` should find `npx` and confirm the MCP server can launch.
- `seed_fixtures` should upsert 3 fixture source chunks.
- `mcp_retrieval` should confirm both `find` and `aggregate` can retrieve fixture data through MCP.
- `gemini` should receive a short response from the configured Gemini model.
- `api_health` should receive `{"app": "Lucero ADK Backend", "status": "ok"}`.
- `api_chat` should receive a non-empty response from `/api/chat`.

## What This Does Not Prove Yet

- `$rankFusion` support.
- Atlas Automated Embedding availability.
- Vector and full-text search indexes.

Those require the first ingestion/index fixture and the ADK backend skeleton.
