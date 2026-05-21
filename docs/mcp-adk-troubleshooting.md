# MCP and ADK Troubleshooting Notes

This document records the first local ADK/MongoDB MCP failures and the fixes that made the backend stable on Windows.

## 1. Stdio Warning Stream Corruption

Symptom:

- ADK starts the MongoDB MCP server over stdio.
- First-time `npx -y mongodb-mcp-server` prints install/download/deprecation output.
- The MCP JSON-RPC session fails during initialization.

Cause:

- Stdio MCP expects clean protocol streams. Package-manager chatter during startup can interfere with the Python MCP/ADK session.

Current fix:

- Install `mongodb-mcp-server` before running the agent.
- Launch MCP with:

```powershell
npx --no-install mongodb-mcp-server --readOnly
```

Lucero uses these defaults through environment-configurable settings:

```env
LUCERO_MCP_COMMAND=npx
LUCERO_MCP_ARGS=--no-install,mongodb-mcp-server,--readOnly
```

## 2. ADK Session Not Found

Symptom:

- ADK raises `SessionNotFoundError: Session not found: cli_session`.

Cause:

- The in-memory session service does not create arbitrary session IDs unless the runner is configured to do so.

Current fix:

- Both the CLI runner and FastAPI runner use:

```python
auto_create_session=True
```

## 3. Vertex AI API Not Enabled or Still Propagating

Symptom:

- Gemini call fails with `PERMISSION_DENIED`.
- Immediately after enabling the API, a model call may briefly return `404 NOT_FOUND`.

Cause:

- `aiplatform.googleapis.com` was not enabled, or Google Cloud service activation had not propagated yet.

Current fix:

```powershell
gcloud services enable aiplatform.googleapis.com
```

Wait 1-2 minutes after enabling the API, then retry.

## 4. Sensitive Logging Guardrail

Do not log the full MongoDB connection string. It contains the database username, password, and cluster host. Agent logs should use a redacted form only.
