from __future__ import annotations

from typing import Any


DEFAULT_EMBEDDING_BATCH_SIZE = 64


def embed_texts(
    texts: list[str],
    *,
    api_key: str,
    model: str,
    input_type: str,
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
) -> list[list[float]]:
    import voyageai

    client = voyageai.Client(api_key=api_key)
    embeddings: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.embed(batch, model=model, input_type=input_type)
        embeddings.extend(_extract_embeddings(response))

    return embeddings


def _extract_embeddings(response: Any) -> list[list[float]]:
    embeddings = getattr(response, "embeddings", None)
    if embeddings is not None:
        return [list(embedding) for embedding in embeddings]

    if isinstance(response, dict) and "embeddings" in response:
        return [list(embedding) for embedding in response["embeddings"]]

    raise TypeError(f"Unexpected Voyage embedding response: {type(response).__name__}")
