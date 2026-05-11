from __future__ import annotations

from sentence_transformers import SentenceTransformer

from config import EMBEDDING_DIM, EMBEDDING_MODEL

_model = SentenceTransformer(EMBEDDING_MODEL)


def embed_chunks(chunks: list[dict]) -> list[dict]:
    if not chunks:
        return chunks
    texts = [c.get("text", "") for c in chunks]
    vectors = _model.encode(texts, normalize_embeddings=True)
    for chunk, vec in zip(chunks, vectors):
        vector = vec.tolist()
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(
                f"Wrong embedding dimension {len(vector)} != {EMBEDDING_DIM}"
            )
        chunk["embedding"] = vector
    return chunks
