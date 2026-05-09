"""
Phase 3 — RAG Core: Post-Processor

Validates and formats the raw LLM output before surfacing to the user.
Responsibilities:
  - Enforce 3-sentence limit (trim if exceeded)
  - Inject formatted source citations
  - Detect and sanitise any PII in the response
  - Escape output for XSS safety (UI layer)
"""

# TODO (Phase 3): Implement post-processor
#   - Parse raw LLM response
#   - Split into sentences; truncate to 3 if exceeded
#   - Append "Source: <fund_name> — <groww_url>" citation block
#   - Run basic PII scan (regex for phone, email, Aadhaar patterns)
#   - HTML-escape the final string before returning to UI
