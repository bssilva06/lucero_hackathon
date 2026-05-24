from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_DIR / ".env"


@dataclass(frozen=True)
class Settings:
    google_cloud_project: str
    google_cloud_location: str
    google_genai_use_vertexai: bool
    mongo_uri: str
    mdb_mcp_connection_string: str
    mongo_db: str
    mongo_chunks_collection: str
    mongo_forms_collection: str
    mongo_visa_bulletins_collection: str
    mongo_query_logs_collection: str
    use_rank_fusion: bool
    use_atlas_automated_embedding: bool
    vector_index: str
    vector_dimensions: int
    fts_index: str
    voyage_api_key: str | None
    voyage_embedding_model: str
    gemini_reasoning_model: str
    gemini_translation_model: str
    mcp_command: str
    mcp_args: list[str]


def load_settings() -> Settings:
    load_dotenv(ENV_PATH)

    return Settings(
        google_cloud_project=_required("GOOGLE_CLOUD_PROJECT"),
        google_cloud_location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        google_genai_use_vertexai=_bool("GOOGLE_GENAI_USE_VERTEXAI", default=True),
        mongo_uri=_required("MONGO_URI"),
        mdb_mcp_connection_string=_required("MDB_MCP_CONNECTION_STRING"),
        mongo_db=os.getenv("MONGO_DB", "lucero"),
        mongo_chunks_collection=os.getenv("MONGO_CHUNKS_COLLECTION", "chunks"),
        mongo_forms_collection=os.getenv("MONGO_FORMS_COLLECTION", "forms"),
        mongo_visa_bulletins_collection=os.getenv(
            "MONGO_VISA_BULLETINS_COLLECTION",
            "visa_bulletins",
        ),
        mongo_query_logs_collection=os.getenv("MONGO_QUERY_LOGS_COLLECTION", "query_logs"),
        use_rank_fusion=_bool("LUCERO_USE_RANK_FUSION", default=True),
        use_atlas_automated_embedding=_bool("LUCERO_USE_ATLAS_AUTOMATED_EMBEDDING", default=False),
        vector_index=os.getenv("LUCERO_VECTOR_INDEX", "vector_autoembed_index"),
        vector_dimensions=_int("LUCERO_VECTOR_DIMENSIONS", default=1024),
        fts_index=os.getenv("LUCERO_FTS_INDEX", "fts_index"),
        voyage_api_key=os.getenv("VOYAGE_API_KEY") or None,
        voyage_embedding_model=os.getenv("VOYAGE_EMBEDDING_MODEL", "voyage-3-large"),
        gemini_reasoning_model=os.getenv("GEMINI_REASONING_MODEL", "gemini-3.5-flash"),
        gemini_translation_model=os.getenv("GEMINI_TRANSLATION_MODEL", "gemini-3.5-flash"),
        mcp_command=os.getenv("LUCERO_MCP_COMMAND", "npx"),
        mcp_args=_csv("LUCERO_MCP_ARGS", ["--no-install", "mongodb-mcp-server", "--readOnly"]),
    )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [part.strip() for part in value.split(",") if part.strip()]


def _int(name: str, *, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Invalid integer environment variable {name}: {value}") from exc


def redact_secret(value: str, *, visible_prefix: int = 12) -> str:
    if not value:
        return "(empty)"
    if len(value) <= visible_prefix:
        return "***"
    return f"{value[:visible_prefix]}..."
