# Backend

Python backend for the Lucero ADK agent, HTTP API, tool implementations, MongoDB MCP integration, and backend tests.

## Planned Components

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
