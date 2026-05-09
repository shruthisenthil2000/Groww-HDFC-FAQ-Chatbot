# HDFC Mutual Fund FAQ Assistant

A Retrieval-Augmented Generation (RAG) system that answers factual questions about
**14 HDFC Mutual Fund schemes** using a fixed, closed corpus of Groww fund pages.

> **Disclaimer:** This system provides source-derived, snapshot-based information only.
> It is not investment advice and is not a substitute for official AMC, AMFI, or SEBI publications.

---

## Project Phases

| Phase | Folder | Description |
|-------|--------|-------------|
| 0 | `corpus/` + `scripts/` | AMC & fund selection, URL manifest (`sources.json`) |
| 1 | `ingestion/scraper.py` | Scrape 14 Groww fund pages (HTML only) |
| 2 | `ingestion/extractor.py`, `chunker.py`, `indexer.py` | Extract, chunk, embed & index |
| 3 | `rag/` | RAG core: retriever, reranker, generator, postprocessor |
| 4 | `pipeline/` | Query classifier, refusal handler, end-to-end orchestrator |
| 5 | `ui/app.py` | Streamlit chat UI |
| 6 | `tests/` | Unit, integration, and RAG evaluation tests |
| 7 | *(deployment)* | Docker, CI/CD, corpus refresh strategy |

---

## Corpus Scope

The corpus is **fixed and closed**: only the 14 Groww HDFC Mutual Fund pages defined in
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

Expected output: `✔ Phase 0 validation PASSED. sources.json is ready for Phase 1.`

### 3. Run tests (Phase 6)

```bash
pytest tests/ -v
```

### 4. Launch UI (Phase 5 — after all phases are implemented)

```bash
streamlit run ui/app.py
```

---

## Folder Structure

```
├── corpus/
│   ├── raw/                  # Scraped HTML files (Phase 1 output)
│   ├── processed/            # Cleaned text + chunks (Phase 2 output)
│   └── sources.json          # Phase 0 deliverable — closed corpus manifest
├── ingestion/
│   ├── scraper.py            # Phase 1
│   ├── extractor.py          # Phase 2
│   ├── chunker.py            # Phase 2
│   └── indexer.py            # Phase 2
├── rag/
│   ├── retriever.py          # Phase 3
│   ├── reranker.py           # Phase 3
│   ├── generator.py          # Phase 3
│   └── postprocessor.py      # Phase 3
├── pipeline/
│   ├── classifier.py         # Phase 4
│   ├── refusal_handler.py    # Phase 4
│   └── pipeline.py           # Phase 4
├── ui/
│   └── app.py                # Phase 5
├── tests/
│   ├── unit/                 # Phase 6 unit tests
│   ├── integration/          # Phase 6 integration tests
│   └── eval/                 # Phase 6 RAG evaluation
├── scripts/
│   └── phase0_setup.py       # Phase 0 validation script
├── DOCS/
│   ├── architecture.md
│   ├── edge_cases.md
│   └── problemstatement.md
├── .env.example
├── requirements.txt
└── README.md
```

---

## Architecture Reference

See [`DOCS/architecture.md`](DOCS/architecture.md) for the full phase-wise architecture.
See [`DOCS/edge_cases.md`](DOCS/edge_cases.md) for edge cases per phase.
