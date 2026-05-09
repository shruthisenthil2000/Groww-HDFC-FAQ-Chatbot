"""
Phase 4 — Query Handling: Query Classifier

Classifies an incoming user query into one of the following intents:
    - factual      : answerable from the corpus (e.g. "What is the expense ratio?")
    - advisory     : investment advice (e.g. "Should I invest in this fund?")
    - out_of_scope : topic not covered by the 15-fund corpus
    - ambiguous    : needs clarification

Only 'factual' queries proceed to the RAG pipeline.
All others are routed to refusal_handler.py.
"""

# TODO (Phase 4): Implement classifier
#   - Use keyword heuristics as a first pass (fast, no LLM call)
#   - Optional: use a lightweight LLM call for ambiguous cases
#   - Return {intent: str, confidence: float, reason: str}
