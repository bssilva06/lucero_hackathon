from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai.types import Content, Part

from app.agent import create_lucero_agent
from app.config import load_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("lucero.api")


# Lifespan manager to handle setup and cleanup of ADK agent and runner
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Lucero ADK Backend skeleton...")
    try:
        settings = load_settings()
        agent = await create_lucero_agent()
        session_service = InMemorySessionService()

        # Initialize the ADK Runner
        runner = Runner(
            app_name="LuceroResearchCoPilot",
            agent=agent,
            session_service=session_service,
            auto_create_session=True,
        )

        app.state.runner = runner
        logger.info("Lucero ADK Backend fully bootstrapped and ready.")
    except Exception as exc:
        logger.exception("Failed to bootstrap ADK runner:")
        raise RuntimeError(f"Startup bootstrap failed: {exc}") from exc

    yield

    logger.info("Shutting down Lucero ADK Backend...")


app = FastAPI(
    title="Lucero ADK Backend API",
    description="HTTP API for Lucero, the bilingual research co-pilot for immigration legal teams.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for React/Vite development local server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production if necessary
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request and Response schemas
class ChatRequest(BaseModel):
    message: str = Field(..., description="The query/instruction from the user.")
    session_id: str = Field("default_session", description="Unique session identifier for memory.")
    user_id: str = Field("default_user", description="Unique user identifier.")


class ToolTrace(BaseModel):
    name: str = Field(..., description="The name of the tool called.")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments sent to the tool.")
    response: Any = Field(None, description="The response/result returned by the tool.")


class SourceChunk(BaseModel):
    chunk_id: str = Field(..., description="Stable source chunk identifier.")
    section_citation: str | None = Field(None, description="Citation label for the source section.")
    source_url: str | None = Field(None, description="Canonical source URL.")
    text: str = Field(..., description="Retrieved source chunk text.")
    doc_id: str | None = Field(None, description="Source document identifier.")
    doc_type: str | None = Field(None, description="Source document type.")
    agency: str | None = Field(None, description="Issuing agency.")
    jurisdiction: str | None = Field(None, description="Jurisdiction for the source.")
    section_path: list[str] = Field(default_factory=list, description="Hierarchical source path.")
    version_label: str | None = Field(None, description="Source version label.")
    retrieval_date: str | None = Field(None, description="Date the source was retrieved.")
    effective_from: str | None = Field(None, description="Source effective start date.")
    effective_to: str | None = Field(None, description="Source effective end date.")
    content_hash: str | None = Field(None, description="Hash of the source chunk text.")
    score: Any = Field(None, description="Retriever score or score details.")


class ChatResponse(BaseModel):
    response: str = Field(..., description="The final structured synthesized answer from Gemini.")
    tool_calls: list[ToolTrace] = Field(
        default_factory=list,
        description="List of tool executions that happened during this turn.",
    )
    sources: list[SourceChunk] = Field(
        default_factory=list,
        description="Structured retrieved source chunks for citation/source-panel rendering.",
    )


@app.get("/api/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "app": "Lucero ADK Backend"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Processes legal research queries, runs the ADK agent, and traces tool usage."""
    runner: Runner = getattr(app.state, "runner", None)
    if not runner:
        raise HTTPException(status_code=503, detail="Agent Runner is not initialized.")

    logger.info("Received query: %s (session_id: %s)", request.message, request.session_id)

    # Convert standard string input to Google GenAI Content structure required by ADK
    user_message = Content(role="user", parts=[Part.from_text(text=request.message)])

    try:
        # Run agent asynchronously
        events = runner.run_async(
            user_id=request.user_id,
            session_id=request.session_id,
            new_message=user_message,
        )

        final_response_text = ""
        captured_calls: dict[str, ToolTrace] = {}
        captured_sources: list[SourceChunk] = []
        captured_source_ids: set[str] = set()

        async for event in events:
            # Accumulate final response text parts
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_response_text += part.text

            # Retrieve intermediate function calls
            func_calls = event.get_function_calls()
            if func_calls:
                for call in func_calls:
                    # Let's map args (which is a pydantic model or dict)
                    args_dict = {}
                    if call.args:
                        # Some versions of genai types return a dict, others a Pydantic model
                        args_dict = (
                            call.args.model_dump()
                            if hasattr(call.args, "model_dump")
                            else dict(call.args)
                        )

                    logger.info("Agent called tool: %s with args: %s", call.name, args_dict)
                    # Use function call name as the key (or composite if multiple similar calls occur)
                    captured_calls[call.name] = ToolTrace(name=call.name, arguments=args_dict)

            # Retrieve intermediate function responses
            func_responses = event.get_function_responses()
            if func_responses:
                for resp in func_responses:
                    resp_data = None
                    if resp.response:
                        resp_data = (
                            resp.response.model_dump()
                            if hasattr(resp.response, "model_dump")
                            else dict(resp.response)
                        )

                    logger.info("Agent received tool response for: %s", resp.name)
                    if resp.name in captured_calls:
                        captured_calls[resp.name].response = resp_data
                    else:
                        captured_calls[resp.name] = ToolTrace(
                            name=resp.name,
                            arguments={},
                            response=resp_data,
                        )

                    if resp.name == "search_uscis_policy_manual":
                        _append_source_chunks(
                            resp_data,
                            captured_sources=captured_sources,
                            captured_source_ids=captured_source_ids,
                        )

        return ChatResponse(
            response=final_response_text.strip(),
            tool_calls=list(captured_calls.values()),
            sources=captured_sources,
        )

    except Exception as exc:
        logger.exception("Error executing agent run:")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while running the research co-pilot: {exc}",
        ) from exc


def _append_source_chunks(
    tool_response: Any,
    *,
    captured_sources: list[SourceChunk],
    captured_source_ids: set[str],
) -> None:
    if not isinstance(tool_response, dict):
        logger.warning("search_uscis_policy_manual returned non-dict response: %s", type(tool_response))
        return

    results = tool_response.get("results")
    if not isinstance(results, list):
        logger.warning("search_uscis_policy_manual response did not include list results.")
        return

    for result in results:
        source = _source_chunk_from_tool_result(result)
        if not source:
            continue
        if source.chunk_id in captured_source_ids:
            continue
        captured_source_ids.add(source.chunk_id)
        captured_sources.append(source)


def _source_chunk_from_tool_result(result: Any) -> SourceChunk | None:
    if not isinstance(result, dict):
        logger.warning("Skipping malformed source result: %s", type(result))
        return None

    chunk_id = result.get("chunk_id")
    text = result.get("text")
    if not chunk_id or not isinstance(chunk_id, str):
        logger.warning("Skipping source result without chunk_id.")
        return None
    if not isinstance(text, str):
        logger.warning("Skipping source result without text for chunk_id=%s.", chunk_id)
        return None

    section_path = result.get("section_path", [])
    if not isinstance(section_path, list):
        section_path = []

    return SourceChunk(
        chunk_id=chunk_id,
        section_citation=_optional_string(result.get("section_citation")),
        source_url=_optional_string(result.get("source_url")),
        text=text,
        doc_id=_optional_string(result.get("doc_id")),
        doc_type=_optional_string(result.get("doc_type")),
        agency=_optional_string(result.get("agency")),
        jurisdiction=_optional_string(result.get("jurisdiction")),
        section_path=[str(part) for part in section_path],
        version_label=_optional_string(result.get("version_label")),
        retrieval_date=_optional_string(result.get("retrieval_date")),
        effective_from=_optional_string(result.get("effective_from")),
        effective_to=_optional_string(result.get("effective_to")),
        content_hash=_optional_string(result.get("content_hash")),
        score=result.get("score"),
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
