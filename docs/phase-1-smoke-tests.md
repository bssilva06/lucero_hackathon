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

## Expected Result

- `env` should show `PASS` for all required variables.
- `atlas` should connect and print the server version.
- `mcp` should find `npx` and confirm the MCP server can launch.

## What This Does Not Prove Yet

- `$rankFusion` support.
- Atlas Automated Embedding availability.
- Vector and full-text search indexes.
- Gemini model availability.

Those require the first ingestion/index fixture and the ADK backend skeleton.
