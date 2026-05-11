from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer

_vectorizer = TfidfVectorizer(max_features=384)


def embed_chunks(texts: list[str]) -> list[list[float]]:
    vectors = _vectorizer.fit_transform(texts).toarray()
    return [v.tolist() for v in vectors]