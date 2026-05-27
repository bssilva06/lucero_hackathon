# Evals

Acceptance prompts and evaluation harness for the Lucero MVP.

The MVP must pass at least 8 of 10 PRD acceptance questions before submission, and all refusal canaries must refuse cleanly.

## Running

The eval runner calls the real `/api/chat` endpoint, which may invoke Gemini, MongoDB MCP, Atlas Search, and Google Vertex AI embeddings.

Run one focused case:

```powershell
cd C:\Users\trash\Documents\Lucero
backend\.venv\Scripts\python.exe evals\run_mvp_evals.py --case hardship-evidence --timeout-seconds 90
```

Run a small batch:

```powershell
backend\.venv\Scripts\python.exe evals\run_mvp_evals.py --limit 2 --timeout-seconds 90
```

By default, the eval runner starts a fresh backend server for each case. This is slower, but it keeps one long or timed-out agent turn from affecting later evals.

For faster local experiments, reuse one backend server:

```powershell
backend\.venv\Scripts\python.exe evals\run_mvp_evals.py --limit 2 --timeout-seconds 90 --reuse-server
```

Use `--reuse-server` only when you are comfortable with cascading failures from a stuck case.

The full gate exits successfully only when at least 8 of 10 MVP prompts pass and all refusal canaries pass.
