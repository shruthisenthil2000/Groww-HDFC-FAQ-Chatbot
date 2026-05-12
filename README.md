# HDFC Mutual Fund FAQ Assistant

## Live Demo

Frontend: https://groww-hdfc-faq-frontend.onrender.com/

Backend API: https://groww-hdfc-faq-chatbot-production.up.railway.app/

A Retrieval-Augmented Generation (RAG) system that answers factual questions about  
**15 HDFC Mutual Fund schemes** using a fixed, closed corpus of Groww fund pages.

> **Disclaimer:** This system provides source-derived, snapshot-based information only.  
> It is not investment advice and is not a substitute for official AMC, AMFI, or SEBI publications.

---

## Features

- Retrieval-Augmented Generation (RAG)
- FAISS vector similarity search
- Sentence-transformer embeddings
- Source-grounded factual answers
- Closed corpus mutual fund assistant
- Live deployed frontend + backend
- Metadata-aware retrieval pipeline

---

## Project Phases

| Phase | Folder | Description |
|-------|--------|-------------|
| 0 | `corpus/` + `scripts/` | AMC & fund selection, URL manifest (`sources.json`) |
| 1 | `ingestion/scraper.py` | Scrape 15 Groww fund pages (HTML only) |
| 2 | `ingestion/extractor.py`, `chunker.py`, `indexer.py` | Extract, chunk, embed & index |
| 3 | `rag/` | RAG core: retriever, reranker, generator, postprocessor |
| 4 | `pipeline/` | Query classifier, refusal handler, end-to-end orchestrator |
| 5 | `ui/app.py` | Streamlit chat UI |
| 6 | `tests/` | Unit, integration, and RAG evaluation tests |
| 7 | *(deployment)* | Docker, CI/CD, corpus refresh strategy |

---

## Corpus Scope

The corpus is **fixed and closed**: only the 15 Groww HDFC Mutual Fund pages defined in  
`corpus/sources.json` are ever scraped or indexed.

| # | Fund | Category |
|---|------|----------|
| 1 | HDFC Flexi Cap Direct Plan Growth | Equity — Flexi Cap |
| 2 | HDFC Mid Cap Fund Direct Growth | Equity — Mid Cap |
| 3 | HDFC Focused Fund Direct Growth | Equity — Focused |
| 4 | HDFC ELSS Tax Saver Fund Direct Plan Growth | Equity — ELSS |
| 5 | HDFC Large Cap Fund Direct Growth | Equity — Large Cap |
| 6 | HDFC Silver ETF FoF Direct Growth | Commodities — Silver |
| 7 | HDFC Small Cap Fund Direct Growth | Equity — Small Cap |
| 8 | HDFC Defence Fund Direct Growth | Equity — Thematic |
| 9 | HDFC Gold ETF Fund of Fund Direct Plan Growth | Commodities — Gold |
| 10 | HDFC NIFTY 50 Index Fund Direct Growth | Equity — Index |
| 11 | HDFC Balanced Advantage Fund Direct Growth | Hybrid — Dynamic AA |
| 12 | HDFC Pharma And Healthcare Fund Direct Growth | Equity — Sectoral |
| 13 | HDFC BSE Sensex Index Fund Direct Growth | Equity — Index |
| 14 | HDFC Short Term Debt Fund Direct Plan Growth | Debt — Short Duration |
| 15 | HDFC Housing Opportunities Fund Direct Growth | Equity — Sectoral |

---

## Quick Start

### 1. Setup environment

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Fill in your API keys
```

### 2. Run Phase 0 validation

```bash
python scripts/phase0_setup.py
```

Expected output:

```txt
✔ Phase 0 validation PASSED. sources.json is ready for Phase 1.
```

### 3. Run tests (Phase 6)

```bash
pytest tests/ -v
```

### 4. Launch UI

```bash
streamlit run ui/app.py
```

---

## Sample Questions

- What is the expense ratio of HDFC Mid Cap Fund?
- Who manages HDFC Flexi Cap Fund?
- What category does HDFC Defence Fund belong to?
- Is HDFC ELSS eligible for tax saving?
- What is the NAV of HDFC Gold Fund?

---

## Known Limitations

- Answers are restricted to the indexed Groww corpus.
- Does not provide financial or investment advice.
- NAV and market values may become outdated over time.
- Cannot answer questions outside supported HDFC schemes.
- Depends on scraped snapshot data, not live AMC feeds.

---

## Folder Structure

```txt
├── corpus/
│   ├── raw/
│   ├── processed/
│   └── sources.json
├── ingestion/
│   ├── scraper.py
│   ├── extractor.py
│   ├── chunker.py
│   └── indexer.py
├── rag/
│   ├── retriever.py
│   ├── reranker.py
│   ├── generator.py
│   └── postprocessor.py
├── pipeline/
│   ├── classifier.py
│   ├── refusal_handler.py
│   └── pipeline.py
├── ui/
│   └── app.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── eval/
├── scripts/
│   └── phase0_setup.py
├── DOCS/
│   ├── architecture.md
│   ├── edge_cases.md
│   └── problemstatement.md
├── sources.md
├── sample_qa.md
├── requirements.txt
└── README.md
```

---

## Architecture Reference

See `DOCS/architecture.md` for the full phase-wise architecture.  
See `DOCS/edge_cases.md` for edge cases and retrieval handling strategies.