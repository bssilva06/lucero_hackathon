from __future__ import annotations

from app.config import load_settings


def main() -> int:
    settings = load_settings()

    checks = {
        "GOOGLE_CLOUD_PROJECT": bool(settings.google_cloud_project),
        "GOOGLE_CLOUD_LOCATION": bool(settings.google_cloud_location),
        "GOOGLE_GENAI_USE_VERTEXAI": settings.google_genai_use_vertexai,
        "MONGO_URI": bool(settings.mongo_uri),
        "MDB_MCP_CONNECTION_STRING": bool(settings.mdb_mcp_connection_string),
        "MONGO_DB": bool(settings.mongo_db),
        "LUCERO_VECTOR_INDEX": bool(settings.vector_index),
        "LUCERO_FTS_INDEX": bool(settings.fts_index),
    }

    print("Lucero Phase 1 environment smoke test")
    print("--------------------------------------")
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'} {name}")

    print()
    print(f"MongoDB database: {settings.mongo_db}")
    print(f"Rank fusion requested: {settings.use_rank_fusion}")
    print(f"Atlas automated embedding requested: {settings.use_atlas_automated_embedding}")
    print(f"Google embedding model: {settings.google_embedding_model}")

    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
