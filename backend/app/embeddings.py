from __future__ import annotations

import time


DEFAULT_EMBEDDING_BATCH_SIZE = 64
DEFAULT_MAX_RETRIES = 4
GOOGLE_DOCUMENT_TASK_TYPE = "RETRIEVAL_DOCUMENT"
GOOGLE_QUERY_TASK_TYPE = "RETRIEVAL_QUERY"


def embed_texts(
    texts: list[str],
    *,
    project_id: str,
    location: str,
    model: str,
    input_type: str,
    output_dimensionality: int | None = None,
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    request_delay_seconds: float = 0,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> list[list[float]]:
    import vertexai
    from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

    if not texts:
        return []

    task_type = _task_type(input_type)
    vertexai.init(project=project_id, location=location)
    embedding_model = TextEmbeddingModel.from_pretrained(model)
    kwargs = (
        {"output_dimensionality": output_dimensionality}
        if output_dimensionality is not None
        else {}
    )
    embeddings: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        # gemini-embedding-001 accepts one input per request; keep this loop model-safe.
        for text in batch:
            embedding_input = TextEmbeddingInput(str(text), task_type)
            response = _get_embedding_with_retry(
                embedding_model,
                embedding_input,
                kwargs=kwargs,
                max_retries=max_retries,
            )
            embeddings.append(list(response[0].values))
            if request_delay_seconds > 0:
                time.sleep(request_delay_seconds)

    return embeddings


def _task_type(input_type: str) -> str:
    normalized = input_type.strip().lower()
    if normalized in {"document", "retrieval_document", "corpus"}:
        return GOOGLE_DOCUMENT_TASK_TYPE
    if normalized in {"query", "retrieval_query", "search_query"}:
        return GOOGLE_QUERY_TASK_TYPE
    raise ValueError(f"Unsupported embedding input_type: {input_type}")


def _get_embedding_with_retry(
    embedding_model: object,
    embedding_input: object,
    *,
    kwargs: dict[str, int],
    max_retries: int,
) -> object:
    for attempt in range(max_retries + 1):
        try:
            return embedding_model.get_embeddings([embedding_input], **kwargs)
        except Exception as exc:
            if not _is_quota_error(exc) or attempt >= max_retries:
                raise
            time.sleep(min(2**attempt * 10, 60))
    raise RuntimeError("unreachable")


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "429" in message or "quota" in message or "resource exhausted" in message
