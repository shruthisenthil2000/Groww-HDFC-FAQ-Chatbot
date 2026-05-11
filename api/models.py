from __future__ import annotations

from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    fund_name: str = ""
    groww_url: str = ""
    ingestion_date: str = ""


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation] = Field(default_factory=list)


class UploadResponse(BaseModel):
    filename: str
    chunks_added: int
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"
    llm_model: str
    embedding_model: str
    corpus_chunks: int
    groq_key_set: bool
