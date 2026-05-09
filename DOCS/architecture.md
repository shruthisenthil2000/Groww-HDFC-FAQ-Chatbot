# Phase-Wise Architecture: Mutual Fund FAQ Assistant (Facts-Only Q&A)

## Overview

This document describes the end-to-end, phase-wise architecture for building a **RAG-based (Retrieval-Augmented Generation) Mutual Fund FAQ Assistant** using Groww as the reference product context. The assistant is designed to answer source-derived, snapshot-based queries about HDFC Mutual Fund schemes, drawing exclusively from the **15 Groww HDFC Mutual Fund pages** listed in Phase 0. No other URLs will be added to the corpus. All financial values (AUM, NAV, expense ratios, exit loads, tax rates) reflect ingestion-time data and may not represent current figures.

---

## Architecture Diagram (High-Level)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE (Phase 5)                     │
│         Welcome Message | Example Questions | Disclaimer            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ User Query
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      QUERY PIPELINE (Phase 4)                       │
│         Query Classifier → Intent Guard → Retriever → Generator     │
└───────┬───────────────────────────────────────────────┬─────────────┘
        │ Factual Query                                 │ Advisory Query
        ▼                                               ▼
┌───────────────────────┐                   ┌──────────────────────────┐
│   RAG CORE (Phase 3)  │                   │  REFUSAL HANDLER (Ph. 4) │
│  Embed → Retrieve →   │                   │  Polite Refusal +        │
│  Rerank → Generate    │                   │  Educational Link        │
└───────────────────────┘                   └──────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    VECTOR STORE (Phase 2)                           │
│              Chunked + Embedded Official Documents                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│               CORPUS & INGESTION PIPELINE (Phase 1 & 2)             │
│        15 Groww HDFC Fund Pages (fixed, no additional URLs)         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 0: Project Scope — AMC, Fund Selection & URL Manifest

**Goal:** Lock down the AMC, schemes, and the exact source URLs that form the corpus for this project before any data collection begins.

### 0.1 Selected AMC

