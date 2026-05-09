"""
ingestion — Data collection and processing pipeline

Package structure
-----------------
phase1/     Phase 1: Corpus definition & data collection
  manifest.py   (1.1) Load & validate sources.json        ✔ implemented
  session.py    (1.2) Configure HTTP scraper session       [stub]
  fetch.py      (1.3) Fetch & save raw HTML               [stub]
  integrity.py  (1.4) De-duplicate & integrity check      [stub]
  scrape_log.py (1.5) Write scrape log                    [stub]

phase2/     Phase 2: Data processing & indexing
  extractor.py  (2.1) Text extraction & cleaning          [stub]
  chunker.py    (2.2) Chunking with metadata              [stub]
  embedder.py   (2.3) Embedding generation                [stub]
  indexer.py    (2.4) Vector store indexing               [stub]
"""
