from __future__ import annotations

import json
import traceback
import uuid
from pathlib import Path

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile

from api.models import ChatRequest, ChatResponse, UploadResponse
from config import EMBEDDING_DIM, FAISS_INDEX_PATH, FAISS_META_PATH
from retrieval.generator import generate_answer
from retrieval.query_guard import is_advisory_or_opinion_query, refusal_response
from retrieval.retriever import embed_texts, retrieve_docs

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    try:
        if is_advisory_or_opinion_query(body.query):
            result = refusal_response()
        else:
            chunks = retrieve_docs(body.query)
            result = generate_answer(body.query, chunks)

        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
        )

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/query", response_model=ChatResponse)
async def query_alias(body: ChatRequest) -> ChatResponse:
    return await chat(body)


def _split_text(text: str, chunk_words: int = 220, overlap: int = 40) -> list[str]:
    words = text.split()

    if not words:
        return []

    out: list[str] = []
    i = 0
    step = max(1, chunk_words - overlap)

    while i < len(words):
        out.append(" ".join(words[i : i + chunk_words]).strip())
        i += step

    return [x for x in out if x]


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    raw = await file.read()
    text = raw.decode("utf-8", errors="ignore").strip()

    chunks = _split_text(text)

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file has no readable text",
        )

    vectors = embed_texts(chunks)

    try:
        import faiss
    except ImportError as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="faiss-cpu not installed",
        ) from exc

    idx_path = Path(FAISS_INDEX_PATH)
    meta_path = Path(FAISS_META_PATH)

    idx_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    if idx_path.exists():
        index = faiss.read_index(str(idx_path))
    else:
        index = faiss.IndexFlatIP(EMBEDDING_DIM)

    arr = np.array(vectors, dtype=np.float32)

    faiss.normalize_L2(arr)

    index.add(arr)

    faiss.write_index(index, str(idx_path))

    meta = []

    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    doc_id = uuid.uuid4().hex[:10]

    for i, chunk in enumerate(chunks):
        meta.append(
            {
                "chunk_id": f"upload_{doc_id}_{i}",
                "fund_id": "uploaded_document",
                "fund_name": file.filename or "Uploaded Document",
                "groww_url": "",
                "section_type": "uploaded_doc",
                "ingestion_date": "",
                "text": chunk,
            }
        )

    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return UploadResponse(
        filename=file.filename or "uploaded_file",
        chunks_added=len(chunks),
        message="Document ingested into vector index",
    )