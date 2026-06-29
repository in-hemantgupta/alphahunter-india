# Alpha Hunter - Development Progress

## Project Overview
Implementation of FGQMATL 7-layer scoring and 8-stage elimination architecture for the QuantumAlpha pipeline.

## Current Status: In Progress

---

## Latest Update (2026-06-29)

### Database Caching for Scored Stocks ✅
- **Issue**: `/stocks/scored` endpoint was re-scoring stocks on-the-fly, causing slow responses and inconsistent data
- **Solution**: Implemented database caching system
  - Created `ScoredStock` model to store scored stocks with all metrics
  - Modified pipeline to save scored stocks to database after processing
  - Updated all endpoints (`/stocks/scored`, `/portfolio/current`, `/signals/latest`) to read from database cache
  - Added `/scan/status` endpoint to check pipeline status and last run time
- **Results**:
  - Pipeline now saves 745 scored stocks to database
  - Endpoints return data instantly from cache (no re-scoring)
  - All 2394 stocks visible on UI with scores for those that passed elimination
  - Score range: 0.00 - 36.91

### Pipeline Running: Scoring All 2394 Stocks
- **Status**: Backend is actively processing all stocks
- **Universe Size**: 2394 stocks (up from 2388)
- **Price Records**: 1,073,088
- **Current Scored**: 745 stocks passed elimination and saved to database
- **Issue**: yfinance rate limiting causing delays, but pipeline continues

### Issues Fixed
1. **Universe Page**: Now shows all 2394 stocks (was showing only 68 scored stocks)
2. **Pipeline Scope**: Now processes all stocks in universe (was limited to 500)
3. **Financial Ingestion**: Now fetches for all stocks with price data (was limited to 100)
4. **Score Caching**: Scores now stored in database and served from cache (was re-scoring on every request)

---

## Completed Tasks

### 1. Nifty Benchmark Caching ✅
- **Issue**: Nifty benchmark fetch was called per stock, causing redundant API calls
- **Fix**: Added global cache (`_nifty_return_cache`) in `pipeline.py`
- **Impact**: Drastically reduced yfinance API calls during batch scoring

### 2. Quarterly Financials Ingestion ✅
- **Issue**: Only 244 quarterly records in DB (out of 2381 stocks)
- **Fix**: Ingested quarterly financials for additional 189 stocks
- **Result**: DB now has 1262 quarterly records

### 3. Delivery Ratio Estimation ✅
- **Issue**: Delivery ratio was hardcoded to 1.0
- **Fix**: Implemented `_calculate_delivery_ratio` using volume/price patterns
- **Logic**: High volume + small price move = accumulation (higher delivery ratio)

### 4. Missing Scoring Fields ✅
- **Issue**: Many FGQMATL scoring fields were not populated
- **Fix**: Added population of missing fields in `get_stock_data_for_scoring`:
  - `volume_high`, `price_flat`, `vwap_defense`, `price_compression`
  - `seller_exhaustion`, `bulk_deal_positive`, `promoter_declining`
  - `auditor_changed`, `dilution_rate`, `cash_conversion`
  - `governance_red_flags`, `roce_trend`, `capex_efficiency`
- **Result**: FGQMATL scoring engine now calculates non-zero sub-scores

### 5. Stock Processing Limit ✅
- **Issue**: Pipeline only processed 100 stocks
- **Fix**: Increased limit from 100 to 500 in `main.py` endpoints
- **Endpoints Updated**:
  - `/stocks/scored`
  - `/portfolio/current`
  - `/signals/latest`

### 6. Elimination Pipeline Verification ✅
- **Test Results** (50 stocks sample):
  - 11 passed elimination
  - 39 failed:
    - Fundamental: 20 failures
    - Liquidity: 14 failures
    - Growth: 5 failures
- **ROCE Threshold**: Relaxed from 10% to 5% in `elimination.py`

### 7. Portfolio Endpoint Verification ✅
- **Result**: `/portfolio/current` returns top 10 stocks with real scores
- **Example**: PPAP: 16.20, VADILALIND: 13.06, GRAUWEIL: 12.88

### 8. Force Re-scoring Capability ✅
- **Issue**: Pipeline skipped stocks that already had price data
- **Fix**: Added `force` parameter to `run_full_pipeline()`
- **Endpoint**: `/scan/run?force=true` now re-ingests all data

---

## In Progress Tasks

### 9. Universe Page Data Fix 🔄
- **Issue**: Universe page shows 0 values for score, returns, volume ratio
- **Root Cause**: Page calls `/stocks` which only returns symbol and company_name
- **Fix**: Update Universe.tsx to call `/stocks/scored` instead
- **Status**: Fix applied, needs verification