| Attribute       | Value                                                              |
|-----------------|--------------------------------------------------------------------|
| AMC             | **HDFC Mutual Fund**                                               |
| AMC Rank        | #2 in India by total AUM *(as per ingestion-time data)*            |
| Total AUM       | ₹8,54,364.43 Cr *(snapshot value — ingestion date: May 2026)*      |
| Website         | [hdfcfund.com](http://www.hdfcfund.com)                            |
| Registrar       | CAMS (camsonline.com)                                              |
| AMC Phone       | 022 – 66316333 *(verify on hdfcfund.com for current details)*      |

---

### 0.2 Selected Fund Schemes (14 Unique Funds)

> **Note:** `hdfc-equity-fund-direct-growth` is the legacy URL for **HDFC Flexi Cap Direct Plan Growth** (renamed per SEBI category rationalisation). It appears once in the corpus.
>
> **Data disclaimer:** All values in this table (Expense Ratio, AUM, Min SIP, Exit Load) are **ingestion-time snapshots** sourced from Groww fund pages at the time of corpus collection. These values may change over time. Do not treat them as current or guaranteed figures.

| # | Fund Name | Category | Sub-Category | Risk *(ingestion-time)* | Expense Ratio *(snapshot)* | AUM *(snapshot, Cr)* | Min SIP *(snapshot)* | Exit Load *(snapshot)* | Benchmark |
|---|-----------|----------|-------------|------|--------------|----------|---------|-----------|-----------|
| 1 | HDFC Flexi Cap Direct Plan Growth *(equity URL)* | Equity | Flexi Cap | Very High | 0.67% | ₹91,334.91 | ₹100 | 1% if redeemed < 1 yr | NIFTY 500 TRI |
| 2 | HDFC Mid Cap Fund Direct Growth | Equity | Mid Cap | Very High | 0.73% | ₹85,357.92 | ₹100 | 1% if redeemed < 1 yr | NIFTY Midcap 150 TRI |
| 3 | HDFC Focused Fund Direct Growth | Equity | Flexi Cap (Focused) | Very High | 0.68% | ₹24,169.51 | ₹100 | 1% if redeemed < 1 yr | NIFTY 500 TRI |
| 4 | HDFC ELSS Tax Saver Fund Direct Plan Growth | Equity | ELSS (3Y lock-in) | Very High | 1.11% | ₹14,615.19 | ₹500 | Nil *(as per source)* | NIFTY 500 TRI |
| 5 | HDFC Large Cap Fund Direct Growth | Equity | Large Cap | Very High | 0.98% | ₹35,458.50 | ₹100 | 1% if redeemed < 1 yr | NIFTY 100 TRI |
| 6 | HDFC Small Cap Fund Direct Growth | Equity | Small Cap | Very High | 0.83% | ₹33,724.28 | ₹100 | 1% if redeemed < 1 yr | NIFTY Smallcap 250 TRI |
| 7 | HDFC Defence Fund Direct Growth | Equity | Thematic | Very High | 0.83% | ₹7,304.61 | ₹100 | 1% if redeemed < 1 yr | Nifty India Defence TRI |
| 8 | HDFC Pharma And Healthcare Fund Direct Growth | Equity | Sectoral | Very High | 1.02% | ₹1,976.86 | ₹100 | 1% if redeemed < 30 days | BSE Healthcare TRI |
| 9 | HDFC NIFTY 50 Index Fund Direct Growth | Equity | Large Cap (Index) | Very High | 0.33% | ₹20,436.59 | ₹100 | Nil *(as per source)* | NIFTY 50 TRI |
| 10 | HDFC BSE Sensex Index Fund Direct Growth | Equity | Large Cap (Index) | Very High | 0.28% | ₹7,896.85 | ₹100 | Nil *(as per source)* | BSE SENSEX TRI |
| 11 | HDFC Balanced Advantage Fund Direct Growth | Hybrid | Dynamic Asset Allocation | Very High | 0.77% | ₹98,457.75 | ₹100 | 1% if redeemed < 1 yr | NIFTY 50 + CRISIL Composite Bond |
| 12 | HDFC Gold ETF Fund of Fund Direct Plan Growth | Commodities | Gold | High | 0.20% | ₹10,990.19 | ₹100 | 1% if redeemed < 15 days | Domestic Price of Gold |
| 13 | HDFC Silver ETF FoF Direct Growth | Commodities | Silver | Very High | 0.21% | ₹4,112.31 | ₹100 | 1% if redeemed < 15 days | Domestic Price of Silver |
| 14 | HDFC Short Term Debt Fund Direct Plan Growth | Debt | Short Duration | Moderate | 0.39% | ₹15,462.92 | ₹100 | Nil *(as per source)* | CRISIL Short Duration Debt Index |

---

### 0.3 Source URL Manifest (15 URLs — 14 Unique)

These are the **primary Groww fund pages** that form the complete corpus. Content is scraped directly from these HTML pages only — linked documents (SID PDFs, factsheets) are not fetched.

| # | URL | Fund | Corpus Role |
|---|-----|------|-------------|
| 1 | [hdfc-equity-fund-direct-growth](https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth) | HDFC Flexi Cap (legacy URL) | Primary source |
| 2 | [hdfc-mid-cap-fund-direct-growth](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth) | HDFC Mid Cap Fund | Primary source |
| 3 | [hdfc-focused-fund-direct-growth](https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth) | HDFC Focused Fund | Primary source |
| 4 | [hdfc-elss-tax-saver-fund-direct-plan-growth](https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth) | HDFC ELSS Tax Saver | Primary source |
| 5 | [hdfc-large-cap-fund-direct-growth](https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth) | HDFC Large Cap Fund | Primary source |
| 6 | [hdfc-silver-etf-fof-direct-growth](https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth) | HDFC Silver ETF FoF | Primary source |
| 7 | [hdfc-equity-fund-direct-growth](https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth) | *(duplicate of #1 — de-duplicated before indexing)* | Excluded |
| 8 | [hdfc-small-cap-fund-direct-growth](https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth) | HDFC Small Cap Fund | Primary source |
| 9 | [hdfc-defence-fund-direct-growth](https://groww.in/mutual-funds/hdfc-defence-fund-direct-growth) | HDFC Defence Fund | Primary source |
| 10 | [hdfc-gold-etf-fund-of-fund-direct-plan-growth](https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth) | HDFC Gold ETF FoF | Primary source |
| 11 | [hdfc-nifty-50-index-fund-direct-growth](https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth) | HDFC NIFTY 50 Index Fund | Primary source |
| 12 | [hdfc-balanced-advantage-fund-direct-growth](https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth) | HDFC Balanced Advantage Fund | Primary source |
| 13 | [hdfc-pharma-and-healthcare-fund-direct-growth](https://groww.in/mutual-funds/hdfc-pharma-and-healthcare-fund-direct-growth) | HDFC Pharma & Healthcare Fund | Primary source |
| 14 | [hdfc-bse-sensex-index-fund-direct-growth](https://groww.in/mutual-funds/hdfc-bse-sensex-index-fund-direct-growth) | HDFC BSE Sensex Index Fund | Primary source |
| 15 | [hdfc-short-term-opportunities-fund-direct-growth](https://groww.in/mutual-funds/hdfc-short-term-opportunities-fund-direct-growth) | HDFC Short Term Debt Fund | Primary source |

---

### 0.4 Category Coverage & Rationale

```
Equity Funds (10)
├── Large Cap          : HDFC Large Cap, NIFTY 50 Index, BSE Sensex Index
├── Mid Cap            : HDFC Mid Cap
├── Small Cap          : HDFC Small Cap
├── Flexi Cap          : HDFC Flexi Cap (Equity URL), HDFC Focused
├── ELSS               : HDFC ELSS Tax Saver  (3Y lock-in, tax-saving)
└── Thematic/Sectoral  : HDFC Defence, HDFC Pharma & Healthcare

Hybrid Funds (1)
└── Dynamic Asset Alloc: HDFC Balanced Advantage

Commodity Funds (2)
├── Gold FoF           : HDFC Gold ETF FoF
└── Silver FoF         : HDFC Silver ETF FoF

Debt Funds (1)
└── Short Duration     : HDFC Short Term Debt
```

**Why this selection covers FAQ diversity:**

| FAQ Topic | Fund(s) Covering It | Notes |
|-----------|-------------------|-------|
| Expense ratio (active vs index) | All 14 funds | Values are ingestion-time snapshots; actual TER may vary |
| ELSS lock-in period | HDFC ELSS Tax Saver | Lock-in period as stated in source at ingestion time |
| Minimum SIP amounts | All 14 funds | Amounts as per Groww page at ingestion; verify with AMC |
| Exit load rules | All 14 funds (varies by fund) | Source-derived; subject to AMC revision |
| Riskometer classification | All 14 funds | Riskometer levels as displayed on Groww at ingestion time |
| Benchmark index | All 14 funds (7 distinct indices) | Benchmarks as stated in source |
| Tax treatment (LTCG/STCG) | All 14 funds | Tax notes as displayed on Groww; tax laws may change — do not treat as tax advice |
| Capital gains / statement download | All 14 funds | Guidance sourced from Groww fund pages only |

---

### 0.5 `sources.json` Manifest Structure (Phase 0 Output)

```json
{
  "amc": "HDFC Mutual Fund",
  "amc_website": "http://www.hdfcfund.com",
  "registrar": "CAMS",
  "last_fetched": "2026-05-08",
  "funds": [
    {
      "fund_name": "HDFC Flexi Cap Direct Plan Growth",
      "category": "Equity - Flexi Cap",
      "risk": "Very High",
      "expense_ratio": "0.67%",
      "min_sip": 100,
      "exit_load": "1% if redeemed within 1 year",
      "benchmark": "NIFTY 500 TRI",
      "groww_url": "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
      "doc_types": ["groww_fund_page"],
      "local_file": "corpus/raw/hdfc_flexi_cap.html"
    }
    // ... repeat for all 14 funds
  ]
}
```

**Deliverable:** Completed `sources.json` with all 14 unique fund entries. This is the **final, closed corpus** — no additional URLs will be added in any subsequent phase.

---

## Phase 1: Corpus Definition & Data Collection

**Goal:** Scrape, validate, and store the 14 HDFC Mutual Fund HTML pages from Groww that form the closed corpus. Phase 1 is split into 5 independent, sequentially-implementable subphases.

> **Scope constraint:** The corpus is **strictly limited** to the 15 Groww HDFC fund page URLs (14 unique) defined in Phase 0 → Section 0.3. No additional URLs (AMC factsheets, AMFI pages, SEBI circulars, CAMS guides, etc.) will be added at any point.

---

### 1.1 Load & Validate `sources.json`

**Goal:** Read the Phase 0 manifest and confirm it is schema-valid before any network calls are made.

```
corpus/sources.json
        │
        ▼
┌──────────────────────────────────────────────┐
│         Manifest Validator                    │
│                                              │
│  ✔ 14 active fund entries present            │
│  ✔ All required fields non-null              │
│     (fund_id, fund_name, groww_url,          │
│      doc_type, local_file, category,         │
│      risk_level, ingestion_date)             │
│  ✔ All groww_url values start with           │
│     https://groww.in/mutual-funds/           │
│  ✔ All doc_type = "groww_fund_page"          │
│  ✔ No duplicate fund_id values               │
│  ✔ excluded_duplicates section present       │
└──────────────────────────────────────────────┘
        │
        ▼
  Validated fund list (14 entries)
```

**Input:** `corpus/sources.json`  
**Output:** In-memory validated list of 14 fund dicts; raises `ValueError` if any check fails  
**Script:** `scripts/phase0_setup.py` already covers this — Phase 1.1 imports its result  
**Key constraint:** If validation fails, Phase 1 must not proceed to 1.2

---

### 1.2 Configure HTTP Scraper Session

**Goal:** Set up a reusable `requests.Session` with safe, respectful scraping defaults before the first URL is fetched.

```python
# Session configuration (ingestion/scraper.py)
SESSION_CONFIG = {
    "headers": {
        "User-Agent": "Mozilla/5.0 (compatible; HDFCFAQBot/1.0; +internal-research)",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml"
    },
    "timeout": 30,           # seconds per request
    "delay_between_requests": 2,   # seconds — polite scraping
    "max_retries": 3,        # retry on 5xx / network errors
    "retry_backoff": 2.0     # exponential backoff multiplier
}
```

**Rules:**
- No crawling or link-following — only the 14 URLs from `sources.json`
- No authentication, cookies, or session tokens
- No PII sent in request headers or query params
- User-Agent clearly identifies the bot

**Input:** `SESSION_CONFIG` constants  
**Output:** Configured `requests.Session` object  
**Script:** `ingestion/scraper.py` — `build_session()` function

---

### 1.3 Fetch & Save Raw HTML (One File Per Fund)

**Goal:** Loop through the 14 active Groww URLs and save each page's full HTML to `corpus/raw/`.

```
Validated fund list (14 entries)
        │
        ▼ (for each fund)
  GET https://groww.in/mutual-funds/<slug>
        │
   ┌────┴──────────────────────┐
   │  HTTP 200?                │
   │  Yes          No (error)  │
   ▼               ▼
Save HTML      Log error +
to             set status =
corpus/raw/    "failed" in
<fund_id>.html  scrape_log
        │
        ▼
  Wait DELAY_BETWEEN_REQUESTS seconds
        │
        ▼ (next fund)
```

**Output files (14 expected):**
```
corpus/raw/
├── hdfc_flexi_cap.html
├── hdfc_mid_cap.html
├── hdfc_focused.html
├── hdfc_elss.html
├── hdfc_large_cap.html
├── hdfc_silver_etf_fof.html
├── hdfc_small_cap.html
├── hdfc_defence.html
├── hdfc_gold_etf_fof.html
├── hdfc_nifty50_index.html
├── hdfc_balanced_advantage.html
├── hdfc_pharma_healthcare.html
├── hdfc_bse_sensex_index.html
└── hdfc_short_term_debt.html
```

**What each HTML page contains (ingestion-time snapshots):**
- Fund overview: category, risk level, AUM, NAV *(point-in-time; not real-time)*
- Expense ratio and minimum SIP / lump sum amounts *(subject to change by AMC)*
- Exit load rules and stamp duty *(as stated on page at time of scrape)*
- Tax implication notes *(as displayed on Groww; reflect tax rules at ingestion time)*
- Benchmark index, fund manager details *(current at time of scrape)*
- Investment objective, holdings breakdown *(snapshot)*, return history *(historical)*

**Input:** Validated fund list + configured session  
**Output:** 14 `.html` files in `corpus/raw/`  
**Script:** `ingestion/scraper.py` — `fetch_and_save(fund, session)` function

---

### 1.4 De-duplicate & Integrity Check

**Goal:** Verify the `list[FetchResult]` produced by Phase 1.3 against the filesystem before the scrape log is written and Phase 2 begins. Raises `IntegrityError` with a full list of all failures — Phase 2 must not start until this gate passes.

> **Why two layers of input?** Phase 1.3's `fetch_all()` is the ground truth for what was *attempted*. The filesystem is the ground truth for what was *actually written*. Phase 1.4 cross-checks both.

**Inputs:**
- `results: list[FetchResult]` — output of `fetch_all()` from Phase 1.3
- `funds: list[dict]` — validated fund list from Phase 1.1 `load_and_validate()`
- `raw_dir: Path` — `corpus/raw/` directory

```
list[FetchResult] + validated funds + corpus/raw/
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│                  Integrity Checker                        │
│                                                          │
│  FetchResult-level checks (primary):                     │
│  ✔ Exactly 14 results in list (one per active fund)      │
│  ✔ All 14 results have scrape_status = "success"         │
│    → status = "failed"  : blocking error                 │
│    → status = "skipped" : unexpected duplicate leaked    │
│      through Phase 1.1/1.3; treated as blocking error    │
│  ✔ All 14 results have http_status = 200                 │
│  ✔ All 14 results have file_size_bytes > 0               │
│                                                          │
│  Filesystem cross-checks (secondary):                    │
│  ✔ For every success result: file exists on disk         │
│  ✔ On-disk file size matches result.file_size_bytes      │
│  ✔ On-disk file size > MIN_FILE_SIZE_BYTES (5 KB)        │
│  ✔ No orphan .html files in corpus/raw/ that are not     │
│    in the fund manifest (unexpected extra files)         │
└──────────────────────────────────────────────────────────┘
        │
   ┌────┴──────────────┐
   │ All checks pass?  │
   │  Yes       No     │
   ▼            ▼
Proceed      Raise IntegrityError
to 1.5       listing all failures
```

**Note on the duplicate URL:** The duplicate (`hdfc-equity-fund-direct-growth` = URL #7 in the original manifest) is already handled at two earlier stages:
- **Phase 1.1** (`load_and_validate`): `excluded_duplicates` documents the duplicate; only 14 unique active funds are returned.
- **Phase 1.3** (`fetch_all`): a `seen_urls` set skips any URL already fetched within the same run.

Phase 1.4 does **not** re-check for this specific duplicate. Instead, it checks that `skipped` count is zero — any `skipped` result at this stage means an unexpected duplicate was not caught earlier and is a blocking error.

**Failure policy:**

| Condition | Severity | Behaviour |
|-----------|----------|-----------|
| `scrape_status = "failed"` on any fund | Blocking | Raise `IntegrityError`; list all failed `fund_id` values |
| `scrape_status = "skipped"` on any fund | Blocking | Raise `IntegrityError`; indicates a de-dup gap in Phase 1.1 or 1.3 |
| `http_status ≠ 200` on a success result | Blocking | Raise `IntegrityError` |
| File missing on disk for a success result | Blocking | Raise `IntegrityError` |
| On-disk size ≠ `result.file_size_bytes` | Blocking | Raise `IntegrityError` |
| On-disk size < `MIN_FILE_SIZE_BYTES` (5 KB) | Warning | Log warning; do not raise (Groww SSR pages vary in size) |
| Orphan `.html` file in `corpus/raw/` | Warning | Log warning; do not raise |

**Input:** `list[FetchResult]` from Phase 1.3 `fetch_all()` + `funds` from Phase 1.1 + `corpus/raw/`  
**Output:** Passes silently on success; raises `IntegrityError` listing all blocking failures  
**Module:** `ingestion/phase1/integrity.py` — `verify_raw_corpus(results, funds, raw_dir)` function

---

### 1.5 Write Scrape Log

**Goal:** Record a machine-readable audit trail of the scraping run for debugging, corpus refresh, and evaluation traceability.

```json
// corpus/raw/scrape_log.json
{
  "run_date": "2026-05-08",
  "total_urls_attempted": 14,
  "total_urls_succeeded": 14,
  "total_urls_failed": 0,
  "entries": [
    {
      "fund_id": "hdfc_mid_cap",
      "groww_url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
      "local_file": "corpus/raw/hdfc_mid_cap.html",
      "http_status": 200,
      "file_size_bytes": 184320,
      "content_hash_sha256": "<hash>",
      "fetched_at": "2026-05-08T00:45:12Z",
      "scrape_status": "success"
    }
    // ... one entry per fund
  ]
}
```

**Fields per entry:**

| Field | Description |
|-------|-------------|
| `fund_id` | Matches `fund_id` in `sources.json` |
| `groww_url` | URL actually fetched |
| `local_file` | Relative path to saved HTML |
| `http_status` | HTTP response code (200 = success) |
| `file_size_bytes` | Size of saved file |
| `content_hash_sha256` | SHA-256 of raw HTML for change detection |
| `fetched_at` | ISO-8601 UTC timestamp |
| `scrape_status` | `"success"` \| `"failed"` \| `"skipped"` |

**Input:** Fetch results from Phase 1.3 + integrity results from Phase 1.4  
**Output:** `corpus/raw/scrape_log.json`  
**Script:** `ingestion/scraper.py` — `write_scrape_log(results)` function

---

### 1.6 Corpus Change Detection

**Goal:** Compare the SHA-256 content hashes from the current scrape log against the hashes recorded in a previous scrape log (if one exists) and produce a per-fund change report. This tells the pipeline whether re-ingestion (Phase 2) is necessary or whether the corpus is unchanged and the existing vector index can be reused.

```
scrape_log.json (current run)
         │
         ▼
┌─────────────────────────────────────────────┐
│           Change Detector                    │
│                                             │
│  Load previous log  ◄── corpus/raw/         │
│                         scrape_log.prev.json │
│  For each fund:                             │
│    compare content_hash_sha256              │
│    ├── same hash    → UNCHANGED             │
│    ├── different    → CHANGED               │
│    └── new fund /   → NEW / MISSING         │
│       prev missing                          │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
         ChangeReport (dict)
```

**Change status values:**

| Status | Meaning |
|--------|---------|
| `unchanged` | Hash matches previous run — HTML content is identical |
| `changed` | Hash differs — page content has been updated since last scrape |
| `new` | Fund present in current log but absent from previous log |
| `missing` | Fund was in previous log but not in current log (scrape failed) |
| `no_baseline` | No previous log exists — first run, all funds treated as new |

**Input:**
- `corpus/raw/scrape_log.json` — current run output from Phase 1.5
- `corpus/raw/scrape_log.prev.json` — previous run's log (if present; absent on first run)

**Output:** `ChangeReport` — an in-memory dict returned to the pipeline. Structure:

```json
{
  "run_date": "2026-05-08",
  "baseline_date": "2026-04-15",
  "has_baseline": true,
  "any_changed": true,
  "summary": {
    "unchanged": 12,
    "changed": 2,
    "new": 0,
    "missing": 0
  },
  "funds": {
    "hdfc_mid_cap": {
      "status": "changed",
      "current_hash":  "abc123...",
      "previous_hash": "def456..."
    },
    "hdfc_flexi_cap": {
      "status": "unchanged",
      "current_hash":  "aaa111...",
      "previous_hash": "aaa111..."
    }
    // ... one entry per fund
  }
}
```

**Behaviour:**
- If no previous log exists (`scrape_log.prev.json` absent): all funds are reported as `"new"`, `has_baseline` is `false`, `any_changed` is `true`.
- If previous log exists: after comparison, the current `scrape_log.json` is **copied** to `scrape_log.prev.json` to become the baseline for the next run.
- Phase 1.6 **never blocks** the pipeline — it is informational only. If `any_changed` is `false`, the pipeline runner (`scripts/run_phase2.py`) may skip Phase 2 to save time.

**Script:** `ingestion/phase1/change_detector.py` — `detect_changes(current_log, prev_log_path)` function

**Integration point in pipeline runner:**
```python
report = detect_changes(current_log, prev_log_path)
if not report["any_changed"]:
    logger.info("Corpus unchanged — skipping Phase 2 re-ingestion.")
    return 0
```

---

### 1.7 Corpus Integrity & Readiness Check

**Goal:** Validate that the persisted corpus on disk is complete, structurally sound, and safe for Phase 2 to consume. Acts as a **hard gate** — Phase 2 does not proceed if this check fails.

**Why distinct from Phase 1.4?**  
Phase 1.4 (`integrity.py`) validates in-memory `FetchResult` objects immediately after the HTTP fetch. Phase 1.7 reads the persisted on-disk state and is designed to run independently — at the start of a new session, after a partial run, after manual file edits, or as the entry-point gate in the GitHub Actions workflow (§7.4) before triggering Phase 2.

```
corpus/raw/               corpus/processed/
   ├── *.html    ──┐         └── chunks.jsonl  ──┐
   └── scrape_       │   (optional, prior run)    │
       log.json  ──┤                              │
                    ▼                              ▼
         ┌──────────────────────────────────────────────┐
         │        Readiness Checker (Phase 1.7)          │
         │                                              │
         │  Check 1  HTML completeness (blocking)       │
         │  Check 2  Minimum file size (blocking)       │
         │  Check 3  Scrape log consistency (blocking)  │
         │  Check 4  Chunk file schema   (warn-only)    │
         └──────────────────┬───────────────────────────┘
                            │
               ┌────────────┴────────────┐
               │ ready == True           │ ready == False
               ▼                         ▼
         Phase 2 proceeds          ReadinessError raised
                                   (all failures listed)
```

**Checks performed:**

| # | Check | Blocking? | Failure condition |
|---|-------|-----------|-------------------|
| 1 | **HTML completeness** | Yes | Any fund listed in `sources.json` is missing its `.html` file in `corpus/raw/` |
| 2 | **Minimum file size** | Yes | Any HTML file < 5 KB (likely a redirect or error page, not real content) |
| 3 | **Scrape log consistency** | Yes | `scrape_log.json` absent; or any entry has `scrape_status == "failed"` |
| 4 | **Chunk file integrity** | Warn-only | `chunks.jsonl` exists but contains entries missing required fields (`chunk_id`, `fund_id`, `text`, `section_type`) or total chunk count < 70 |

> Check 4 is warn-only because `chunks.jsonl` is a Phase 2 output and will be regenerated. Its absence is not an error.

**Input:**
- `funds` — validated fund list from Phase 1.1 `load_and_validate()`
- `corpus/raw/` — directory of scraped HTML files (Phase 1.3 output)
- `corpus/raw/scrape_log.json` — audit log from Phase 1.5
- `corpus/processed/chunks.jsonl` — *(optional)* chunk file from a prior Phase 2 run

**Output:** `ReadinessReport` — dict returned to the pipeline and logged. Structure:

```json
{
  "ready": true,
  "checked_at": "2026-05-08T18:30:00Z",
  "checks": {
    "html_completeness":      { "passed": true,  "found": 14, "missing": [] },
    "file_sizes":             { "passed": true,  "undersized": [] },
    "scrape_log_consistency": { "passed": true,  "failed_entries": 0, "skipped_entries": 0 },
    "chunk_file_integrity":   { "passed": true,  "chunks_found": 85, "schema_errors": [] }
  },
  "blocking_failures": [],
  "warnings": []
}
```

**Failure behaviour:**
- All blocking checks are run before raising — the error message lists every failure at once (fail loudly, fail completely).
- `ReadinessError` is raised with the full list of blocking failures.
- Warnings are logged at `WARNING` level but do not block Phase 2.

**Script:** `ingestion/phase1/readiness.py` — `check_readiness(funds, raw_dir, processed_dir)` function

**Integration point in pipeline runner (`scripts/run_phase1.py`):**
```python
from ingestion.phase1.readiness import check_readiness

report = check_readiness(funds, raw_dir, processed_dir)
if not report["ready"]:
    # ReadinessError already raised inside check_readiness — this line not reached
    pass
logger.info("Corpus ready. Proceeding to Phase 2.")
```

---

**Phase 1 Deliverable:** `corpus/raw/` with 14 validated HTML files + `corpus/raw/scrape_log.json` + `ChangeReport` (Phase 1.6) + `ReadinessReport` (Phase 1.7) confirming the corpus is gated and ready for Phase 2.

---

## Phase 2: Data Processing & Indexing

**Goal:** Transform raw documents into a searchable, semantically indexed vector store.

### 2.1 Text Extraction & Cleaning

```
Raw HTML (Groww fund pages)
     │
     ▼
┌──────────────────────────────────────┐
│         Text Extraction Layer        │
│  HTML ──► BeautifulSoup text strip   │
│  Tables ──► Structured row capture   │
│  Boilerplate ──► Selector blocklist  │
└──────────────────┬───────────────────┘
                   │
                   ▼
           Cleaned Plain Text
           (noise removed: nav menus,
            footers, promotional content)
```

### 2.2 Chunking Strategy

> **Why the original 500-token recursive splitter was replaced:**
> Groww fund pages contain three types of content in very different proportions:
> (1) ~200–300 tokens of dense, FAQ-critical facts (expense ratio, exit load, tax, min SIP, benchmark, about)
> (2) ~400–600 tokens of holdings rows (50–78 stocks per fund) that answer no FAQ query
> (3) ~200+ tokens of sitewide footer navigation repeated identically on every page.
> A generic 500-token splitter would scatter FAQ facts across chunk boundaries, pack holdings noise into retrieval results, and produce 400+ chunks across 14 funds — most of them useless. A section-aware strategy targeting ~100–140 clean chunks is far more appropriate for this corpus size and query type.

#### 2.2.1 Sections to extract vs. exclude

| Section | Action | Reason |
|---------|--------|--------|
| Fund header (name, category, risk, NAV, AUM, expense ratio, min SIP) | **Extract → `fund_overview` chunk** | Core FAQ target |
| Return calculator table (1Y/3Y/5Y SIP returns) | **Exclude** | Snapshot data, not FAQ-answerable |
| Holdings table (all rows) | **Exclude** | Portfolio changes daily; adds noise to every retrieval |
| Minimum investments block | **Merge into `fund_overview`** | Always answered alongside expense ratio |
| Generic term definitions (expense ratio, tax, exit load) | **Exclude** | Identical across all 14 funds; no fund-specific signal |
| Exit load + stamp duty + tax implication | **Extract → `exit_load_tax` chunk** | Always kept together — they answer the same query |
| Investment objective + fund benchmark | **Extract → `investment_objective` chunk** | Frequently queried directly |
| "About [Fund Name]" summary paragraph | **Extract → `about` chunk** | Best single-chunk answer for "What is [fund]?" |
| Fund management (manager name, education, experience) | **Extract → `fund_manager` chunk** | Occasionally queried |
| Fund manager "also manages" list | **Exclude** | Other-fund names add cross-fund retrieval noise |
| Compare similar funds table | **Exclude** | Cross-fund comparisons are out of scope |
| Fund house (AMC name, address, phone, AUM) | **Extract → `fund_house` chunk** | AMC-level FAQ queries |
| Site navigation header | **Exclude** | Pure UI boilerplate |
| Sitewide footer (~160 lines of links) | **Exclude** | Pure navigation noise |

#### 2.2.2 Section-Aware Chunking Flow

```
Cleaned per-fund text
        │
        ▼
┌────────────────────────────────────────────────────────────┐
│                  Section Detector                           │
│                                                            │
│  Match section boundaries using heading patterns:          │
│  "# <Fund Name>"         → fund_overview start             │
│  "## Holdings"           → holdings start (SKIP)           │
│  "### Minimum invest"    → merge into fund_overview        │
│  "### Exit Load"         → exit_load_tax start             │
│  "#### Investment Obj"   → investment_objective start      │
│  "### About <Fund>"      → about start                     │
│  "### Fund management"   → fund_manager start              │
│  "### Fund house"        → fund_house start                │
│  "© 2016" / footer text  → stop extraction                 │
└──────────────────┬─────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
   Short sections          Longer sections
   (< 250 tokens)          (> 250 tokens)
        │                     │
        ▼                     ▼
   Keep as single        Recursive Character Splitter
   chunk (no split)      Chunk size:  200 tokens
                         Overlap:      20 tokens
        │                     │
        └──────────┬──────────┘
                   ▼
        Section chunks with metadata
```

#### 2.2.3 Expected output per fund

| Chunk name | Content | Approx. tokens | Split? |
|------------|---------|----------------|--------|
| `fund_overview` | Fund name, category, risk, NAV, AUM, expense ratio, min SIP (1st/2nd/SIP) | 80–120 | No |
| `exit_load_tax` | Exit load rule + stamp duty + LTCG/STCG tax implication | 100–150 | No |
| `investment_objective` | Investment objective text + benchmark index | 60–100 | No |
| `about` | About [Fund Name] summary paragraph | 80–120 | No |
| `fund_manager` | Manager name, education, experience summary | 80–150 | No |
| `fund_house` | AMC name, AUM, incorporation date, contact details | 80–120 | No |

**Expected total:** ~6–8 chunks per fund × 14 funds = **~85–112 chunks** across the corpus.
This is intentionally compact: small corpus + focused chunks = higher retrieval precision.

#### 2.2.4 Chunk schema

```json
{
  "chunk_id":      "<fund_id>_<section_type>_<seq>",
  "fund_id":       "hdfc_mid_cap",
  "fund_name":     "HDFC Mid Cap Fund Direct Growth",
  "groww_url":     "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
  "doc_type":      "groww_fund_page",
  "section_type":  "exit_load_tax",
  "ingestion_date":"2026-05-08",
  "text":          "Exit load of 1% if redeemed within 1 year...",
  "tokens":        112
}
```

**`section_type` values:** `fund_overview` | `exit_load_tax` | `investment_objective` | `about` | `fund_manager` | `fund_house`

The `section_type` field is surfaced to Phase 3.2 retrieval for optional metadata filtering (e.g., an expense-ratio query can filter to `section_type="fund_overview"` to boost precision).

### 2.3 Embedding Generation

```
(chunk_text, metadata)
        │
        ▼
┌──────────────────────────────────────┐
│         Embedding Model              │
│  Model: text-embedding-3-small       │
│         (OpenAI) OR                  │
│         sentence-transformers/       │
│         all-MiniLM-L6-v2 (local)     │
│                                      │
│  Output: 384 or 1536-dim vector      │
└──────────────────┬───────────────────┘
                   │
                   ▼
           (vector, chunk_text, metadata)
```

### 2.4 Vector Store Indexing

```
(vector, chunk_text, metadata)
              │
              ▼
┌─────────────────────────────────────────┐
│            Vector Store                  │
│  Options:                               │
│  ├── FAISS (local, lightweight)         │
│  ├── ChromaDB (local persistent)        │
│  └── Pinecone (cloud, production)       │
│                                         │
│  Index Type: cosine similarity          │
│  Metadata filtering: doc_type, scheme   │
└─────────────────────────────────────────┘
```

**Deliverable:** A persisted vector index with chunk metadata, ready for semantic search.

---

## Phase 3: RAG Core Architecture

**Goal:** Given a user query, retrieve the most relevant document chunks and generate a grounded, factual response.

### 3.1 Query Embedding

```
User Query (text)
        │
        ▼
  Same Embedding Model
  (as Phase 2.3)
        │
        ▼
  Query Vector (384 or 1536-dim)
```

### 3.2 Retrieval — Two-Stage Metadata-Anchored Strategy

> **Why a two-stage approach?**
> Cross-fund cosine similarity analysis on the 85-chunk corpus reveals that pure dense retrieval is unreliable for this data:
>
> | Section | Avg cross-fund sim | Risk |
> |---|---|---|
> | `fund_house` | **0.994** | All 14 share the same AMC — chunks are near-identical |
> | `exit_load_tax` | **0.934** | Structurally identical text across funds |
> | `about` | 0.841 | Moderate confusion |
> | `fund_overview` | 0.788 | Acceptable — metric values vary |
>
> The discriminating signals are the **fund name** and **query intent**, not the embedding distance. A router that extracts both before the dense search eliminates the confusion at zero extra cost.

#### 3.2.1 Stage 1 — Query Router

```
User Query
      │
      ▼
┌─────────────────────────────────────────┐
│           Query Router                   │
│  (retrieval/router.py)                  │
│                                         │
│  Fund name detection                    │
│  ─────────────────────                  │
│  Match query against fund aliases:      │
│  "mid cap"      → hdfc_mid_cap          │
│  "ELSS","tax saver" → hdfc_elss         │
│  "flexi cap","equity fund"→hdfc_flexi_cap│
│  "nifty 50"     → hdfc_nifty50_index    │
│  "sensex"       → hdfc_bse_sensex_index  │
│  "defence"      → hdfc_defence          │
│  "pharma","healthcare" → hdfc_pharma_   │
│                          healthcare     │
│  "gold"         → hdfc_gold_etf_fof     │
│  "silver"       → hdfc_silver_etf_fof   │
│  "large cap"    → hdfc_large_cap        │
│  "small cap"    → hdfc_small_cap        │
│  "focused"      → hdfc_focused          │
│  "balanced","advantage" →               │
│                  hdfc_balanced_advantage │
│  "short term","debt"→hdfc_short_term_debt│
│  (no match)     → None (search all 85) │
│                                         │
│  Section routing                        │
│  ────────────────                       │
│  "expense ratio","TER","fee" →          │
│                  fund_overview          │
│  "exit load","redemption"  →            │
│                  exit_load_tax          │
│  "tax","LTCG","STCG","stamp duty" →     │
│                  exit_load_tax          │
│  "minimum SIP","min investment" →       │
│                  fund_overview          │
│  "NAV","AUM","fund size"  →             │
│                  fund_overview          │
│  "investment objective","benchmark" →   │
│                  investment_objective   │
│  "fund manager","who manages" →         │
│                  fund_manager           │
│  "about","what is","overview" →         │
│                  about                  │
│  "AMC","fund house" →  fund_house       │
│  (no match)     → None (no filter)     │
└──────────────┬──────────────────────────┘
               │
               ▼
     (fund_id, section_type)
     either or both may be None
```

**Script:** `retrieval/router.py` — `route(query) -> tuple[str | None, str | None]`

#### 3.2.2 Stage 2 — Dense Search with Metadata Filters

```
(query_embedding, fund_id, section_type)
               │
               ▼
┌──────────────────────────────────────────────┐
│          FAISS Dense Search                   │
│                                              │
│  search_faiss(                               │
│    query_embedding,                          │
│    top_k = RETRIEVER_TOP_K,                  │
│    filter_section_type = section_type        │
│  )                                           │
│                                              │
│  → Returns top-k chunks, ordered by          │
│    cosine similarity (highest first)         │
└──────────────────────┬───────────────────────┘
                       │
          ┌────────────┴────────────┐
          │ fund_id detected?       │
          │  Yes          No        │
          ▼               ▼
  Post-filter by       Return all
  fund_id             results as-is
          │
  ┌───────┴──────────────────┐
  │ filtered results ≥ 1?    │
  │  Yes          No         │
  ▼               ▼
Return          Fall back to
filtered        unfiltered
results         results
                (prevents empty
                 response on
                 ambiguous query)
```

**Why fallback?** If the user asks about "exit load" without specifying a fund, or the fund name is ambiguous, the post-filter would return nothing. Falling back to the unfiltered `section_type`-filtered results still improves precision over a fully unfiltered search.

**Input:** `query_embedding` + `(fund_id, section_type)` from Stage 1
**Output:** Ranked list of result dicts — `chunk_id`, `fund_id`, `fund_name`, `groww_url`, `section_type`, `text`, `score`
**Script:** `retrieval/retriever.py` — `retrieve(query, top_k, fund_id, filter_section_type)`

#### 3.2.3 Retrieval Precision Expectations

| Query type | Anchors detected | Effective search space | Expected precision |
|---|---|---|---|
| "Exit load for HDFC Mid Cap?" | fund_id + section_type | 1 chunk (exact) | Very high |
| "What is the expense ratio?" (no fund) | section_type only | 14 chunks (one per fund) | High — top result will be highest-sim fund_overview |
| "Who manages HDFC ELSS?" | fund_id + section_type | 1 chunk (exact) | Very high |
| "Tell me about HDFC Gold fund" | fund_id + section_type | 1 chunk | Very high |
| "What is a mutual fund?" | None | All 85 chunks | Low — out-of-scope; refusal handler catches it |

### 3.3 Re-ranking (Optional but Recommended)

```
Top-K Retrieved Chunks
        │
        ▼
┌───────────────────────────────────┐
│         Cross-Encoder Reranker    │
│  Model: ms-marco-MiniLM-L-6-v2    │
│  Scores each (query, chunk) pair  │
│  Returns top-3 most relevant      │
└───────────────────────────────────┘
```

### 3.4 Prompt Construction

```python
SYSTEM_PROMPT = """
You are a facts-only mutual fund FAQ assistant for HDFC Mutual Fund schemes.

STRICT RULES:
1. Answer ONLY using the information provided in the context below.
   Do NOT use any knowledge outside of the provided context.
2. Keep your response to 3 sentences or fewer.
3. Do NOT give investment advice, recommendations, or performance predictions.
4. Do NOT include or reproduce any personal information (names, phone numbers,
   email addresses, Aadhaar numbers, PAN, or any other identifiers).
5. Answer in plain, factual English. Be concise.

NO-ANSWER RULE (critical):
- If the context does not contain enough information to answer the question,
  respond with EXACTLY this phrase and nothing else:
  "I don't have this information in my current sources."
- Do NOT guess, infer, or supplement from general knowledge.
- Do NOT include a source citation when you cannot answer.

SOURCE CITATION RULE:
- When you provide a real answer, end with:
  "Source: <groww_url> | Data as of: <ingestion_date>"
- When you output the no-answer phrase, do NOT include any URL or date.
"""

USER_PROMPT = f"""
Context:
{retrieved_chunks}

Question: {user_query}
"""
```

**No-answer sentinel:** `"I don't have this information in my current sources."`
- The post-processor detects this exact string to decide whether to attach a URL.
- Triggered whenever retrieved chunks do not contain a relevant answer.
- **No URL is attached when this sentinel is returned.**

### 3.5 Response Generation

```
(System Prompt + User Prompt)
              │
              ▼
┌──────────────────────────────────────────────┐
│            LLM (Generation)                  │
│                                              │
│  Primary: Groq (LLM_PROVIDER=groq)           │
│  ├── llama-3.1-8b-instant  (default, fast)   │
│  ├── llama-3.3-70b-versatile (higher quality)│
│  └── mixtral-8x7b-32768    (large context)   │
│  Free tier available — https://console.groq.com│
│                                              │
│  Fallback: OpenAI (LLM_PROVIDER=openai)      │
│  └── gpt-4o-mini                             │
│                                              │
│  Retrieval-only (no API key configured):     │
│  └── formats top chunk text directly         │
│                                              │
│  Parameters:                                 │
│  ├── temperature: 0.1 (low-variance)         │
│  ├── max_tokens:  256                        │
│  └── top_p:       1.0                        │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
         GeneratorResult
         ├── answer:      str   (raw LLM text)
         ├── answered:    bool  (False → no-answer sentinel detected)
         ├── sources:     list  (empty if answered=False)
         ├── tokens_used: int
         └── mode:        "groq" | "openai" | "fallback"
```

**Backend selection order:**
1. Groq — if `LLM_PROVIDER=groq` and `GROQ_API_KEY` is set
2. OpenAI — if `LLM_PROVIDER=openai` and `OPENAI_API_KEY` is set
3. Retrieval-only fallback — if no valid API key is available

**Script:** `retrieval/generator.py` — `generate(query, retrieved_chunks) -> GeneratorResult`

### 3.6 Response Post-Processing

```
(query, GeneratorResult)
              │
              ▼
┌──────────────────────────────────────────────────────────┐
│              Post-Processor                               │
│                                                          │
│  Step 1: PII check on QUERY                              │
│  ────────────────────────────────────────                │
│  Detect: Aadhaar (12-digit), PAN (XXXXX0000X),           │
│          Indian phone (10-digit, starts 6-9),            │
│          email address                                   │
│  If PII found →                                          │
│    Return refusal: "I'm sorry, but I cannot process      │
│    queries containing personal information. Please       │
│    remove any personal details and try again."           │
│    *** NO source URL attached ***                        │
│                                                          │
│  Step 2: No-answer check                                 │
│  ────────────────────────────────────────                │
│  If GeneratorResult.answered == False →                  │
│    Return: "I don't have this information in my          │
│    current sources."                                     │
│    *** NO source URL attached ***                        │
│                                                          │
│  Step 3: Format answered response                        │
│  ────────────────────────────────────────                │
│  Enforce 3-sentence limit (trim if exceeded)             │
│  Ensure source citation is present:                      │
│    "Source: <groww_url> | Data as of: <ingestion_date>"  │
│  Sanitize: strip any PII leaked into LLM output          │
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
                  PostProcessResult
                  ├── response:       str
                  ├── refused:        bool
                  ├── refused_reason: "pii" | "no_answer" | None
                  └── sources:        list  (empty when refused)
```

**URL attachment policy:**

| Condition | URL attached? | Reason |
|---|---|---|
| Answer found in corpus | Yes | Citation is mandatory for grounded answers |
| Answer NOT found in corpus | **No** | No source can be cited for information we don't have |
| Query contains PII | **No** | Refusal responses never cite sources |
| Advisory query (Phase 4) | **No** | Refusal does not imply any source endorsement |

**Script:** `retrieval/postprocessor.py` — `postprocess(query, generator_result) -> PostProcessResult`

**Example — answered:**
```
As per the ingestion-time data, the expense ratio for HDFC Large Cap Fund (Direct Plan)
is 0.98% per annum. Exit load is 1% if redeemed within 1 year from the date of allotment.

Source: https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth | Data as of: 2026-05-08
```

**Example — not answered (no URL):**
```
I don't have this information in my current sources.
```

**Example — PII in query (no URL):**
```
I'm sorry, but I cannot process queries containing personal information.
Please remove any personal details and try again.
```

---

## Phase 4: Query Classification & Refusal Handling

**Goal:** Identify advisory or non-factual queries and return a polite, compliant refusal before any retrieval or LLM call is made.

### 4.1 Intent Classification — Hybrid Approach

```
User Query
     │
     ▼
┌──────────────────────────────────────────────────────────┐
│              Intent Classifier (Hybrid)                   │
│                                                          │
│  Stage A: Rule-based pass (fast, no LLM, always runs)    │
│  ─────────────────────────────────────────               │
│  Advisory triggers (→ "advisory"):                       │
│    "should i", "recommend", "which is best",             │
│    "better fund", "worth investing", "good fund",        │
│    "which fund should", "suggest", "which one",          │
│    "will it give", "expected return", "future return"    │
│                                                          │
│  Out-of-scope triggers (→ "out_of_scope"):               │
│    "stock price", "share price", "crypto", "bitcoin",    │
│    "sensex level", "nifty level", "ipo", "demat",        │
│    "weather", "cricket", "election", "company revenue"   │
│                                                          │
│  Factual signals (→ "factual", skip LLM):                │
│    "expense ratio", "exit load", "nav", "aum", "sip",   │
│    "fund manager", "benchmark", "objective", "elss",     │
│    "lock-in", "minimum", "riskometer", "tax", "ltcg"    │
│                                                          │
│  If no rule fires → result = "ambiguous"                 │
│                                                          │
│  Stage B: Groq LLM pass (only for "ambiguous" queries)   │
│  ─────────────────────────────────────────               │
│  Zero-shot prompt:                                       │
│    "Classify this query into one of: factual,            │
│     advisory, out_of_scope. Reply with one word only."   │
│  If Groq unavailable → keep "ambiguous"                  │
└──────────────────────────┬───────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
      factual           advisory      out_of_scope / ambiguous
         │                 │                 │
         ▼                 ▼                 ▼
    RAG Pipeline    Refusal Handler    Refusal Handler
```

**Output:** `ClassificationResult`
```json
{
  "intent":     "factual | advisory | out_of_scope | ambiguous",
  "confidence": 1.0,
  "reason":     "matched rule: 'should i'",
  "method":     "rule_based | groq_llm | fallback"
}
```

**Script:** `orchestrator/classifier.py` — `classify(query) -> ClassificationResult`

### 4.2 Refusal Handler

Per-intent refusal templates — no source URL is ever attached to a refusal response.

| Intent | Response | Link |
|---|---|---|
| `advisory` | SEBI-compliant investment advice refusal | AMFI Investor Corner |
| `out_of_scope` | "This assistant only covers factual questions about the 14 HDFC fund schemes." | hdfcfund.com |
| `ambiguous` | Clarification prompt — lists example factual questions | — |

```python
ADVISORY_REFUSAL = """
I'm sorry, but I can only answer factual questions about mutual fund schemes.
Questions about whether to invest, which fund is better, or expected returns
fall outside the scope of this assistant.

For investment guidance, please consult a SEBI-registered investment advisor.
Learn more: https://www.amfiindia.com/investor-corner
"""

OUT_OF_SCOPE_REFUSAL = """
This assistant only covers factual questions about the 14 HDFC Mutual Fund
schemes in its corpus. For other topics, please refer to official sources.
"""

AMBIGUOUS_REFUSAL = """
I can answer factual questions about HDFC Mutual Fund schemes — for example:
  • "What is the expense ratio of HDFC Mid Cap Fund?"
  • "What is the exit load for HDFC ELSS?"
  • "Who manages the HDFC Balanced Advantage Fund?"

Could you rephrase your question along those lines?
"""
```

**Script:** `orchestrator/refusal_handler.py` — `get_refusal(classification_result) -> RefusalResult`

### 4.3 Out-of-Scope Handling

```
Query intent
  │
  ├── advisory      → ADVISORY_REFUSAL    (no URL — no source endorsement)
  ├── out_of_scope  → OUT_OF_SCOPE_REFUSAL (no URL)
  ├── ambiguous     → AMBIGUOUS_REFUSAL   (with example questions)
  └── factual       → RAG pipeline (Phase 3)
```

### 4.4 Full Pipeline Flow (Phase 3 + 4 combined)

```
User Query
     │
     ├─ Phase 3.6 Step 1 ──► PII check     → refuse (no URL)
     │
     ├─ Phase 4.1 ──────────► Classify intent
     │    ├── advisory / out_of_scope / ambiguous → refuse (no URL)
     │    └── factual ──────────────────────────────────────────┐
     │                                                          │
     ├─ Phase 3.2.1 ─────────► Route (fund_id, section_type)   │
     │                                                          │
     ├─ Phase 3.2.2 ─────────► Retrieve (FAISS + filters)      │ factual
     │                                                          │ path
     ├─ Phase 3.5 ───────────► Generate (Groq LLM / fallback)  │
     │                                                          │
     └─ Phase 3.6 ───────────► Postprocess (citation + limit) ─┘
```

---

## Phase 5: User Interface

**Goal:** Provide a minimal, clean, and compliant interface for users.

### 5.1 UI Components

```
┌─────────────────────────────────────────────────────────────────┐
│                   Mutual Fund FAQ Assistant                      │
│              Powered by Groww | Facts-Only Q&A                   │
├─────────────────────────────────────────────────────────────────┤
│  ⚠️  Facts-only. No investment advice.                          │
├─────────────────────────────────────────────────────────────────┤
│  Try asking:                                                    │
│  • "What is the expense ratio of [Scheme Name]?"                │
│  • "What is the ELSS lock-in period?"                           │
│  • "How do I download my capital gains statement?"              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Chat Window]                                                  │
│                                                                 │
│  User: What is the exit load for HDFC Mid Cap Fund?             │
│                                                                 │
│  Assistant: As per ingestion-time data, exit load is 1% if     │
│  redeemed within 1 year. [Source page details below]           │
│  Source: https://groww.in/mutual-funds/hdfc-mid-cap-fund-...   │
│  Last updated from sources: 2026-05-08                         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  [  Ask a question about mutual funds...        ] [Send]        │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Technology Options

| Option           | Stack                          | Use Case                        |
|------------------|--------------------------------|---------------------------------|
| Minimal (MVP)    | Streamlit                      | Quick prototype, internal demo  |
| Web App          | React + FastAPI backend        | Production-ready                |
| CLI              | Python REPL / Click            | Developer testing               |

### 5.3 Required UI Elements

- **Welcome message** — Project name, purpose, disclaimer
- **3 example questions** — Pre-populated clickable suggestions
- **Disclaimer badge** — Always visible: _"Facts-only. No investment advice."_
- **Source citation** — Displayed below every answer
- **Last updated footer** — Appended to every response

---

## Phase 6: Testing & Validation

**Goal:** Assess retrieval quality, response faithfulness, and refusal robustness before deployment. Targets below are aspirational; actual scores depend on corpus coverage and model behaviour.

### 6.1 Test Suite Structure

```
tests/
├── unit/
│   ├── test_chunking.py          # Chunk size, overlap, metadata
│   ├── test_embedding.py         # Embedding shape, non-null
│   ├── test_retrieval.py         # Top-K correctness, metadata filter
│   └── test_postprocessor.py     # 3-sentence limit, citation format
├── integration/
│   ├── test_rag_pipeline.py      # End-to-end query → answer
│   └── test_refusal_handler.py   # Advisory query → refusal response
└── eval/
    ├── factual_qa_eval.csv        # Ground-truth Q&A pairs
    └── eval_runner.py             # Precision / faithfulness scoring
```

### 6.2 Evaluation Metrics

| Metric               | Description                                                    | Aspirational Target |
|----------------------|----------------------------------------------------------------|---------------------|
| Retrieval Precision  | Relevant chunk retrieved for a given factual query             | ≥ 90%               |
| Answer Faithfulness  | Response grounded in retrieved context; no extrapolation       | ≥ 95%               |
| Citation Presence    | Source URL appended to every response                          | ≥ 99%               |
| Refusal Coverage     | Advisory / out-of-scope queries correctly deflected            | ≥ 95%               |
| Response Length      | Responses within the 3-sentence limit after post-processing    | ≥ 99%               |

### 6.3 Test Query Categories

- **Factual (should answer):** Expense ratio, exit load, SIP minimum, lock-in period, riskometer, benchmark index, statement download
- **Advisory (should refuse):** "Should I invest?", "Which fund is better?", "What will the returns be?"
- **Out-of-scope (should deflect):** Unrelated financial topics, stock market queries, PII inputs

---

## Phase 7: Deployment & Operations

**Goal:** Make the system reproducible, maintainable, and compliant.

### 7.1 System Architecture (Deployment)

```
┌──────────────────────────────────────────────────────────────┐
│                        Deployment Stack                       │
│                                                              │
│  ┌────────────┐    ┌─────────────┐    ┌────────────────┐    │
│  │  Frontend  │    │   Backend   │    │  Vector Store  │    │
│  │ (Streamlit │───►│  (FastAPI)  │───►│  (ChromaDB /   │    │
│  │  / React)  │    │             │    │   FAISS /      │    │
│  └────────────┘    └──────┬──────┘    │   Pinecone)    │    │
│                           │           └────────────────┘    │
│                           ▼                                  │
│                    ┌─────────────┐                           │
│                    │  LLM API    │                           │
│                    │ (OpenAI /   │                           │
│                    │  Local LLM) │                           │
│                    └─────────────┘                           │
└──────────────────────────────────────────────────────────────┘
```

### 7.2 Corpus Refresh Strategy

> The **14 Groww URLs are fixed** — no new URLs are added during refresh. The scheduled job only re-fetches the same pages to pick up content updates (e.g., NAV changes, expense ratio updates, new exit load rules). Scheduling is handled via **GitHub Actions** (see §7.4).

```
GitHub Actions — weekly schedule (or manual trigger)
       │
       ▼
  Re-fetch the same 14 Groww URLs (no new URLs added)
       │
       ▼
  Phase 1.6: Diff SHA-256 hashes vs. scrape_log.prev.json
       │
  ┌────┴────────┐
  │ Changed?    │
  │ Yes  │  No  │
  ▼            ▼
Re-scrape     Skip Phase 2
Re-chunk      Commit nothing
Re-embed
Re-index
Commit updated HTML +
parquet + scrape_log
to corpus/ branch
```

### 7.3 Project Directory Structure

```
mutual-fund-faq-assistant/
├── corpus/
│   ├── raw/                   # Scraped HTML files (14 files, one per fund)
│   ├── processed/             # Cleaned and extracted text files
│   └── sources.json           # URL manifest with ingestion-time metadata
├── ingestion/
│   ├── scraper.py             # Web scraper (HTML only — no PDF downloads)
│   ├── extractor.py           # Text extraction from HTML
│   ├── chunker.py             # Chunking logic
│   └── indexer.py             # Embedding + vector store indexing
├── rag/
│   ├── retriever.py           # Query embedding + vector search
│   ├── reranker.py            # Optional cross-encoder reranker
│   ├── generator.py           # LLM prompt + response generation
│   └── postprocessor.py       # Citation injection, length enforcement
├── pipeline/
│   ├── classifier.py          # Intent / query classification
│   ├── refusal_handler.py     # Refusal response logic
│   └── pipeline.py            # Orchestrates end-to-end query flow
├── ui/
│   └── app.py                 # Streamlit / FastAPI UI
├── tests/
│   ├── unit/
│   ├── integration/
│   └── eval/
├── .env.example               # API keys template (never commit secrets)
├── requirements.txt
└── README.md
```

### 7.4 GitHub Actions: Automated Corpus Refresh

**Goal:** Automatically keep the corpus up-to-date by re-scraping all 14 Groww fund pages on a schedule, running change detection, and re-ingesting only when content has changed. The workflow also supports a manual one-click trigger for on-demand refreshes.

#### 7.4.1 Workflow Triggers

| Trigger | When |
|---------|------|
| `schedule: cron` | Every Sunday at 02:00 UTC (weekly cadence — balances freshness vs. Groww rate-limit courtesy) |
| `workflow_dispatch` | Manual trigger from the GitHub Actions UI (for on-demand refresh or testing) |

#### 7.4.2 Workflow Steps

```
┌─────────────────────────────────────────────────────────────┐
│         .github/workflows/corpus_refresh.yml                │
│                                                             │
│  1. Checkout repo (fetch full history)                      │
│  2. Set up Python 3.11                                      │
│  3. pip install -r requirements.txt                         │
│  4. Run scripts/run_phase1.py                               │
│       └─ Phase 1.1–1.5: fetch + validate + scrape_log      │
│  5. Run Phase 1.6 change detection                          │
│       └─ compare hashes vs. scrape_log.prev.json           │
│  6. If any_changed == false → exit 0 (no-op)               │
│  7. If any_changed == true:                                 │
│       └─ Run scripts/run_phase2.py                          │
│            └─ Phase 2.1–2.4: extract → chunk → embed       │
│                              → parquet → ChromaDB          │
│  8. Commit changed files to the corpus-refresh branch       │
│       corpus/raw/*.html                                     │
│       corpus/raw/scrape_log.json                            │
│       corpus/raw/scrape_log.prev.json                       │
│       corpus/processed/chunks.parquet                       │
│       corpus/processed/chunks.jsonl                         │
│  9. Open a PR into main (or auto-merge if CI passes)        │
└─────────────────────────────────────────────────────────────┘
```

#### 7.4.3 Workflow YAML (reference design)

```yaml
# .github/workflows/corpus_refresh.yml
name: Corpus Refresh

on:
  schedule:
    - cron: "0 2 * * 0"   # Every Sunday at 02:00 UTC
  workflow_dispatch:        # Manual trigger

jobs:
  refresh:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Phase 1 — Scrape & validate
        run: python scripts/run_phase1.py

      - name: Phase 1.6 — Change detection
        id: change_detect
        run: |
          python - <<'EOF'
          import json, sys
          from ingestion.phase1.change_detector import detect_changes
          from pathlib import Path
          log = json.loads(Path("corpus/raw/scrape_log.json").read_text())
          prev = Path("corpus/raw/scrape_log.prev.json")
          report = detect_changes(log, prev)
          print(f"any_changed={report['any_changed']}")
          Path("change_report.json").write_text(json.dumps(report, indent=2))
          sys.exit(0 if report["any_changed"] else 2)
          EOF
        continue-on-error: true   # exit 2 = unchanged; handled below

      - name: Phase 2 — Re-ingest (only if changed)
        if: steps.change_detect.outcome == 'success'
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          EMBEDDING_MODEL: ${{ vars.EMBEDDING_MODEL || 'all-MiniLM-L6-v2' }}
        run: python scripts/run_phase2.py

      - name: Commit updated corpus artifacts
        if: steps.change_detect.outcome == 'success'
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git checkout -b corpus-refresh-${{ github.run_id }}
          git add corpus/raw/ corpus/processed/chunks.parquet \
                  corpus/processed/chunks.jsonl change_report.json
          git commit -m "chore: corpus refresh $(date -u '+%Y-%m-%d')"
          git push origin corpus-refresh-${{ github.run_id }}

      - name: Open Pull Request
        if: steps.change_detect.outcome == 'success'
        uses: peter-evans/create-pull-request@v6
        with:
          branch: corpus-refresh-${{ github.run_id }}
          title: "chore: automated corpus refresh — ${{ github.run_id }}"
          body: |
            Automated corpus refresh triggered by GitHub Actions.
            See `change_report.json` for per-fund change summary.
          labels: corpus-refresh, automated
```

#### 7.4.4 Secrets & Variables

| Name | Type | Purpose |
|------|------|---------|
| `OPENAI_API_KEY` | Secret | Required only if `EMBEDDING_MODEL=text-embedding-3-small` |
| `EMBEDDING_MODEL` | Variable | Override embedding model (default: `all-MiniLM-L6-v2`) |

> **Note:** When using the local `all-MiniLM-L6-v2` model no API key is needed.
> The model is automatically downloaded from HuggingFace on first run and cached
> by the `actions/setup-python` pip cache step on subsequent runs (if
> `HF_HOME` is pointed at a cached directory).

#### 7.4.5 Integration with Phase 1.6

Phase 1.6 (`change_detector.py`) is the gate that decides whether Phase 2 runs at all. The exit-code convention keeps the workflow YAML clean:

| Phase 1.6 exit code | Meaning | Workflow action |
|---------------------|---------|----------------|
| `0` | Changes detected | Run Phase 2, commit, open PR |
| `2` | Corpus unchanged | Skip Phase 2, no commit, no PR |
| `1` | Unexpected error | Workflow fails, GitHub sends alert email |

---

## Technology Stack Summary

| Component            | Recommended Tool / Library                      |
|----------------------|-------------------------------------------------|
| HTML Scraping        | `requests`, `BeautifulSoup4`                    |
| Chunking             | `LangChain RecursiveCharacterTextSplitter`      |
| Embeddings           | `text-embedding-3-small` (OpenAI) or `sentence-transformers` |
| Vector Store         | `ChromaDB` (local dev), `FAISS` (lightweight), `Pinecone` (prod) |
| LLM                  | `llama-3.1-8b-instant` via **Groq** (primary); `GPT-4o-mini` (OpenAI fallback) |
| Reranker             | `cross-encoder/ms-marco-MiniLM-L-6-v2`         |
| Orchestration        | `LangChain` or custom Python                    |
| UI                   | `Streamlit` (MVP) or `React + FastAPI`          |
| Testing              | `pytest`, `RAGAS` (RAG evaluation)              |
| Deployment           | `Docker`, `Railway` / `Render` / `AWS Lambda`   |
| Scheduling / Refresh | `GitHub Actions` (weekly cron + manual trigger) |

---

## Phase Summary Table

| Phase | Name                             | Key Output                                                          |
|-------|----------------------------------|---------------------------------------------------------------------|
| **0** | **AMC & Scheme Selection**       | `sources.json` with 14 HDFC fund URLs + metadata                   |
| 1     | Corpus Collection                | `corpus/raw/` — 14 scraped HTML files from Groww (fixed, closed corpus) |
| 2     | Data Processing & Indexing       | Chunked text + persisted vector index (ChromaDB / FAISS)            |
| 3     | RAG Core (Retrieval + Generation)| Working Q&A pipeline with citations                                 |
| 4     | Query Classification & Refusal   | Intent guard + compliant refusal responses                          |
| 5     | User Interface                   | Streamlit / web app with disclaimer                                 |
| 6     | Testing & Validation             | Test suite + evaluation metrics                                     |
| 7     | Deployment & Operations          | Dockerized app + GitHub Actions corpus refresh (§7.4)               |

---

*This architecture is designed to prioritise source-grounded, snapshot-based responses and transparent sourcing. All financial values are ingestion-time data. The system does not guarantee real-time accuracy and is not a substitute for official AMC, AMFI, or SEBI publications.*
