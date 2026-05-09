"""
Phase 3 + 4 — End-to-End RAG Pipeline Orchestrator

Flow per query:
  1. PII check   — refuse immediately if personal data detected (no retrieval)
  2. Route       — extract (fund_id, section_type) anchors from the query
  3. Retrieve    — two-stage FAISS search filtered by anchors
  4. Generate    — LLM generation (or retrieval-only fallback if no API key)
  5. Postprocess — enforce URL-attachment policy, sentence limit, citation
"""

from __future__ import annotations

import logging
import time

import config  # loads .env at import time
from config import RETRIEVER_TOP_K
from retrieval.retriever import retrieve
from retrieval.router import route
from retrieval.generator import generate
from retrieval.postprocessor import postprocess, check_pii
from orchestrator.classifier import classify, INTENT_FACTUAL
from orchestrator.refusal_handler import get_refusal

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Pipeline:

    def __init__(self):
        logger.info("Pipeline initialized (model=%s)", config.LLM_MODEL)

    def run(self, query: str) -> dict:
        """
        Run the full RAG pipeline for a single query.

        Returns a dict with:
            response:       str   — final formatted answer for the user
            refused:        bool  — True when the query was refused
            refused_reason: str | None — "pii" | "no_answer" | "advisory" | None
            sources:        list  — [{fund_name, groww_url, ingestion_date}]
            answered:       bool  — False when no info found or refused
            fund_id:        str | None — router-detected fund
            section_type:   str | None — router-detected section
            latency_s:      float
        """
        start = time.time()
        logger.info("Query: %r", query)

        # ── Step 1: Pre-retrieval PII check ──────────────────────────────────────
        # Refuse before any retrieval — never log or process personal data.
        if check_pii(query):
            logger.warning("PII detected in query — refusing immediately")
            return self._refused(query, "pii", time.time() - start)

        # ── Step 2: Intent classification (Phase 4) ──────────────────────────────
        clf = classify(query)
        intent = clf["intent"]
        logger.info(
            "Classifier: intent=%s  method=%s  reason=%s",
            intent, clf["method"], clf["reason"],
        )

        if intent != INTENT_FACTUAL:
            refusal = get_refusal(clf)
            latency = time.time() - start
            logger.info("Refused: intent=%s  latency=%.2fs", intent, latency)
            return {
                "response":       refusal["response"],
                "refused":        True,
                "refused_reason": refusal["refused_reason"],
                "sources":        [],
                "answered":       False,
                "fund_id":        None,
                "section_type":   None,
                "intent":         intent,
                "latency_s":      round(latency, 3),
            }

        # ── Step 3: Route — extract anchor signals ───────────────────────────────
        fund_id, section_type = route(query)
        logger.info("Router → fund_id=%s  section_type=%s", fund_id, section_type)

        # ── Step 4: Retrieve ─────────────────────────────────────────────────────
        chunks = retrieve(
            query,
            top_k=RETRIEVER_TOP_K,
            fund_id=fund_id,
            filter_section_type=section_type,
        )
        logger.info("Retrieved %d chunks", len(chunks))

        # ── Step 5: Generate ─────────────────────────────────────────────────────
        gen_result = generate(query, chunks)
        logger.info(
            "Generator → answered=%s  mode=%s  tokens=%d",
            gen_result["answered"], gen_result["mode"], gen_result["tokens_used"],
        )

        # ── Step 6: Postprocess (PII sanitize + URL policy + citation) ───────────
        pp_result = postprocess(query, gen_result)

        latency = time.time() - start
        logger.info("Latency: %.2fs", latency)

        return {
            "response":       pp_result["response"],
            "refused":        pp_result["refused"],
            "refused_reason": pp_result["refused_reason"],
            "sources":        pp_result["sources"],
            "answered":       pp_result["answered"],
            "fund_id":        fund_id,
            "section_type":   section_type,
            "intent":         intent,
            "latency_s":      round(latency, 3),
        }

    @staticmethod
    def _refused(query: str, reason: str, latency: float) -> dict:
        messages = {
            "pii":      (
                "I'm sorry, but I cannot process queries containing personal information. "
                "Please remove any personal details and try again."
            ),
            "advisory": (
                "I'm sorry, but I can only answer factual questions about mutual fund schemes. "
                "For investment guidance, please consult a SEBI-registered investment advisor."
            ),
        }
        return {
            "response":       messages.get(reason, "I cannot process this request."),
            "refused":        True,
            "refused_reason": reason,
            "sources":        [],
            "answered":       False,
            "fund_id":        None,
            "section_type":   None,
            "latency_s":      round(latency, 3),
        }


if __name__ == "__main__":
    pipeline = Pipeline()

    print("PIPELINE STARTED")

    test_query = "What is SIP?"
    result = pipeline.run(test_query)

    print("\nRESULT:")
    print(result)

    print("PIPELINE FINISHED")