### 10. Score All 500 Stocks 🔄
- **Issue**: Only 71 stocks scored (out of 500 processed)
- **Action**: Run pipeline with `force=true` to re-score all stocks
- **Status**: Pipeline ready to run

---

## Pipeline Results (Latest)

### Scan Summary
- **Processed**: 6 stocks (new ingestion)
- **Skipped**: 494 stocks (already had price data)
- **Passed Elimination**: 71 stocks
- **Eliminated**: 2312 stocks
- **Ranked**: 30 stocks (top 30 returned)

### Top 10 Stocks
1. PPAP - Score: 16.20
2. VADILALIND - Score: 13.06
3. GRAUWEIL - Score: 12.88
4. DWARKESH - Score: 12.77
5. KIRLPNU - Score: 12.62
6. SHAKTIPUMP - Score: 12.52
7. AARTECH - Score: 12.09
8. HEROMOTOCO - Score: 11.87
9. NAUKRI - Score: 11.61
10. NCLIND - Score: 11.36

### Portfolio Allocation (Top 10)
- Total Weight: 100.01%
- PPAP: 12.76% (Score: 16.20)
- VADILALIND: 10.29% (Score: 13.06)
- GRAUWEIL: 10.14% (Score: 12.88)
- DWARKESH: 10.06% (Score: 12.77)
- KIRLPNU: 9.94% (Score: 12.62)

---

## Architecture Details

### FGQMATL Scoring Weights
- **F** (Fundamental): 0.18
- **G** (Growth): 0.20
- **Q** (Quality): 0.18
- **M** (Momentum): 0.14
- **A** (Accumulation): 0.10
- **T** (Technical): 0.08
- **L** (Liquidity): 0.12

### 8-Stage Elimination Pipeline
1. **Liquidity Filter**: Min volume, market cap requirements
2. **Fundamental Filter**: ROCE > 5%, D/E < 2, positive net worth
3. **Growth Filter**: Revenue growth, profit growth
4. **Quality Filter**: Margin stability, cash conversion
5. **Momentum Filter**: Price trends, relative strength
6. **Accumulation Filter**: Delivery ratio, bulk deals
7. **Technical Filter**: VWAP defense, price compression
8. **Alternative/LLM Filter**: Permissive (dummy scores)

### Database Schema
- **Stocks Table**: 2381 stocks
- **Quarterly Financials**: 1262 records (composite PK: symbol, quarter)
- **Shareholding Pattern**: Populated for scored stocks
- **Price History**: 500 stocks with OHLCV data

---

## API Endpoints

### Core Endpoints
- `GET /stocks` - Basic stock list (symbol, company_name only)
- `GET /stocks/scored?limit=500` - Scored stocks with full metrics
- `GET /stocks/universe` - All stocks in database
- `GET /stock/{symbol}` - Individual stock details with score
- `GET /portfolio/current` - Top 10 portfolio with allocations
- `GET /signals/latest` - Top 50 stocks with signals
- `GET /scan/run?force=true` - Run full pipeline (force re-ingestion)
- `GET /scan/history` - Historical portfolio snapshots
- `GET /rebalancing` - Rebalancing history

---

## Technical Stack

### Backend
- **Framework**: FastAPI
- **Database**: SQLite (stocks.db)
- **Data Source**: yfinance for price/financial data
- **Scoring**: Custom FGQMATL engine with numpy/pandas

### Frontend
- **Framework**: React + TypeScript
- **Build Tool**: Vite
- **Charts**: Recharts
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios

### Ports
- Backend: `:8001`
- Frontend: `:5174`

---

## Known Issues & TODOs

### High Priority
- [ ] Verify Universe page shows scores after fix
- [ ] Score all 500 stocks with force=true
- [ ] Increase `/stocks/scored` limit to return all scored stocks (currently capped at 100)

### Medium Priority
- [ ] Ingest quarterly data for remaining ~2000 stocks
- [ ] Wire up actual data sources for Alternative (Stage 6) and LLM (Stage 7)
- [ ] Add error handling for yfinance API failures
- [ ] Implement caching for scored stocks to avoid recalculation

### Low Priority
- [ ] Add stock sector/industry classification
- [ ] Implement portfolio rebalancing alerts
- [ ] Add historical score tracking
- [ ] Create admin dashboard for pipeline monitoring

---

## Next Steps
1. Verify Universe page displays scores correctly
2. Run `/scan/run?force=true` to score all 500 stocks
3. Update `/stocks/scored` endpoint to return all scored stocks (not just top 100)
4. Test all frontend pages with real data
5. Document API usage for future development

---

**Last Updated**: 2026-06-29
**Session Status**: Active development
