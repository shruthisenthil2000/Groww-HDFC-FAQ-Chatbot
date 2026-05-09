"""
Phase 4 — Query Handling: End-to-End Pipeline Orchestrator
"""

from __future__ import annotations

import logging
import time

import config  # loads .env at import time
from config import LLM_MODEL, RETRIEVER_TOP_K, USE_RERANKER
from rag.retriever import retrieve

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Pipeline:

    def __init__(self):
        self.classifier = None
        self.retriever = retrieve
        self.reranker = None
        self.generator = None
        self.postprocessor = None

        logger.info("Pipeline initialized")

    def run(self, query: str) -> dict:
        start_time = time.time()
        logger.info(f"Query received: {query}")

        # ── STEP 1: Intent (placeholder) ──
        intent = "factual"

        if intent != "factual":
            return {
                "answer": "Sorry, I cannot help with that request.",
                "sources": [],
                "intent": intent,
                "refused": True
            }

        # ── STEP 2: Retrieve ──
        retrieved_docs = self.retriever(query)

        # ── STEP 3: Rerank (not implemented yet) ──
        reranked_docs = retrieved_docs

        # ── STEP 4: Generate (no LLM yet) ──
        if reranked_docs:
            answer = reranked_docs[0]["text"]
        else:
            answer = "No relevant information found."

        # ── STEP 5: Sources ──
        sources = [
            {
                "fund_name": doc.get("fund_name", ""),
                "groww_url": doc.get("groww_url", "")
            }
            for doc in reranked_docs[:3]
        ]

        end_time = time.time()
        logger.info(f"Latency: {end_time - start_time:.2f}s")

        return {
            "answer": answer,
            "sources": sources,
            "intent": intent,
            "refused": False
        }


if __name__ == "__main__":
    pipeline = Pipeline()

    print("PIPELINE STARTED")

    test_query = "What is SIP?"
    result = pipeline.run(test_query)

    print("\nRESULT:")
    print(result)

    print("PIPELINE FINISHED")