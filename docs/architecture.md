# Architecture Notes

Lucero's intended MVP flow:

```text
React frontend
  -> Cloud Run API
  -> Google ADK agent with Gemini
  -> Function tools and MongoDB MCP toolset
  -> MongoDB Atlas source collections and vector search
  -> cited structured answer back to UI
```

## Retrieval Path

Primary path:

- Atlas Automated Embedding with managed Voyage.
- `$rankFusion` combining vector search and Atlas Search BM25.
- MongoDB MCP `aggregate` visible in traces.

Fallback path:

- Atlas Automated Embedding with pure `$vectorSearch`.
- If automated embedding is unavailable, client-side Voyage embeddings with PyMongo retrieval while preserving MongoDB MCP usage for schema, indexes, and logging traces.
