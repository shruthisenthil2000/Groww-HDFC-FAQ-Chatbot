"""
ingestion.phase1 — Phase 1: Corpus Definition & Data Collection

Subphase modules
----------------
manifest        (1.1)  Load & validate corpus/sources.json        ✔ implemented
session         (1.2)  Configure HTTP scraper session             ✔ implemented
fetch           (1.3)  Fetch & save raw HTML                      ✔ implemented
integrity       (1.4)  De-duplicate & integrity check             ✔ implemented
scrape_log      (1.5)  Write scrape log                           ✔ implemented
change_detector (1.6)  Corpus change detection (hash diff)        stub
readiness       (1.7)  Corpus integrity & readiness gate          ✔ implemented

Quick-start
-----------
    from ingestion.phase1 import (
        load_and_validate, build_session, fetch_all,
        verify_raw_corpus, write_scrape_log, check_readiness,
    )

    funds   = load_and_validate()                  # Phase 1.1 — must run first
    session = build_session()                      # Phase 1.2
    results = fetch_all(funds, session)            # Phase 1.3
    verify_raw_corpus(results, funds, raw_dir)     # Phase 1.4 — raises IntegrityError on failure
    write_scrape_log(results, raw_dir)             # Phase 1.5 — writes corpus/raw/scrape_log.json
    check_readiness(funds, raw_dir, processed_dir) # Phase 1.7 — raises ReadinessError if not ready
"""

# Phase 1.1 — manifest validation
from ingestion.phase1.manifest import (  # noqa: F401
    ManifestError,
    load_and_validate,
    load_sources,
    validate_sources,
    GROWW_URL_PREFIX,
    EXPECTED_DOC_TYPE,
    EXPECTED_FUND_COUNT,
    REQUIRED_FUND_FIELDS,
)

# Phase 1.2 — session configuration
from ingestion.phase1.session import (  # noqa: F401
    SESSION_CONFIG,
    build_session,
)

# Phase 1.3 — fetch & save
from ingestion.phase1.fetch import (  # noqa: F401
    FetchResult,
    fetch_and_save,
    fetch_all,
)

# Phase 1.4 — integrity check
from ingestion.phase1.integrity import (  # noqa: F401
    IntegrityError,
    verify_raw_corpus,
    MIN_FILE_SIZE_BYTES,
)

# Phase 1.5 — scrape log
from ingestion.phase1.scrape_log import (  # noqa: F401
    write_scrape_log,
    load_scrape_log,
    SCRAPE_LOG_FILENAME,
)

# Phase 1.7 — corpus integrity & readiness gate
from ingestion.phase1.readiness import (  # noqa: F401
    ReadinessError,
    check_readiness,
    MIN_EXPECTED_CHUNKS,
    REQUIRED_CHUNK_FIELDS,
)
