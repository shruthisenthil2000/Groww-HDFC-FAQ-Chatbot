"""
Phase 4 — Query Handling: Refusal Handler

Returns a polite, SEBI-compliant refusal message for queries classified
as advisory, out-of-scope, or ambiguous.

Refusal templates:
    advisory     : "I can share factual details about fund features, but I'm not
                    able to provide investment advice. Please consult a registered
                    financial advisor."
    out_of_scope : "This question is outside the scope of the 15 HDFC fund pages
                    I have access to. Please refer to hdfcfund.com or AMFI."
    ambiguous    : "Could you clarify what you'd like to know? I can answer
                    factual questions about HDFC mutual fund features."
"""

# TODO (Phase 4): Implement refusal handler
#   - Accept {intent, reason} from classifier
#   - Select and return the appropriate refusal template
#   - Log refusal events for evaluation (Phase 6)
