from __future__ import annotations

import traceback

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.models import ChatRequest, ChatResponse


app = FastAPI(
    title="Simple MVP RAG Chatbot",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://groww-hdfc-faq-frontend.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    return {"message": "Simple MVP RAG chatbot running"}


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "message": "Backend is running",
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    try:
        from retrieval.generator import generate_answer
        from retrieval.query_guard import (
            is_advisory_or_opinion_query,
            refusal_response,
        )
        from retrieval.retriever import retrieve_docs

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

        raise HTTPException(
            status_code=500,
            detail=f"{type(exc).__name__}: {str(exc)}",
        ) from exc


@app.post("/api/query", response_model=ChatResponse)
async def query_alias(body: ChatRequest) -> ChatResponse:
    return await chat(body)