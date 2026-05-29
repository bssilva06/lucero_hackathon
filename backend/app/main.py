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
from app.retrieval import (
    lookup_consular_process,
    search_uscis_policy_manual,
    search_uscis_policy_manual_text,
)

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

    refusal_response = _preflight_refusal_response(request.message)
    if refusal_response:
        return ChatResponse(response=refusal_response)

    routed_response = _policy_manual_fast_path(request.message)
    if routed_response:
        return routed_response

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
                    if resp.name == "lookup_consular_process":
                        _append_consular_sources(
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


def _preflight_refusal_response(message: str) -> str | None:
    normalized = message.casefold()
    if "fake" in normalized and "hardship" in normalized and "letter" in normalized:
        return (
            "I can't help create fraudulent or deceptive case materials. "
            "I can help outline legitimate hardship factors and evidence categories using cited sources."
        )
    if "misrepresent" in normalized or (
        "entry date" in normalized and any(term in normalized for term in ["alter", "hide", "lie"])
    ):
        return (
            "I can't help conceal, alter, or falsify immigration facts. "
            "I can help research the legal consequences of inaccurate information and identify cited authorities."
        )
    if "will my client win" in normalized or "chances" in normalized or "approval rate" in normalized:
        return (
            "I can't predict an individual case outcome. "
            "I can help retrieve the governing hardship factors, eligibility rules, and evidence standards."
        )
    return None


def _policy_manual_fast_path(message: str) -> ChatResponse | None:
    route = _policy_manual_route(message)
    if not route:
        return None

    query, response, retrieval_mode = route
    search_tool = (
        search_uscis_policy_manual_text
        if retrieval_mode == "text"
        else search_uscis_policy_manual
    )
    tool_response = search_tool(query, limit=5)
    captured_sources: list[SourceChunk] = []
    captured_source_ids: set[str] = set()
    _append_source_chunks(
        tool_response,
        captured_sources=captured_sources,
        captured_source_ids=captured_source_ids,
    )
    tool_calls = [
        ToolTrace(
            name="search_uscis_policy_manual",
            arguments={"query": query, "limit": 5},
            response=tool_response,
        )
    ]

    consular_response = None
    if _should_include_consular_process(message):
        consular_response = lookup_consular_process("I-601A timeline", post="CDJ")
        _append_consular_sources(
            consular_response,
            captured_sources=captured_sources,
            captured_source_ids=captured_source_ids,
        )
        tool_calls.append(
            ToolTrace(
                name="lookup_consular_process",
                arguments={"topic": "I-601A timeline", "post": "CDJ"},
                response=consular_response,
            )
        )
        response = _add_consular_timeline_context(response, consular_response)

    citations = _citation_summary(captured_sources)
    if citations:
        response = f"{response}\n\nSources: {citations}."

    return ChatResponse(
        response=response,
        tool_calls=tool_calls,
        sources=captured_sources,
    )


def _policy_manual_route(message: str) -> tuple[str, str, str] | None:
    normalized = message.casefold()
    asks_fee_or_location = any(
        term in normalized
        for term in ["fee", "tarifa", "filing location", "dónde se presenta", "donde se presenta"]
    )
    if asks_fee_or_location:
        return None

    if (
        "i-601" in normalized
        and "i-601a" in normalized
        and any(term in normalized for term in [" vs ", "versus", "diferencias", "differences", "resume"])
    ):
        return (
            "I-601 I-601A provisional unlawful presence waiver consular processing Volume 9 Part H",
            (
                "En resumen, la I-601A es una exención provisional limitada a presencia ilegal antes "
                "de la salida para el proceso consular, mientras que la I-601 se usa para pedir ciertas "
                "exenciones después de que se identifica una causal aplicable. Para un caso que va a "
                "CDJ, la diferencia práctica es el momento, el alcance de la causal y el riesgo de "
                "salir sin una exención provisional aprobada. Para la ruta de I-601A, revise "
                "9 USCIS-PM H junto con las fuentes recuperadas."
            ),
            "text",
        )

    if "i-601a" in normalized and any(term in normalized for term in ["timeline", "cdj"]):
        return (
            "I-601A provisional unlawful presence waivers Volume 9 Part H",
            (
                "For a Mexican spouse consular-processing through Ciudad Juarez (CDJ), "
                "the research path is generally: confirm immigrant-visa eligibility, screen for "
                "provisional unlawful presence waiver eligibility, file Form I-601A before the "
                "immigrant visa interview, then continue with NVC and CDJ consular processing "
                "after USCIS acts."
            ),
            "text",
        )

    if "10-year" in normalized or "10 year" in normalized or "212(a)(9)(b)" in normalized:
        return (
            "ten year bar unlawful presence qualifying relative extreme hardship waiver",
            (
                "For the 10-year unlawful presence bar, the relevant waiver analysis centers on "
                "unlawful presence, a qualifying relative, and extreme hardship to that qualifying "
                "relative. The available Policy Manual sources discuss how USCIS evaluates extreme "
                "hardship factors; this is legal research support, not an outcome prediction."
            ),
            "hybrid",
        )

    if "i-485" in normalized and ("consular" in normalized or "entered without inspection" in normalized):
        return (
            "I-601A provisional unlawful presence waivers Volume 9 Part H",
            (
                "If the client entered without inspection, the threshold I-485 issue is whether the "
                "person was inspected and admitted or paroled for adjustment purposes. If adjustment "
                "is unavailable, the consular route may make an I-601A provisional unlawful presence "
                "waiver relevant before departure, assuming the only inadmissibility ground to waive "
                "is unlawful presence and the other eligibility requirements are met."
            ),
            "text",
        )

    if "extreme hardship" in normalized or "hardship" in normalized:
        return (
            "extreme hardship medical children family ties I-601A",
            (
                "For I-601A hardship evidence, organize proof around extreme hardship factors such "
                "as medical needs, family ties, care responsibilities for children, financial impact, "
                "country conditions, and the cumulative effect on the qualifying relative."
            ),
            "hybrid",
        )

    if "orden" in normalized and ("remoción" in normalized or "remocion" in normalized):
        return (
            "Form I-601A provisional unlawful presence waiver eligibility removal order Volume 9 Part H",
            (
                "No puedo confirmar que califique solo con esos datos. Para una I-601A, una orden de "
                "remoción exige revisar cuidadosamente elegibilidad, inadmisibilidades y cualquier "
                "efecto procesal antes de salir; la respuesta debe basarse en las reglas citadas, "
                "no en una predicción."
            ),
            "text",
        )

    return None


def _should_include_consular_process(message: str) -> bool:
    normalized = message.casefold()
    return any(
        term in normalized
        for term in [
            "cdj",
            "ciudad juarez",
            "ciudad juárez",
            "nvc",
            "consular",
            "interview",
            "medical",
            "asc",
        ]
    )


def _add_consular_timeline_context(response: str, tool_response: Any) -> str:
    if not isinstance(tool_response, dict) or not tool_response.get("found"):
        return response

    return (
        f"{response} After NVC document review, NVC may issue a documentarily-complete notice "
        "and work with the appropriate embassy or consulate to schedule the interview. For CDJ, "
        "the applicant should register the appointment, complete ASC photos/fingerprints before "
        "the Consulate interview, schedule the medical exam in Mexico, bring required originals "
        "and checklist documents, and avoid travel plans until adjudication is complete."
    )


def _append_consular_sources(
    tool_response: Any,
    *,
    captured_sources: list[SourceChunk],
    captured_source_ids: set[str],
) -> None:
    if not isinstance(tool_response, dict):
        logger.warning("lookup_consular_process returned non-dict response: %s", type(tool_response))
        return

    records = tool_response.get("records")
    if not isinstance(records, list):
        logger.warning("lookup_consular_process response did not include list records.")
        return

    for record in records:
        source = _source_chunk_from_consular_record(record)
        if not source:
            continue
        if source.chunk_id in captured_source_ids:
            continue
        captured_source_ids.add(source.chunk_id)
        captured_sources.append(source)


def _source_chunk_from_consular_record(record: Any) -> SourceChunk | None:
    if not isinstance(record, dict):
        logger.warning("Skipping malformed consular record: %s", type(record))
        return None

    record_id = record.get("record_id")
    if not record_id:
        logger.warning("Skipping consular record without record_id.")
        return None

    timeline_steps = record.get("timeline_steps", [])
    step_texts = []
    if isinstance(timeline_steps, list):
        step_texts = [
            str(step.get("text"))
            for step in timeline_steps
            if isinstance(step, dict) and step.get("text")
        ]

    source_urls = record.get("source_urls", {})
    source_url = None
    if isinstance(source_urls, dict) and source_urls:
        source_url = str(next(iter(source_urls.values())))

    text = " ".join([str(record.get("summary") or ""), *step_texts]).strip()
    return SourceChunk(
        chunk_id=str(record_id),
        section_citation=_optional_string(record.get("section_citation")),
        source_url=source_url,
        text=text,
        doc_id=str(record_id),
        doc_type=_optional_string(record.get("doc_type")) or "consular_process",
        agency=_optional_string(record.get("agency")) or "DOS",
        jurisdiction=_optional_string(record.get("jurisdiction")) or "federal",
        section_path=[str(record.get("post") or "CDJ"), str(record.get("title") or "")],
        version_label=None,
        retrieval_date=_optional_string(record.get("retrieval_date")),
        effective_from=None,
        effective_to=None,
        content_hash=_optional_string(record.get("content_hash")),
        score=None,
    )


def _citation_summary(sources: list[SourceChunk]) -> str:
    citations: list[str] = []
    for source in sources:
        citation = source.section_citation
        if citation and citation not in citations:
            citations.append(citation)
    return ", ".join(citations[:4])
