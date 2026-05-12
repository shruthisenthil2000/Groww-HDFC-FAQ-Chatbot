"""
Phase 2.4 — Persist Chunks & Build Vector Index
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import (
    CHROMA_COLLECTION,
    CHROMA_DIR,
    CHUNKS_PARQUET,
    FAISS_INDEX_PATH,
    FAISS_META_PATH,
)

logger = logging.getLogger(__name__)

_CHROMA_META_FIELDS = (
    "chunk_id",
    "fund_id",
    "fund_name",
    "groww_url",
    "doc_type",
    "section_type",
    "ingestion_date",
)

_FAISS_META_FIELDS = (
    "chunk_id",
    "fund_id",
    "fund_name",
    "groww_url",
    "doc_type",
    "section_type",
    "ingestion_date",
    "text",
)


# ─────────────────────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────────────────────

def _validate_chunks(chunks: list[dict]) -> None:
    required = {"chunk_id", "text", "embedding"}

    errors = []

    for i, chunk in enumerate(chunks):
        missing = required - set(chunk.keys())

        if missing:
            errors.append(f"Chunk[{i}] missing {missing}")
            continue

        if not chunk["text"].strip():
            errors.append(f"Chunk[{i}] empty text")

        emb = chunk["embedding"]

        if not isinstance(emb, list) or len(emb) == 0:
            errors.append(f"Chunk[{i}] invalid embedding")

    if errors:
        raise ValueError("\n".join(errors))


# ─────────────────────────────────────────────────────────────
# SAVE PARQUET
# ─────────────────────────────────────────────────────────────

def save_parquet(
    chunks: list[dict],
    path: Path | str | None = None,
) -> Path:

    _validate_chunks(chunks)

    out_path = Path(path) if path else Path(CHUNKS_PARQUET)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(chunks)

    df.to_parquet(out_path, engine="pyarrow", index=False)

    logger.info("Saved parquet → %s", out_path)

    return out_path


# ─────────────────────────────────────────────────────────────
# BUILD CHROMA
# ─────────────────────────────────────────────────────────────

def build_index(
    chunks: list[dict],
    chroma_dir: Path | str | None = None,
    collection_name: str | None = None,
) -> Any:

    try:
        import chromadb
    except ImportError:
        raise RuntimeError("Install chromadb")

    _validate_chunks(chunks)

    persist_dir = str(chroma_dir) if chroma_dir else CHROMA_DIR
    coll_name = collection_name or CHROMA_COLLECTION

    Path(persist_dir).mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=persist_dir)

    collection = client.get_or_create_collection(
        name=coll_name,
        metadata={"hnsw:space": "cosine"},
    )

    ids = [c["chunk_id"] for c in chunks]
    embeddings = [c["embedding"] for c in chunks]
    documents = [c["text"] for c in chunks]

    metadatas = [
        {k: c.get(k, "") for k in _CHROMA_META_FIELDS}
        for c in chunks
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    logger.info("Chroma index built")

    return collection


# ─────────────────────────────────────────────────────────────
# SEARCH CHROMA
# ─────────────────────────────────────────────────────────────

def search(
    query_embedding: list[float],
    top_k: int = 5,
    filter_section_type: str | None = None,
    chroma_dir: Path | str | None = None,
    collection_name: str | None = None,
) -> list[dict]:

    try:
        import chromadb
    except ImportError:
        raise RuntimeError("Missing chromadb")

    persist_dir = str(chroma_dir) if chroma_dir else CHROMA_DIR
    coll_name = collection_name or CHROMA_COLLECTION

    client = chromadb.PersistentClient(path=persist_dir)

    collection = client.get_or_create_collection(
        name=coll_name,
        metadata={"hnsw:space": "cosine"},
    )

    where = (
        {"section_type": filter_section_type}
        if filter_section_type
        else None
    )

    raw = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    results = []

    if raw["ids"] and raw["ids"][0]:
        for cid, doc, meta, dist in zip(
            raw["ids"][0],
            raw["documents"][0],
            raw["metadatas"][0],
            raw["distances"][0],
        ):
            results.append(
                {
                    "chunk_id": cid,
                    "text": doc,
                    "score": 1 - dist,
                    "distance": dist,
                    "fund_id": meta.get("fund_id", ""),
                    "fund_name": meta.get("fund_name", ""),
                    "groww_url": meta.get("groww_url", ""),
                    "section_type": meta.get("section_type", ""),
                }
            )

    return results


# ─────────────────────────────────────────────────────────────
# BUILD FAISS INDEX
# ─────────────────────────────────────────────────────────────

def build_faiss_index(
    parquet_path: Path | str | None = None,
    faiss_path: Path | str | None = None,
    meta_path: Path | str | None = None,
) -> Path:

    try:
        import faiss
    except ImportError:
        raise RuntimeError("Install faiss-cpu")

    src = Path(parquet_path) if parquet_path else Path(CHUNKS_PARQUET)

    dst = Path(faiss_path) if faiss_path else Path(FAISS_INDEX_PATH)

    meta = Path(meta_path) if meta_path else Path(FAISS_META_PATH)

    if not src.exists():
        raise FileNotFoundError(
            f"Parquet source not found: {src}"
        )

    print("Loading parquet...")

    df = pd.read_parquet(src)

    if "embedding" not in df.columns:
        raise ValueError("embedding column missing")

    vectors = np.array(
        df["embedding"].tolist(),
        dtype=np.float32,
    )

    if vectors.ndim != 2:
        raise ValueError(
            f"Expected 2D vectors got {vectors.shape}"
        )

    n_vectors, dim = vectors.shape

    print(f"Vectors: {n_vectors}")
    print(f"Dimension: {dim}")

    faiss.normalize_L2(vectors)

    index = faiss.IndexFlatIP(dim)

    index.add(vectors)

    dst.parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(dst))

    meta_records = []

    for _, row in df.iterrows():
        meta_records.append(
            {
                k: row.get(k, "")
                for k in _FAISS_META_FIELDS
            }
        )

    meta.parent.mkdir(parents=True, exist_ok=True)

    meta.write_text(
        json.dumps(meta_records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved FAISS index → {dst}")
    print(f"Saved metadata → {meta}")

    return dst


# ─────────────────────────────────────────────────────────────
# SEARCH FAISS
# ─────────────────────────────────────────────────────────────

def search_faiss(
    query_embedding: list[float],
    top_k: int = 5,
    filter_section_type: str | None = None,
    faiss_path: Path | str | None = None,
    meta_path: Path | str | None = None,
) -> list[dict]:

    try:
        import faiss
    except ImportError:
        raise RuntimeError("Install faiss-cpu")

    idx_path = (
        Path(faiss_path)
        if faiss_path
        else Path(FAISS_INDEX_PATH)
    )

    side_path = (
        Path(meta_path)
        if meta_path
        else Path(FAISS_META_PATH)
    )

    if not idx_path.exists():
        raise FileNotFoundError(
            f"FAISS index not found: {idx_path}"
        )

    if not side_path.exists():
        raise FileNotFoundError(
            f"FAISS metadata not found: {side_path}"
        )

    index = faiss.read_index(str(idx_path))

    sidecar = json.loads(
        side_path.read_text(encoding="utf-8")
    )

    qvec = np.array(
        [query_embedding],
        dtype=np.float32,
    )

    faiss.normalize_L2(qvec)

    fetch_k = (
        index.ntotal
        if filter_section_type
        else top_k
    )

    scores, indices = index.search(qvec, fetch_k)

    results = []

    for score, idx in zip(scores[0], indices[0]):

        if idx == -1:
            continue

        meta = sidecar[idx]

        if (
            filter_section_type
            and meta.get("section_type") != filter_section_type
        ):
            continue

        results.append(
            {
                "chunk_id": meta.get("chunk_id", ""),
                "fund_id": meta.get("fund_id", ""),
                "fund_name": meta.get("fund_name", ""),
                "groww_url": meta.get("groww_url", ""),
                "section_type": meta.get("section_type", ""),
                "ingestion_date": meta.get("ingestion_date", ""),
                "text": meta.get("text", ""),
                "score": float(score),
            }
        )

        if len(results) == top_k:
            break

    return results


# ─────────────────────────────────────────────────────────────
# RUN DIRECTLY
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("Building FAISS index...")

    build_faiss_index()

    print("FAISS build complete.")