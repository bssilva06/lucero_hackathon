# Lucero

Bilingual research co-pilot for immigration legal teams, focused on I-601A provisional unlawful presence waivers and Ciudad Juarez consular processing.

Lucero is designed as a citation-first AI research tool for licensed immigration practitioners. It retrieves primary-source immigration authority from MongoDB Atlas, uses Google ADK and Gemini to synthesize answers, and presents every factual claim with source metadata.

## MVP Stack

- Backend: Python, Google Agent Development Kit, Gemini
- Database: MongoDB Atlas
- Retrieval: Google Vertex AI embeddings in MongoDB Atlas, `$rankFusion` when available, `$vectorSearch` fallback
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

This repository is currently in Phase 0 bootstrap. Implementation begins with:

1. Configure local environment variables from `.env.example`.
2. Scaffold the ADK backend in `backend/`.
3. Smoke test MongoDB Atlas, Atlas Automated Embedding, `$rankFusion`, and MongoDB MCP.
4. Build the MVP ingestion pipeline for the minimum source corpus.
5. Add the React dual-pane research UI.

## Safety Posture

Lucero is not legal advice and is not a consumer immigration guide. It is a research and drafting aid for licensed immigration practitioners. Outputs must be verified against retrieved source authority before use in a client matter.

## License

Apache-2.0.
