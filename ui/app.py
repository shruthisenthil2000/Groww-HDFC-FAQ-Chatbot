"""
Phase 5 — User Interface: Streamlit App

Chat-style UI for the HDFC Mutual Fund FAQ Assistant.
Features:
    - Chat input with conversation history
    - Source citations displayed below each answer
    - Disclaimer banner: "For informational purposes only. Not investment advice."
    - Fund selector sidebar (optional filter by fund name)
    - XSS-safe rendering (output sanitised by postprocessor before display)

Run:
    streamlit run ui/app.py
"""

# TODO (Phase 5): Implement UI
#   - Streamlit chat interface (st.chat_input / st.chat_message)
#   - Call pipeline.run(query) for each user message
#   - Render answer + source links
#   - Add persistent disclaimer in sidebar and below each response
#   - Show riskometer / fund metadata cards (optional enhancement)
