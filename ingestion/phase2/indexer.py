"""
Phase 2.4 — Persist Chunks & Build Vector Index

Two back-ends are available and can be used independently or together:

  ChromaDB  — build_index() / search()
      Stores vectors + metadata in a single persistent directory.
      Preferred for local development and metadata-filtered retrieval.

  FAISS     — build_faiss_index() / search_faiss()
      Stores a binary .faiss index file + a JSON metadata sidecar.
      Preferred for lightweight deployment and raw vector performance.
      Index type: IndexFlatIP on L2-normalised vectors (= cosine similarity).
      Input:  chunks.parquet  (produced by save_parquet())
      Output: data/index/vector.faiss   (FAISS binary)
              data/index/vector.meta.json  (row-index → chunk metadata)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import CHROMA_DIR, CHROMA_COLLECTION, CHUNKS_PARQUET, FAISS_INDEX_PATH, FAISS_META_PATH

logger = logging.getLogger(__name__)


_CHROMA_META_FIELDS = (
    "chunk_id", "fund_id", "fund_name", "groww_url",
    "doc_type", "section_type", "ingestion_date",
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
# PARQUET SAVE
# ─────────────────────────────────────────────────────────────

def save_parquet(chunks: list[dict], path: Path | str | None = None) -> Path:
    _validate_chunks(chunks)

    out_path = Path(path) if path else Path(CHUNKS_PARQUET)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(chunks)

    tmp_path = out_path.with_suffix(".tmp")
    df.to_parquet(tmp_path, engine="pyarrow", index=False)
    tmp_path.rename(out_path)

    logger.info("Parquet saved → %s (%d rows)", out_path, len(df))
    return out_path


# ─────────────────────────────────────────────────────────────
# BUILD CHROMA INDEX
# ─────────────────────────────────────────────────────────────

def build_index(
    chunks: list[dict],
    chroma_dir: Path | str | None = None,
    collection_name: str | None = None,
) -> Any:

    try:
        import chromadb
    except ImportError:
        raise RuntimeError("Install chromadb: pip install chromadb")

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

    BATCH = 500
    for i in range(0, len(chunks), BATCH):
        collection.upsert(
            ids=ids[i:i+BATCH],
            embeddings=embeddings[i:i+BATCH],
            documents=documents[i:i+BATCH],
            metadatas=metadatas[i:i+BATCH],
        )

    logger.info(
        "ChromaDB built → %s | collection=%s | vectors=%d",
        persist_dir, coll_name, len(chunks)
    )

    return collection


# ─────────────────────────────────────────────────────────────
# SEARCH (FIXED: takes TEXT, not embedding)
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

    where = {"section_type": filter_section_type} if filter_section_type else None

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
            results.append({
                "chunk_id": cid,
                "text": doc,
                "score": 1 - dist,
                "distance": dist,
                "fund_id": meta.get("fund_id", ""),
                "fund_name": meta.get("fund_name", ""),
                "groww_url": meta.get("groww_url", ""),
                "section_type": meta.get("section_type", ""),
            })

    return results


# ─────────────────────────────────────────────────────────────
# FAISS — build index from parquet
# ─────────────────────────────────────────────────────────────

#: Metadata fields written to the JSON sidecar alongside the FAISS index.
#: Row position in the sidecar == row position in the FAISS index.
_FAISS_META_FIELDS: tuple[str, ...] = (
    "chunk_id", "fund_id", "fund_name", "groww_url",
    "doc_type", "section_type", "ingestion_date", "text",
)


def build_faiss_index(
    parquet_path: Path | str | None = None,
    faiss_path:   Path | str | None = None,
    meta_path:    Path | str | None = None,
) -> Path:
    """
    Build a FAISS flat cosine-similarity index from the embeddings stored in
    chunks.parquet and persist it to data/index/vector.faiss.

    FAISS stores only numeric vectors — all chunk metadata is saved alongside
    as a JSON sidecar (vector.meta.json) keyed by row position so that search
    results can be hydrated with text and metadata.

    Index type: ``faiss.IndexFlatIP`` on L2-normalised vectors.
    L2-normalising unit vectors makes inner-product == cosine similarity,
    which matches the architecture spec (§2.4: "Index Type: cosine similarity").

    Args:
        parquet_path: Source Parquet file containing an "embedding" column
                      (list[float] per row). Defaults to CHUNKS_PARQUET.
        faiss_path:   Output path for the FAISS binary.
                      Defaults to FAISS_INDEX_PATH  (data/index/vector.faiss).
        meta_path:    Output path for the JSON metadata sidecar.
                      Defaults to FAISS_META_PATH   (data/index/vector.meta.json).

    Returns:
        Absolute Path of the written .faiss file.

    Raises:
        FileNotFoundError: parquet_path does not exist.
        ValueError:        "embedding" column is absent or contains wrong-dim vectors.
        RuntimeError:      faiss package is not installed.
    """
    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError(
            "faiss-cpu is not installed. Run: pip install faiss-cpu"
        ) from exc

    src  = Path(parquet_path) if parquet_path else Path(CHUNKS_PARQUET)
    dst  = Path(faiss_path)   if faiss_path   else Path(FAISS_INDEX_PATH)
    meta = Path(meta_path)    if meta_path    else Path(FAISS_META_PATH)

    if not src.exists():
        raise FileNotFoundError(
            f"Parquet source not found: {src}\n"
            "Run save_parquet() (Phase 2.4a) before building the FAISS index."
        )

    # ── Load parquet ──────────────────────────────────────────
    df = pd.read_parquet(src)

    if "embedding" not in df.columns:
        raise ValueError(
            f"'embedding' column not found in {src}. "
            "Re-run embed_chunks() to add embeddings to the parquet file."
        )

    # ── Build float32 matrix ──────────────────────────────────
    vectors: np.ndarray = np.array(df["embedding"].tolist(), dtype=np.float32)

    if vectors.ndim != 2:
        raise ValueError(
            f"Expected a 2-D embedding matrix, got shape {vectors.shape}."
        )

    n_vectors, dim = vectors.shape
    logger.info(
        "Building FAISS index  n=%d  dim=%d  source=%s",
        n_vectors, dim, src,
    )

    # ── L2-normalise → cosine similarity via inner product ────
    faiss.normalize_L2(vectors)

    # IndexFlatIP: exact brute-force inner-product (cosine on unit vectors)
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    # ── Write FAISS binary (atomic: tmp → rename) ─────────────
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp_faiss = dst.with_suffix(".faiss.tmp")
    faiss.write_index(index, str(tmp_faiss))
    tmp_faiss.rename(dst)

    # ── Write JSON metadata sidecar ───────────────────────────
    # Row i in the sidecar corresponds to row i in the FAISS index.
    meta_records: list[dict] = []
    for _, row in df.iterrows():
        meta_records.append(
            {k: row.get(k, "") for k in _FAISS_META_FIELDS}
        )

    meta.parent.mkdir(parents=True, exist_ok=True)
    tmp_meta = meta.with_suffix(".meta.tmp")
    tmp_meta.write_text(
        json.dumps(meta_records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_meta.rename(meta)

    logger.info(
        "  ✔  FAISS index saved   → %s  (%d vectors  dim=%d)",
        dst, n_vectors, dim,
    )
    logger.info(
        "  ✔  Metadata sidecar    → %s  (%d entries)",
        meta, len(meta_records),
    )
    return dst


def search_faiss(
    query_embedding: list[float],
    top_k: int = 5,
    filter_section_type: str | None = None,
    faiss_path: Path | str | None = None,
    meta_path:  Path | str | None = None,
) -> list[dict]:
    """
    Query the persisted FAISS index.

    The query vector is L2-normalised before search so that the inner-product
    scores equal cosine similarity (consistent with how the index was built).

    Args:
        query_embedding:     Query vector. Must have the same dimension as the
                             indexed embeddings.
        top_k:               Number of nearest neighbours to return.
        filter_section_type: If set, post-filter results to only this
                             section_type (e.g. "fund_overview").
                             Because FAISS has no native metadata filtering,
                             this over-fetches (top_k * 4) and post-filters.
        faiss_path:          Path to the .faiss binary. Defaults to FAISS_INDEX_PATH.
        meta_path:           Path to the metadata sidecar. Defaults to FAISS_META_PATH.

    Returns:
        list of result dicts, each with:
            chunk_id, fund_id, fund_name, groww_url, section_type,
            text, score (cosine similarity, higher = more similar).
    """
    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError(
            "faiss-cpu is not installed. Run: pip install faiss-cpu"
        ) from exc

    idx_path  = Path(faiss_path) if faiss_path else Path(FAISS_INDEX_PATH)
    side_path = Path(meta_path)  if meta_path  else Path(FAISS_META_PATH)

    if not idx_path.exists():
        raise FileNotFoundError(
            f"FAISS index not found: {idx_path}\n"
            "Run build_faiss_index() first."
        )
    if not side_path.exists():
        raise FileNotFoundError(
            f"FAISS metadata sidecar not found: {side_path}\n"
            "Run build_faiss_index() first."
        )

    index    = faiss.read_index(str(idx_path))
    sidecar: list[dict] = json.loads(side_path.read_text(encoding="utf-8"))

    # L2-normalise the query vector (same transform applied at index time)
    qvec = np.array([query_embedding], dtype=np.float32)
    faiss.normalize_L2(qvec)

    # When section filtering: fetch the entire index so we never miss a
    # relevant chunk due to an arbitrary multiplier.  At 85 chunks this is
    # instantaneous; scale the approach if the corpus grows significantly.
    fetch_k = index.ntotal if filter_section_type else top_k
    scores, indices = index.search(qvec, fetch_k)

    results: list[dict] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:           # FAISS returns -1 for padded slots
            continue
        meta = sidecar[idx]
        if filter_section_type and meta.get("section_type") != filter_section_type:
            continue
        results.append({
            "chunk_id":       meta.get("chunk_id", ""),
            "fund_id":        meta.get("fund_id", ""),
            "fund_name":      meta.get("fund_name", ""),
            "groww_url":      meta.get("groww_url", ""),
            "section_type":   meta.get("section_type", ""),
            "ingestion_date": meta.get("ingestion_date", ""),
            "text":           meta.get("text", ""),
            "score":          float(score),
        })
        if len(results) == top_k:
            break

    return results
