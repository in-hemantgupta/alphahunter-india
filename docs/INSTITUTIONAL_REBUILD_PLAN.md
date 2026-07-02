# QuantumAlpha India — Institutional Rebuild Plan

**Status:** Planning document only. No code has been changed. Confirm before Phase 1 execution.
**Grounded in:** live code audit (2026-07-02), not the aspirational docs. `docs/system_architecture.md` and `docs/RESEARCH_BIBLE.md` describe a system that does not match what's running — treat both as design intent, not current state.

---

## 0. What's actually fake right now (audit findings)

| Area | File:line | Reality |
|---|---|---|
| Pledge % | `app/ingestion/shareholding_ingestor.py:60,68` | Hardcoded `0`. No source. |
| FII/DII % | `app/ingestion/shareholding_ingestor.py:23-24,34-37` | String-matched off yfinance `major_holders` — not NSE/BSE filings. |
| `governance_clean` | `app/services/pipeline.py:477` | Hardcoded `True`. |
| `auditor_changed` | `app/services/pipeline.py:313` | Hardcoded `False`. |
| `dilution_rate` | `app/services/pipeline.py:314` | Hardcoded `0`. |
| `delivery_ratio` | `app/services/pipeline.py:102-122` | Volume/price heuristic, not NSE/BSE delivery archive. |
| `sector_rotation_score`, `search_trend_score` | `app/alternative_data/alternative_data_engine.py:15-16` | Hardcoded `50` default, no ingestion. |
| `contract_score`, `shipment_score` | `app/alternative_data/{government_contracts,import_export_tracker}.py` | Threshold stubs on inputs nothing populates. |
| `patent_score` | `app/alternative_data/alternative_data_engine.py:3` | Imports a module that doesn't exist — dead code path. |
| Missing-data handling | `app/scoring/quality_score.py:25,38-41`, `management_score.py`, `pipeline.py:429` | `(x or 0)` everywhere — missing data silently becomes a bad score instead of `None`/excluded. |
| Backtest universe | `scripts/portfolio_backtest.py:40,83-88` | No `is_active`/`delisted` field on `Stock` — survivorship-biased by construction. |
| Live alpha formula | `app/scoring/alpha_engine.py:21-26` | Only 4 layers actually wired into `LAYER_WEIGHTS` (growth 35%, technical 30%, forensic 25%, value 10%). `quality`, `management`, `microstructure`, `lowvol` scores are computed but **never used**. This contradicts both docs. |
| LLM layer | `app/llm_engine/groq_client.py` | This one is real — genuine Groq API call, cached in `LLMAnalysis`. Keep it, harden it. |
| FCF | `app/ingestion/financial_ingestor.py:258-262` | Real — sourced field, not a PAT proxy. Keep it. |

Net: roughly a third of what the docs claim is real, real. The rest is stub, heuristic, or dead code presented as a working layer. This is the actual starting point.

---

## 1. Architecture

Keep the shape that already exists (ingestion → DB → factor engine → portfolio → execution/monitoring) — it's the right shape. The rebuild is about making each box honest, not inventing a new topology.

```
                    ┌─────────────────────────────────────────┐
                    │           INGESTION LAYER                │
                    │  each source = own module, own health    │
                    │  row, own confidence score                │
                    └─────────────────────────────────────────┘
   NSE bhavcopy ──┐        NSE/BSE shareholding filings ──┐
   Yahoo (fallback)├─Price │  SEBI insider disclosures ────┤─Ownership/Insider
                   │       │                                │
   Screener.in ────┤       BSE/NSE PDF filings ─────────────┤─Fundamentals
   NSE/BSE filings │                                        │
   (fallback) ─────┘       NSE/BSE delivery+bulk archives ──┤─Microstructure
                                                              │
                    ┌─────────────────────────────────────────┐
                    │        RAW DATA STORE (point-in-time)     │
                    │  append-only, never overwritten,           │
                    │  every row has source+confidence+ts         │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────────────────────────────┐
                    │           FACTOR ENGINE                    │
                    │  Factor{raw, normalized, confidence,        │
                    │  freshness, source} — factors independent   │
                    │  dynamic weight redistribution on NULL       │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────────────────────────────┐
                    │      BACKTEST ENGINE (point-in-time)       │
                    │  full historical universe incl. delisted    │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────────────────────────────┐
                    │        PORTFOLIO ENGINE V2                 │
                    │  constrained optimizer + drawdown breaker    │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────────────────────────────┐
                    │   EXECUTION SIM → MONITORING → AUDIT LOG   │
                    └─────────────────────────────────────────┘
```

