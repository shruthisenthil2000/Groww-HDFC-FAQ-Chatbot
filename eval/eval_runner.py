"""
Phase 6 — Evaluation: RAG Metrics Runner

Runs the evaluation suite over factual_qa_eval.csv and computes:
    - Faithfulness      : answer is grounded in retrieved context
    - Context Precision : fraction of retrieved chunks that are relevant
    - Refusal Rate      : fraction of advisory queries correctly refused
    - Citation Presence : fraction of answers with a valid source citation
    - Latency (P50/P95) : end-to-end response time

Output: eval/results_<date>.json

Usage:
    python tests/eval/eval_runner.py
"""

# TODO (Phase 6): Implement evaluation runner
#   - Load factual_qa_eval.csv (columns: question, expected_answer, fund_id, is_advisory)
#   - For each row: run pipeline.run(question)
#   - Compute metrics using RAGAS or custom scoring functions
#   - Write results to tests/eval/results_<date>.json
