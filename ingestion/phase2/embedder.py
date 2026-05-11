from __future__ import annotations

from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL

_model = SentenceTransformer(EMBEDDING_MODEL)


def embed_chunks(texts: list[str]) -> list[list[float]]:
    vectors = _model.encode(texts)
    return [v.tolist() for v in vectors]