**Core design rule that fixes most of the audit findings at once:** every ingested field is written as `(value, source, confidence, as_of_date, fetched_at)`, never a bare scalar. A factor computed from a field with no row → `None`. A layer with `coverage < 30%` of its inputs present → excluded from the composite, and its weight is redistributed proportionally across the remaining active layers (this redistribution logic — `_score_layer` in `alpha_engine.py` — already exists and works; it's the pattern to extend everywhere, not reinvent).

---

## 2. Database schema redesign

Keep existing tables that are genuinely point-in-time and additive (`price_history`, `score_snapshot`, `rebalance_history`, `system_audit_log` — these are fine). Redesign the ones that currently overwrite or fake data.

```sql
-- Provenance is a first-class column set on every fundamental/ownership table, not bolted on.

CREATE TABLE shareholding_pattern (
    symbol            VARCHAR(20) NOT NULL,
    quarter           VARCHAR(10) NOT NULL,   -- filing quarter, not fetch date
    promoter_pct      NUMERIC,                 -- NULL if unavailable
    promoter_pledge_pct NUMERIC,
    fii_pct           NUMERIC,
    dii_pct           NUMERIC,
    retail_pct        NUMERIC,
    source            VARCHAR(50) NOT NULL,    -- 'nse_filing' | 'bse_filing'
    confidence         NUMERIC NOT NULL,        -- 0-1, based on parse quality
    filing_date        DATE,
    fetched_at         TIMESTAMP NOT NULL,
    PRIMARY KEY (symbol, quarter)
);
-- No 'yfinance_estimate' source value permitted for this table.

CREATE TABLE insider_transactions (
    id               SERIAL PRIMARY KEY,
    symbol           VARCHAR(20) NOT NULL,
    transaction_date DATE NOT NULL,
    person_name      VARCHAR(200),
    person_category  VARCHAR(50),   -- promoter | director | kmp | designated_person
    transaction_type VARCHAR(10),   -- buy | sell
    quantity         BIGINT,
    value_inr        NUMERIC,
    source           VARCHAR(50) NOT NULL,  -- 'sebi_pit_disclosure'
    disclosure_url   TEXT,
    fetched_at       TIMESTAMP NOT NULL
);

CREATE TABLE quarterly_financials (
    symbol            VARCHAR(20) NOT NULL,
    quarter           VARCHAR(10) NOT NULL,
    revenue           NUMERIC, pat NUMERIC, ebitda NUMERIC,
    cfo               NUMERIC, capex NUMERIC,       -- FCF derived, never stored as a proxy
    debt              NUMERIC, equity NUMERIC,
    total_assets      NUMERIC, total_liabilities NUMERIC,
    shares_outstanding BIGINT,
    source            VARCHAR(50) NOT NULL,   -- 'screener' | 'nse_filing' | 'bse_filing'
    confidence        NUMERIC NOT NULL,
    restated          BOOLEAN DEFAULT FALSE,   -- flag restatements, never overwrite history
    fetched_at        TIMESTAMP NOT NULL,
    PRIMARY KEY (symbol, quarter, source)      -- multiple sources can coexist; engine picks highest-confidence
);

CREATE TABLE delivery_data (
    symbol       VARCHAR(20) NOT NULL,
    date         DATE NOT NULL,
    delivery_qty BIGINT,
    total_qty    BIGINT,
    delivery_pct NUMERIC,           -- computed from real archive, never estimated
    source       VARCHAR(20) NOT NULL DEFAULT 'nse_bhavcopy_delivery',
    PRIMARY KEY (symbol, date)
);

CREATE TABLE bulk_deals (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20), deal_date DATE, client_name VARCHAR(200),
    deal_type VARCHAR(10),          -- buy | sell
    quantity BIGINT, price NUMERIC,
    source VARCHAR(20)              -- 'nse' | 'bse'
);

CREATE TABLE factor_values (
    id             SERIAL PRIMARY KEY,
    symbol         VARCHAR(20) NOT NULL,
    as_of_date     DATE NOT NULL,
    factor_name    VARCHAR(50) NOT NULL,   -- e.g. 'promoter_holding_trend'
    raw_value      NUMERIC,
    normalized_score NUMERIC,               -- 0-100, NULL if raw missing
    confidence     NUMERIC NOT NULL,        -- 0-1
    data_source    VARCHAR(50),
    data_freshness_days INTEGER,
    UNIQUE (symbol, as_of_date, factor_name)
);
-- This table replaces the current pattern of dumping factor inputs as loose
-- columns on ScoreSnapshot. It's what makes every score auditable and
-- reproducible: "why was this stock's management_score 62 on this date"
-- becomes one query, not a code read.

CREATE TABLE stocks_master (
    symbol VARCHAR(20) PRIMARY KEY,
    company_name VARCHAR(200), sector VARCHAR(100), exchange VARCHAR(10),
    listing_date DATE,
    delisting_date DATE,             -- NULL if still listed
    status VARCHAR(20) NOT NULL DEFAULT 'active'  -- active | delisted | suspended
);
-- The single field that fixes survivorship bias: backtests query
-- "what was in stocks_master with status valid as-of date X", not
-- "what's in stocks_master today".
```

Everything else (`price_history`, `score_snapshot`, `portfolio_position`, `rebalance_history`, `fund_nav`, `system_audit_log`) stays structurally as-is — they're already append-only and point-in-time correct.

---

## 3. Module dependency graph

```
ingestion/
  price/          nse_bhavcopy.py, yahoo_fallback.py, corporate_actions.py
  fundamentals/   screener_scraper.py, nse_filing_parser.py, bse_filing_parser.py
  ownership/      nse_shareholding_parser.py, bse_shareholding_parser.py
  insider/        sebi_pit_scraper.py
  microstructure/ nse_delivery_archive.py, bulk_block_deals.py
  documents/      bse_pdf_archive.py, annual_report_fetcher.py, transcript_fetcher.py
       │
       ▼ (each writes to its own table, stamped with source+confidence+ts — never touches another module's table)
       │
factors/
  base.py                 → Factor dataclass {raw, normalized, confidence, freshness, source}
  profitability.py         → roce, roe, gross_margin_stability, asset_turnover
  cashflow.py               → cfo_growth, fcf, cash_conversion
  leverage.py                → debt_equity, interest_coverage
  growth.py                   → revenue/pat/ebitda acceleration
  management.py                → promoter_trend, pledge_trend, insider_buying, dilution
  governance.py                  → auditor_changes, rpt_ratio, comp_ratio
  microstructure.py                → delivery signals, bulk deal signals, vwap/atr
  llm/                               → concall/annual-report structured scoring (existing groq_client, extended)
       │
       ▼ (factors are read-only inputs to composite.py — never write to each other)
       │
scoring/
  composite.py       → weight redistribution on NULL factors (extends existing _score_layer pattern)
  elimination.py      → multi-stage reject pipeline
       │
       ▼
backtest/
  universe.py           → point-in-time universe incl. delisted (reads stocks_master.status as-of date)
  engine.py               → walk-forward, monthly rebalance, cost model
  montecarlo.py             → regime-conditioned resampling
       │
       ▼
portfolio/               (mostly exists already — optimizer.py, regime.py, position_sizing.py,
                           exit_rules.py, kill_switch.py — extend, don't replace)
       │
       ▼
monitoring/ + audit/     (exists — audit_logger.py, data_freshness.py, data_health_monitor.py — extend)
```

Rule enforced by this graph: `ingestion` never imports from `factors`; `factors` never import from `scoring`; nothing downstream can reach back and mutate an upstream table. This is what "no factor can affect another" (Phase 3 requirement) actually means structurally.

---

## 4. Build roadmap

Realistic sequencing for a single senior engineer (you + me), assuming this runs alongside a still-functioning (if partially fake) live shadow fund that shouldn't go dark mid-migration.

| Phase | Scope | Depends on | Est. |
|---|---|---|---|
| **0** | Add provenance columns (source/confidence/fetched_at) to existing tables without changing values yet. Add `stocks_master.status` + backfill delisting dates for currently-known delisted NSE names. | — | 3-4 days |
| **1** | Delete/neutralize the fake paths from the audit table above. Each hardcoded field → `NULL` + factor drops out + weight redistributes. This will drop average scores and shrink the passing universe — expected and correct, not a regression. | Phase 0 | 3-5 days |
| **2A** | Real shareholding ingestion (NSE/BSE quarterly shareholding pattern filings — these are structured XBRL/CSV on nseindia.com and bseindia.com, not scraped HTML). Replaces `shareholding_ingestor.py`'s yfinance guess entirely. | Phase 0 | 1-1.5 wk |
| **2B** | Real NSE delivery archive ingestion (daily delivery bhavcopy, publicly downloadable). Replaces the volume heuristic. | Phase 0 | 3-5 days |
| **2C** | SEBI insider (PIT) disclosure ingestion. This is the hardest real-data phase — no clean bulk API, requires parsing exchange disclosure PDFs/HTML per-filing. | Phase 0 | 1.5-2 wk |
| **2D** | Bulk/block deal ingestion (NSE/BSE publish daily CSV — straightforward). | Phase 0 | 2-3 days |
| **3** | Factor engine rewrite: `Factor` dataclass, per-factor confidence/freshness, dynamic weight redistribution generalized beyond the current single `_score_layer` function. | Phase 1, 2A-D | 1.5 wk |
| **4** | Alternative data: hiring (already has a real freehire.dev integration — harden it), fix or delete the broken patent_score import, government tenders via GeM/CPPP (public but unstructured — realistically the lowest-ROI item here, consider deprioritizing vs. everything else), drop `sector_rotation_score`/`search_trend_score` to NULL until real sources exist. | Phase 3 | 1 wk (excl. tenders), +1-2wk if tenders pursued |
| **5** | LLM pipeline: extend the existing real Groq integration — add PDF extraction (annual reports, BSE archive) → chunk → embed → structured extraction, quarter-over-quarter narrative diff. The API call already works; this phase is document acquisition + chunking + a proper eval set to check extraction quality. | Phase 3 | 1.5-2 wk |
| **6** | Backtest rebuild: point-in-time universe query using `stocks_master.status`, walk-forward with real cost/slippage model (execution.py cost model already exists — reuse), Monte Carlo + regime splits. | Phase 0, 3 | 1.5-2 wk |
| **7** | Portfolio engine hardening: sector cap 15%, portfolio beta ≤0.9, drawdown circuit breaker at 15% (currently 20% kill-switch threshold — tighten and add the auto-deleverage step, not just a hard stop). Mostly parameter/constraint changes to existing `optimizer.py`/`kill_switch.py`. | Phase 3 | 3-5 days |
| **8** | Infra hardening: timeout+retry+backoff+circuit-breaker decorator applied uniformly across all ingestion modules (some already have circuit breakers — e.g. Screener — generalize the pattern into one decorator, apply everywhere). | Ongoing, can run parallel to 2A-D | 3-4 days |

**Total: roughly 11-14 weeks of focused solo engineering**, not counting time lost to data-source friction (NSE/BSE anti-scraping measures, SEBI disclosure format inconsistency across companies — this is the actual dominant risk, not the code).

---

## 5. Engineering estimate

| Phase | Days (single engineer) |
|---|---:|
| 0 — Provenance scaffolding | 3-4 |
| 1 — Delete fakes, wire NULL propagation | 3-5 |
| 2A-D — Real data ingestion (shareholding, delivery, insider, bulk deals) | 18-24 |
| 3 — Factor engine rewrite | 6-8 |
| 4 — Alternative data (hiring/tenders, drop unfounded scores) | 5-14 |
| 5 — LLM pipeline (docs → chunks → structured scores) | 8-10 |
| 6 — Backtest rebuild + Monte Carlo/regime | 8-10 |
| 7 — Portfolio constraints/circuit breaker | 3-5 |
| 8 — Infra hardening (retry/backoff/circuit breaker everywhere) | 3-4 |
| **Total** | **57-79 working days ≈ 11-16 weeks** |

This assumes: existing DB/infra reused (Postgres, FastAPI, SQLAlchemy — no rewrite), no new team hired, and that NSE/BSE/SEBI sources remain scrapeable at current friction. Add 20-30% contingency for anti-bot changes on exchange sites, which is the single biggest unknown — it has broken this project's Screener scraper before (hence the existing circuit breaker).

**What this estimate does not cover:** any paid data vendor integration (e.g. a licensed NSE/BSE data feed, a commercial fundamentals API). If ₹100Cr deployment readiness requires eliminating scraping risk entirely, budget for a data vendor contract — that's a procurement decision, not an engineering one, and it would cut phases 2A/2B/2D down to integration work (days, not weeks).

---

## 6. Code refactor plan (Phase 1 — concrete, ready to execute)

This is the immediately actionable part — deleting the specific fakes found in the audit, file by file:

1. **`app/services/pipeline.py:313-314`** — delete `auditor_changed = False`, `dilution_rate = 0`. Replace with lookups against new `quarterly_financials`/governance tables; `None` if absent.
2. **`app/services/pipeline.py:477`** — delete `governance_clean = True`. Compute from real auditor-change + RPT data, or `None`.
3. **`app/services/pipeline.py:102-122`** — delete the volume-based `delivery_ratio` heuristic once `delivery_data` table (Phase 2B) is populated; until then, factor returns `None` rather than a fabricated 1.0-3.0 value.
4. **`app/ingestion/shareholding_ingestor.py`** — delete the yfinance string-matching logic entirely (lines 22-37, 60, 68). Replace with `ownership/nse_shareholding_parser.py` + `ownership/bse_shareholding_parser.py` (Phase 2A). Pledge stays `NULL` until that source lands — never `0`.
5. **`app/alternative_data/alternative_data_engine.py:3,15-16`** — remove the broken `patent_tracker` import (dead code, would crash if invoked — confirms it's never actually called end-to-end, another sign this layer is decorative). Remove hardcoded `50` defaults for `sector_rotation_score`/`search_trend_score`; return `None`.
6. **`app/alternative_data/government_contracts.py`, `import_export_tracker.py`** — either wire to a real GeM/CPPP/customs source (Phase 4, low priority) or delete outright and let the factor drop from the composite. Recommend delete-until-real rather than leaving a threshold stub that looks meaningful but isn't.
7. **`app/scoring/quality_score.py:25,38-41`, `app/scoring/management_score.py`** — replace every `(x or 0)` with `(x if x is not None else None)` and push the "insufficient data → layer excluded, weight redistributed" logic (already correct in `alpha_engine._score_layer`) down into these per-factor functions too, so a single missing field doesn't silently zero out a whole layer.
8. **`app/scoring/alpha_engine.py:21-26`** — decide `quality`, `management`, `microstructure`, `lowvol` scores' fate deliberately: either wire them into `LAYER_WEIGHTS` for real (they're computed, just unused) or delete the dead computation. Currently they're neither on nor off — wired code with no effect is worse than either state because it makes the docs lie.
9. **`scripts/portfolio_backtest.py:40,83-88`** — add `stocks_master.status`/`delisting_date` filter (Phase 0) so historical universe includes delisted names as-of each rebalance date, not just currently-active ones.

Each of these is a small, isolated diff once its replacement data source (where one is needed) exists — that's the point of doing Phase 0/2 first. Don't delete a fake before its real replacement is landed, or the shadow fund goes blind on that factor with no signal at all instead of a degraded-but-honest one.

---

## Where I'd push back

- **Alternative data (tenders, patents, Google Trends) is the lowest ROI here.** GeM/CPPP have no clean bulk API, patent search is per-request scraping, Google Trends has aggressive rate limits. This phase will cost real time for factors that get low weight (10% in the current — soon to be redesigned — composite) and were already dummy/stubbed. I'd deprioritize this behind ownership/insider/delivery data, which feed the higher-weighted management and microstructure factors.
- **"10-year history, all NSE equities including delisted" is a data-acquisition project, not a code project.** NSE doesn't publish a clean historical delisted-company dataset; you'll be assembling it from bhavcopy archives + manual reconciliation. Scope this explicitly before committing to a timeline — it's likely the single largest unknown in the whole plan.
- Everything above assumes scraping stays viable. If you want ₹100Cr-grade reliability, the honest fix for #2A/2B/2C/6's biggest risk is a paid data vendor, not more scraper resilience code.

**Next step:** say the word and I'll start Phase 0 (provenance columns + `stocks_master.status` backfill) and Phase 1 (deleting the nine fakes above) — that's the part with no data-source dependency and can start immediately.
