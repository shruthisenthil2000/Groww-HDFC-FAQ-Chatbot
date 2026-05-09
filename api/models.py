"""
Pydantic request / response models for the FAQ Assistant API.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ── Request ─────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="User's natural-language question about an HDFC mutual fund.",
        examples=["What is the exit load for HDFC Mid Cap Fund?"],
    )


# ── Source citation ──────────────────────────────────────────────────────────────

class SourceCitation(BaseModel):
    fund_name:      str
    groww_url:      str
    ingestion_date: str = ""


# ── Query response ───────────────────────────────────────────────────────────────

class QueryResponse(BaseModel):
    response:       str   = Field(description="Final answer or refusal text.")
    answered:       bool  = Field(description="True when a factual answer was found.")
    refused:        bool  = Field(description="True when the query was refused.")
    refused_reason: Optional[str] = Field(
        None,
        description="Reason for refusal: pii | advisory | out_of_scope | ambiguous | no_answer",
    )
    intent:         str   = Field(description="Classified intent of the query.")
    sources:        list[SourceCitation] = Field(
        default_factory=list,
        description="Source citations. Empty when refused or no answer found.",
    )
    fund_id:        Optional[str] = Field(None, description="Router-detected fund ID.")
    section_type:   Optional[str] = Field(None, description="Router-detected section type.")
    latency_s:      float = Field(description="End-to-end latency in seconds.")


# ── Health check ─────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:          str   = "ok"
    llm_provider:    str
    llm_model:       str
    embedding_model: str
    corpus_chunks:   int
    groq_key_set:    bool


# ── Fund list ────────────────────────────────────────────────────────────────────

class FundInfo(BaseModel):
    fund_id:   str
    fund_name: str
    category:  str
    groww_url: str


class FundListResponse(BaseModel):
    total:  int
    funds:  list[FundInfo]


# ── Example questions ────────────────────────────────────────────────────────────

class ExamplesResponse(BaseModel):
    examples: list[str]
