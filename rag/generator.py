"""
Phase 3 — RAG Core: Response Generator

Constructs the final answer by passing retrieved context + user query
to the LLM. Enforces strict constraints:
  - Answers only from retrieved context (no hallucination)
  - Maximum 3 sentences per response
  - Mandatory source citation
  - Temperature: low-variance (≤ 0.2)
  - Financial advice is explicitly refused

Environment variables (loaded via config.py):
    LLM_PROVIDER      openai | mistral (default: openai)
    LLM_MODEL         Model name (default: gpt-4o-mini)
    LLM_TEMPERATURE   Sampling temperature (default: 0.1)
    OPENAI_API_KEY    Required when LLM_PROVIDER=openai

System prompt template and generation parameters live here.
"""

from __future__ import annotations

import logging

# Environment is loaded once via config.py — no per-module load_dotenv() needed.
from config import LLM_PROVIDER, LLM_MODEL, LLM_TEMPERATURE, require_openai_key

logger = logging.getLogger(__name__)

# ── TODO (Phase 3): Implement generator ───────────────────────────────────────
#   - Build system prompt: facts-only, cite sources, max 3 sentences, no advice
#   - Build user prompt: inject top-n retrieved chunks as context
#   - Call LLM API:
#       api_key = require_openai_key()   # raises RuntimeError if missing
#       client = openai.OpenAI(api_key=api_key)
#       response = client.chat.completions.create(
#           model=LLM_MODEL,
#           messages=[{"role": "system", "content": SYSTEM_PROMPT},
#                     {"role": "user", "content": user_prompt}],
#           temperature=LLM_TEMPERATURE,
#           max_tokens=256,
#       )
#   - Return {answer, sources: [{fund_name, groww_url}], tokens_used}
