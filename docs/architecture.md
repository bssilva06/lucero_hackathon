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

- Google Vertex AI `gemini-embedding-001` embeddings stored in MongoDB Atlas.
- `$rankFusion` combining vector search and Atlas Search BM25.
- MongoDB MCP `aggregate` visible in traces.

Fallback path:

- Google Vertex AI embeddings with pure `$vectorSearch`.
- Atlas Search keyword retrieval through MongoDB MCP for demo continuity if vector retrieval is unavailable.
