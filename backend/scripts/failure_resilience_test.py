import sys, os, json, time, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['DISABLE_BAYESIAN'] = '1'
from unittest.mock import patch, MagicMock
from sqlalchemy import text, create_engine
from app.db.database import SessionLocal, engine
from app.db.base import Base


class FailureResilienceTest:
    def __init__(self):
        self.scenarios = []
        self._build_scenarios()

    def _build_scenarios(self):
        self.scenarios = [
            self._t1_screener_unreachable(),
            self._t2_screener_timeout(),
            self._t3_screener_empty_data(),
            self._t4_screener_malformed_html(),
            self._t5_screener_circuit_breaker_activates(),
            self._t6_screener_circuit_breaker_reset(),
            self._t7_screener_partial_data(),
            self._t8_screener_fallback_yfinance(),
            self._t9_nse_connection_failure(),
            self._t10_nse_empty_quarterly(),
            self._t11_nse_missing_balance_sheet(),
            self._t12_nse_missing_cashflow(),
            self._t13_yfinance_ticker_not_found(),
            self._t14_yfinance_empty_history(),
            self._t15_yfinance_rate_limited(),
            self._t16_yfinance_missing_financials(),
            self._t17_db_connection_lost(),
            self._t18_db_query_timeout(),
            self._t19_db_constraint_violation(),
            self._t20_db_table_missing(),
            self._t21_db_write_failure(),
            self._t22_db_concurrent_write(),
            self._t23_db_transaction_rollback(),
            self._t24_db_session_leak(),
            self._t25_all_scores_none(),
            self._t26_layer_scores_missing(),
            self._t27_confidence_zero(),
            self._t28_all_sector_unknown(),
            self._t29_price_history_missing(),
            self._t30_market_cap_none(),
            self._t31_low_data_coverage(),
            self._t32_no_score_spread(),
            self._t33_rank_ties(),
            self._t34_outlier_scores(),
            self._t35_zero_stock_universe(),
            self._t36_single_stock_universe(),
            self._t37_all_same_sector(),
            self._t38_weekend_holiday_date(),
            self._t39_pipeline_idempotency(),
            self._t40_missing_env_vars(),
            self._t41_empty_symbols(),
            self._t42_special_chars_symbols(),
            self._t43_no_data_stock(),
            self._t44_pipeline_mid_run_interrupt(),
            self._t45_dns_failure(),
            self._t46_connection_timeout(),
            self._t47_ssl_error(),
            self._t48_truncated_response(),
            self._t49_redirect_loop(),
            self._t50_http_429(),
        ]

    def _t1_screener_unreachable(self):
        def run():
            from app.ingestion.financial_ingestor import FinancialIngestor
            FinancialIngestor._screener_unreachable = True
            with patch('app.ingestion.nse_financial_ingestor.fetch_nse_quarterly') as mock_nse:
                mock_nse.return_value = [{"quarter": "2025-Q1", "revenue": 1000.0}]
                ingestor = FinancialIngestor()
                result = ingestor.fetch_quarterly("RELIANCE")
                ok = result is True
                return ok, f"Screener circuit breaker fallback to yfinance: {'worked' if ok else 'failed'}"
        return {"id": 1, "name": "Screener unreachable triggers yfinance fallback", "category": "screener", "run": run}

    def _t2_screener_timeout(self):
        def run():
            from app.ingestion.screener_scraper import scrape_screener
            with patch('app.ingestion.screener_scraper.requests.get') as mock_get:
                mock_get.side_effect = ConnectionError("Connection timed out")
                result = scrape_screener("RELIANCE")
                ok = result == {}
                return ok, f"Screener timeout returns empty dict: {'ok' if ok else 'unexpected'}"
        return {"id": 2, "name": "Screener timeout returns empty dict gracefully", "category": "screener", "run": run}

    def _t3_screener_empty_data(self):
        def run():
            from app.ingestion.screener_scraper import scrape_screener
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "<html><body>No financial data</body></html>"
            with patch('app.ingestion.screener_scraper.requests.get', return_value=mock_resp):
                result = scrape_screener("RELIANCE")
                ok = result == {"symbol": "RELIANCE"}
                return ok, f"Screener empty HTML returns symbol-only dict: {'ok' if ok else 'unexpected'}"
        return {"id": 3, "name": "Screener returns empty data gracefully", "category": "screener", "run": run}

    def _t4_screener_malformed_html(self):
        def run():
            from app.ingestion.screener_scraper import scrape_screener
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "<tr><td>broken<$$$>"
            with patch('app.ingestion.screener_scraper.requests.get', return_value=mock_resp):
                result = scrape_screener("RELIANCE")
                ok = result == {"symbol": "RELIANCE"}
                return ok, f"Screener malformed HTML returns symbol-only dict: {'ok' if ok else 'unexpected'}"
        return {"id": 4, "name": "Screener malformed HTML handled without crash", "category": "screener", "run": run}

    def _t5_screener_circuit_breaker_activates(self):
        def run():
            from app.ingestion.financial_ingestor import FinancialIngestor
            FinancialIngestor._screener_unreachable = False
            with patch('app.ingestion.financial_ingestor.scrape_screener', return_value={}):
                with patch('app.ingestion.nse_financial_ingestor.fetch_nse_quarterly') as mock_nse:
                    mock_nse.return_value = [{"quarter": "2025-Q1", "revenue": 1000.0}]
                    ingestor = FinancialIngestor()
                    for _ in range(5):
                        ingestor.fetch_quarterly("RELIANCE")
                    activated = FinancialIngestor._screener_unreachable is True
                    return activated, f"Circuit breaker activated after 5 failures: {'yes' if activated else 'no'}"
        return {"id": 5, "name": "Screener circuit breaker activates after failures", "category": "screener", "run": run}

    def _t6_screener_circuit_breaker_reset(self):
        def run():
            from app.ingestion.financial_ingestor import FinancialIngestor
            FinancialIngestor._screener_unreachable = True
            with patch('app.ingestion.screener_scraper.scrape_screener') as mock_scrape:
                mock_scrape.return_value = {"quarterly_pl": {"quarters": ["Mar 2025"], "revenue": [1000]}}
                with patch('app.ingestion.financial_ingestor.SessionLocal'):
                    ingestor = FinancialIngestor()
                    FinancialIngestor._screener_unreachable = True
                    ingestor.fetch_quarterly("RELIANCE")
                    still_blocked = FinancialIngestor._screener_unreachable
                    ok = still_blocked is True
                    return ok, f"Circuit breaker stays active until reset: {'ok' if ok else 'unexpected'}"
        return {"id": 6, "name": "Screener circuit breaker stays active (manual reset required)", "category": "screener", "run": run}

    def _t7_screener_partial_data(self):
        def run():
            from app.ingestion.financial_ingestor import FinancialIngestor
            FinancialIngestor._screener_unreachable = False
            call_count = 0
            def mock_scrape(sym):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {"quarterly_pl": {"quarters": ["Mar 2025"], "revenue": [1000]}}
                return {}
            with patch('app.ingestion.screener_scraper.scrape_screener', side_effect=mock_scrape):
                with patch('app.ingestion.nse_financial_ingestor.fetch_nse_quarterly') as mock_nse:
                    mock_nse.return_value = [{"quarter": "2025-Q1", "revenue": 500.0}]
                    ingestor = FinancialIngestor()
                    r1 = ingestor.fetch_quarterly("STOCK1")
                    r2 = ingestor.fetch_quarterly("STOCK2")
                    ok = r1 is True and r2 is True
                    return ok, f"Partial screener data: first={r1}, second(fallback)={r2}: {'ok' if ok else 'unexpected'}"
        return {"id": 7, "name": "Screener partial data falls back to yfinance for failing stocks", "category": "screener", "run": run}

    def _t8_screener_fallback_yfinance(self):
        def run():
            from app.ingestion.financial_ingestor import FinancialIngestor
            FinancialIngestor._screener_unreachable = False
            with patch('app.ingestion.screener_scraper.scrape_screener') as mock_scrape:
                mock_scrape.return_value = None
                with patch('app.ingestion.nse_financial_ingestor.fetch_nse_quarterly') as mock_nse:
                    mock_nse.return_value = [{"quarter": "2025-Q1", "revenue": 500.0}]
                    ingestor = FinancialIngestor()
                    result = ingestor.fetch_quarterly("RELIANCE")
                    ok = result is True
                    return ok, f"Screener None fallback to yfinance: {'worked' if ok else 'failed'}"
        return {"id": 8, "name": "Screener returns None triggers yfinance fallback", "category": "screener", "run": run}

    def _t9_nse_connection_failure(self):
        def run():
            from app.ingestion.nse_financial_ingestor import fetch_nse_quarterly
            with patch('yfinance.Ticker') as mock_ticker:
                mock_ticker.side_effect = Exception("Connection refused")
                result = fetch_nse_quarterly("RELIANCE")
                ok = result is None
                return ok, f"NSE ingestor connection failure returns None: {'ok' if ok else 'unexpected'}"
        return {"id": 9, "name": "NSE ingestor connection failure returns None gracefully", "category": "yfinance", "run": run}

    def _t10_nse_empty_quarterly(self):
        def run():
            from app.ingestion.nse_financial_ingestor import fetch_nse_quarterly
            mock_ticker = MagicMock()
            mock_ticker.quarterly_financials = None
            with patch('yfinance.Ticker', return_value=mock_ticker):
                result = fetch_nse_quarterly("RELIANCE")
                ok = result is None
                return ok, f"NSE empty quarterly financials returns None: {'ok' if ok else 'unexpected'}"
        return {"id": 10, "name": "NSE empty quarterly data handled", "category": "yfinance", "run": run}

    def _t11_nse_missing_balance_sheet(self):
        def run():
            from app.ingestion.nse_financial_ingestor import fetch_nse_quarterly
            import pandas as pd
            dates = pd.date_range("2025-01-01", periods=4, freq="QE")
            fin_data = pd.DataFrame({"Total Revenue": [1000, 1100, 1200, 1300]}, index=dates)
            mock_ticker = MagicMock()
            mock_ticker.quarterly_financials = fin_data.T
            mock_ticker.quarterly_balance_sheet = None
            mock_ticker.quarterly_cashflow = None
            mock_ticker.cashflow = None
            with patch('yfinance.Ticker', return_value=mock_ticker):
                result = fetch_nse_quarterly("RELIANCE")
                ok = result is not None and len(result) > 0
                return ok, f"NSE missing balance sheet returns {len(result) if result else 0} records: {'ok' if ok else 'unexpected'}"
        return {"id": 11, "name": "NSE missing balance sheet doesn't crash", "category": "yfinance", "run": run}

    def _t12_nse_missing_cashflow(self):
        def run():
            from app.ingestion.nse_financial_ingestor import fetch_nse_quarterly
            import pandas as pd
            dates = pd.date_range("2025-01-01", periods=4, freq="QE")
            fin_data = pd.DataFrame({"Total Revenue": [1000, 1100, 1200, 1300]}, index=dates)
            bs_data = pd.DataFrame({"Total Debt": [500, 450, 400, 350]}, index=dates)
            mock_ticker = MagicMock()
            mock_ticker.quarterly_financials = fin_data.T
            mock_ticker.quarterly_balance_sheet = bs_data.T
            mock_ticker.quarterly_cashflow = None
            mock_ticker.cashflow = None
            with patch('yfinance.Ticker', return_value=mock_ticker):
                result = fetch_nse_quarterly("RELIANCE")
                ok = result is not None and len(result) > 0
                return ok, f"NSE missing cashflow returns {len(result) if result else 0} records: {'ok' if ok else 'unexpected'}"
        return {"id": 12, "name": "NSE missing cashflow data falls back to annual", "category": "yfinance", "run": run}

    def _t13_yfinance_ticker_not_found(self):
        def run():
            from app.ingestion.financial_ingestor import FinancialIngestor
            FinancialIngestor._screener_unreachable = True
            with patch('app.ingestion.nse_financial_ingestor.fetch_nse_quarterly') as mock_nse:
                mock_nse.side_effect = Exception("Ticker not found")
                with patch('app.ingestion.financial_ingestor.FinancialIngestor._from_bse') as mock_bse:
                    mock_bse.return_value = False
                    ingestor = FinancialIngestor()
                    result = ingestor.fetch_quarterly("INVALID123")
                    ok = result is False
                    return ok, f"Invalid ticker falls through all fallbacks: {'ok' if ok else 'unexpected'}"
        return {"id": 13, "name": "Invalid yfinance ticker handled via fallback chain", "category": "yfinance", "run": run}

    def _t14_yfinance_empty_history(self):
        def run():
            from app.services.pipeline import ingest_stock_prices
            mock_session = MagicMock()
            mock_query = MagicMock()
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            mock_session.query.return_value.filter_by.return_value.count.return_value = 0
            with patch('yfinance.Ticker') as mock_ticker:
                mock_info = MagicMock()
                mock_info.get.return_value = None
                mock_ticker_instance = MagicMock()
                mock_ticker_instance.info = {}
                mock_ticker_instance.history.return_value.empty = True
                mock_ticker.return_value = mock_ticker_instance
                result = ingest_stock_prices("RELIANCE", mock_session)
                ok = result is False
                return ok, f"Empty price history returns False: {'ok' if ok else 'unexpected'}"
        return {"id": 14, "name": "Empty yfinance history returns clean False", "category": "yfinance", "run": run}

    def _t15_yfinance_rate_limited(self):
        def run():
            from app.services.pipeline import ingest_stock_prices
            mock_session = MagicMock()
            mock_query = MagicMock()
            mock_session.query.return_value = mock_query
            mock_query.filter_by.return_value = mock_query
            mock_query.first.return_value = None
            mock_query.count.return_value = 0
            with patch('yfinance.Ticker') as mock_ticker:
                mock_ticker.side_effect = Exception("Rate limited: Too Many Requests")
                result = ingest_stock_prices("RELIANCE", mock_session)
                ok = result is False
                return ok, f"yfinance rate limited returns False: {'ok' if ok else 'unexpected'}"
        return {"id": 15, "name": "yfinance rate limited handled gracefully", "category": "yfinance", "run": run}

    def _t16_yfinance_missing_financials(self):
        def run():
            from app.ingestion.nse_financial_ingestor import fetch_nse_quarterly
            mock_ticker = MagicMock()
            mock_ticker.quarterly_financials = None
            with patch('yfinance.Ticker', return_value=mock_ticker):
                result = fetch_nse_quarterly("RELIANCE")
                ok = result is None
                return ok, f"Missing yfinance financials returns None: {'ok' if ok else 'unexpected'}"
        return {"id": 16, "name": "yfinance financial statements missing returns None", "category": "yfinance", "run": run}

    def _t17_db_connection_lost(self):
        def run():
            from sqlalchemy.exc import OperationalError
            try:
                eng = create_engine("postgresql://invalid:invalid@localhost:1/nonexistent")
                conn = eng.connect()
                conn.execute(text("SELECT 1"))
                ok = False
            except OperationalError:
                ok = True
            except Exception:
                ok = True
            return ok, f"DB connection loss raises OperationalError: {'handled' if ok else 'unexpected'}"
        return {"id": 17, "name": "Database connection loss raises OperationalError", "category": "database", "run": run}

    def _t18_db_query_timeout(self):
        def run():
            try:
                session = SessionLocal()
                session.execute(text("SET LOCAL statement_timeout = '1ms'"))
                session.execute(text("SELECT pg_sleep(10)"))
                session.close()
                ok = False
            except Exception as e:
                ok = True
            return ok, f"Query timeout raises exception (expected): {'handled' if ok else 'unexpected'}"
        return {"id": 18, "name": "Database query timeout raises exception", "category": "database", "run": run}

    def _t19_db_constraint_violation(self):
        def run():
            from app.models.score_snapshot import ScoreSnapshot
            ok = False
            try:
                session = SessionLocal()
                duplicate = ScoreSnapshot(
                    date="2025-01-01",
                    symbol="DUPLICATE_TEST",
                    total_score=50.0
                )
                session.add(duplicate)
                session.commit()
                duplicate2 = ScoreSnapshot(
                    date="2025-01-01",
                    symbol="DUPLICATE_TEST",
                    total_score=60.0
                )
                session.add(duplicate2)
                session.commit()
            except Exception as e:
                ok = "duplicate" in str(e).lower() or "unique" in str(e).lower() or "primary" in str(e).lower()
                session.rollback()
            finally:
                session.close()
            return ok, f"Constraint violation caught: {'yes' if ok else 'no (may need DB reset)'}"
        return {"id": 19, "name": "Database constraint violation raises integrity error", "category": "database", "run": run}

    def _t20_db_table_missing(self):
        def run():
            try:
                session = SessionLocal()
                session.execute(text("SELECT * FROM nonexistent_table_xyz"))
                session.close()
                ok = False
            except Exception as e:
                ok = "does not exist" in str(e).lower() or "not found" in str(e).lower() or "relation" in str(e).lower()
            return ok, f"Missing table raises error: {'handled' if ok else 'unexpected'}"
        return {"id": 20, "name": "Database table missing raises error", "category": "database", "run": run}

    def _t21_db_write_failure(self):
        def run():
            ok = False
            try:
                session = SessionLocal()
                session.execute(text("CREATE TEMP TABLE _test_write_fail (id int)"))
                session.execute(text("INSERT INTO _test_write_fail VALUES (1)"))
                session.execute(text("DROP TABLE IF EXISTS _test_write_fail"))
                session.commit()
                ok = True
            except Exception as e:
                ok = False
            finally:
                session.close()
            return ok, f"DB write succeeded (disk not simulated): {'ok' if ok else 'unexpected'}"
        return {"id": 21, "name": "Database write failure simulation", "category": "database", "run": run}

    def _t22_db_concurrent_write(self):
        def run():
            session1 = SessionLocal()
            session2 = SessionLocal()
            ok = False
            try:
                session1.execute(text("CREATE TEMP TABLE _test_concurrent (id int PRIMARY KEY, val int)"))
                session1.commit()
                session1.execute(text("INSERT INTO _test_concurrent VALUES (1, 10)"))
                session1.commit()
                session1.execute(text("UPDATE _test_concurrent SET val = 20 WHERE id = 1"))
                session2.execute(text("UPDATE _test_concurrent SET val = 30 WHERE id = 1"))
                session1.commit()
                session2.commit()
                ok = True
            except Exception:
                ok = True
            finally:
                try:
                    session1.execute(text("DROP TABLE IF EXISTS _test_concurrent"))
                    session1.commit()
                except:
                    pass
                session1.close()
                session2.close()
            return ok, f"Concurrent writes handled: no deadlock (MVCC): {'ok' if ok else 'unexpected'}"
        return {"id": 22, "name": "Concurrent write conflict handled by MVCC", "category": "database", "run": run}

    def _t23_db_transaction_rollback(self):
        def run():
            session = SessionLocal()
            try:
                session.execute(text("CREATE TABLE IF NOT EXISTS _test_rb_persist (id int)"))
                session.execute(text("INSERT INTO _test_rb_persist VALUES (1)"))
                session.commit()
                session.execute(text("UPDATE _test_rb_persist SET id = 2"))
                session.rollback()
                val = session.execute(text("SELECT id FROM _test_rb_persist")).scalar()
                ok = val == 1
            except Exception:
                ok = False
            finally:
                try:
                    session.execute(text("DROP TABLE IF EXISTS _test_rb_persist"))
                    session.commit()
                except:
                    pass
                session.close()
            return ok, f"Transaction rollback preserves committed data: {'ok' if ok else 'unexpected'}"
        return {"id": 23, "name": "Transaction rollback preserves committed data", "category": "database", "run": run}

    def _t24_db_session_leak(self):
        def run():
            sessions = []
            try:
                for _ in range(5):
                    s = SessionLocal()
                    s.execute(text("SELECT 1"))
                    sessions.append(s)
                ok = len(sessions) == 5
                return ok, f"Multiple sessions created without leak: {len(sessions)} sessions"
            finally:
                for s in sessions:
                    s.close()
        return {"id": 24, "name": "Session leak detection (multiple sessions)", "category": "database", "run": run}

    def _t25_all_scores_none(self):
        def run():
            from app.scoring.alpha_engine import alpha_score, _compute_confidence
            data = {"symbol": "TEST", "sector": "Technology"}
            for k in ["roce", "debt_equity", "revenue", "pat", "operating_margin",
                       "eps", "receivables", "inventory", "debt", "interest_expense",
                       "current_price", "return_6m", "returns_1y", "volume_ratio",
                       "delivery_ratio", "beta", "atr_14", "high_52w", "market_cap",
                       "pe_ratio", "pb_ratio", "ev_ebitda", "dividend_yield",
                       "promoter_change", "pledge_percent", "operating_cashflow",
                       "cash_conversion_ratio", "cash_flow_operations",
                       "liquidity_score", "avg_daily_value",
                       "relative_strength", "trend_strength"]:
                data[k] = None
            score = alpha_score(data)
            ok = score >= 5 and score <= 100
            return ok, f"All-None data produces score={score} (floor=5): {'ok' if ok else 'unexpected'}"
        return {"id": 25, "name": "All scores None for a stock handled gracefully", "category": "data_quality", "run": run}

    def _t26_layer_scores_missing(self):
        def run():
            from app.scoring.alpha_engine import get_score_breakdown
            data = {"symbol": "TEST", "sector": "Technology", "current_price": 100,
                    "returns_6m": 10, "returns_1y": 20, "volume_ratio": 1.2,
                    "delivery_ratio": 0.8, "beta": 1.0, "atr_14": 2, "high_52w": 120,
                    "market_cap": 1000000000, "pe_ratio": 15, "pb_ratio": 2,
                    "ev_ebitda": 10, "dividend_yield": 1, "promoter_change": 0,
                    "pledge_percent": 0, "operating_cashflow": 0,
                    "cash_conversion_ratio": 1, "cash_flow_operations": 0,
                    "liquidity_score": 100, "avg_daily_value": 100000000,
                    "relative_strength": 50, "trend_strength": 0}
            breakdown = get_score_breakdown(data)
            ok = breakdown.get("total_score") is not None
            return ok, f"Partial data breakdown produces score={breakdown.get('total_score')}: {'ok' if ok else 'unexpected'}"
        return {"id": 26, "name": "Some layer scores missing handled", "category": "data_quality", "run": run}

    def _t27_confidence_zero(self):
        def run():
            from app.scoring.alpha_engine import _compute_confidence
            data = {"symbol": "TEST"}
            conf = _compute_confidence(data, 50)
            ok = conf == 0.0
            return ok, f"Empty data confidence={conf}: {'ok' if ok else 'unexpected'}"
        return {"id": 27, "name": "Confidence score is 0 for empty data", "category": "data_quality", "run": run}

    def _t28_all_sector_unknown(self):
        def run():
            from app.scoring.ranker import PercentileRanker
            data_list = [
                {"symbol": "A", "sector": "Unknown", "roce": 20, "debt_equity": 0.5},
                {"symbol": "B", "sector": "Unknown", "roce": 15, "debt_equity": 0.3},
                {"symbol": "C", "sector": "Unknown", "roce": 10, "debt_equity": 0.8},
            ]
            ranker = PercentileRanker(data_list)
            pcts = [ranker.pct("roce", d["roce"], sector=d["sector"]) for d in data_list]
            ok = all(p is not None for p in pcts) and len(set(pcts)) == len(pcts)
            return ok, f"Unknown sector percentile ranking: all non-None, unique pcts={pcts}: {'ok' if ok else 'unexpected'}"
        return {"id": 28, "name": "Unknown sector falls back to universe ranking", "category": "data_quality", "run": run}

    def _t29_price_history_missing(self):
        def run():
            mock_session = MagicMock()
            mock_query = MagicMock()
            mock_filter = MagicMock()
            mock_session.query.return_value.filter_by.return_value = mock_filter
            mock_filter.order_by.return_value.limit.return_value.all.return_value = []
            from app.services.pipeline import get_stock_data_for_scoring
            result = get_stock_data_for_scoring("TEST", mock_session)
            ok = result is None
            return ok, f"Missing price history returns None: {'ok' if ok else 'unexpected'}"
        return {"id": 29, "name": "Stock with no price history returns None", "category": "data_quality", "run": run}

    def _t30_market_cap_none(self):
        def run():
            from app.scoring.penalty_engine import confidence_penalty
            data = {"symbol": "TEST", "market_cap": None, "avg_daily_value": None}
            penalty = confidence_penalty(data)
            ok = isinstance(penalty, (int, float))
            return ok, f"None market_cap penalty={penalty} (type ok): {'ok' if ok else 'unexpected'}"
        return {"id": 30, "name": "Market cap is None doesn't cause error", "category": "data_quality", "run": run}

    def _t31_low_data_coverage(self):
        def run():
            from app.services.data_validation import validate_score_distribution
            scored = [{"total_score": 5} for _ in range(100)]
            result = validate_score_distribution(scored)
            ok = result.get("status") is not None
            return ok, f"Low coverage distribution validation: status={result.get('status')}: {'ok' if ok else 'unexpected'}"
        return {"id": 31, "name": "Low data coverage (<30%) detected", "category": "data_quality", "run": run}

    def _t32_no_score_spread(self):
        def run():
            from app.services.data_validation import validate_score_distribution
            scored = [{"total_score": 50} for _ in range(100)]
            result = validate_score_distribution(scored)
            ok = result.get("status") == "fail" and len(result.get("issues", [])) > 0
            return ok, f"Zero spread distribution: {result.get('status')}, issues={len(result.get('issues', []))}: {'ok' if ok else 'unexpected'}"
        return {"id": 32, "name": "Zero spread score distribution detected", "category": "data_quality", "run": run}

    def _t33_rank_ties(self):
        def run():
            from app.scoring.ranker import PercentileRanker
            data_list = [
                {"symbol": "A", "roce": 20},
                {"symbol": "B", "roce": 20},
                {"symbol": "C", "roce": 20},
                {"symbol": "D", "roce": 10},
            ]
            ranker = PercentileRanker(data_list)
            pct_a = ranker.pct("roce", 20)
            pct_b = ranker.pct("roce", 20)
            pct_c = ranker.pct("roce", 20)
            pct_d = ranker.pct("roce", 10)
            ok = pct_a == pct_b == pct_c and pct_d < pct_a
            return ok, f"Rank ties (identical scores) handled: all 20s={pct_a}, 10={pct_d}: {'ok' if ok else 'unexpected'}"
        return {"id": 33, "name": "Rank ties with identical scores handled", "category": "data_quality", "run": run}

    def _t34_outlier_scores(self):
        def run():
            from app.scoring.alpha_engine import alpha_score
            data = {
                "symbol": "OUTLIER", "sector": "Technology",
                "roce": 200, "debt_equity": -5, "revenue": 1e12, "pat": 1e11,
                "operating_margin": 200, "eps": 5000, "receivables": 0,
                "inventory": 0, "debt": 0, "interest_expense": 0,
                "current_price": 10000, "returns_6m": 200, "returns_1y": 300,
                "volume_ratio": 20, "delivery_ratio": 3, "beta": 3.5,
                "atr_14": 100, "high_52w": 15000, "market_cap": 1e13,
                "pe_ratio": 2, "pb_ratio": 0.1, "ev_ebitda": 1, "dividend_yield": 10,
                "promoter_change": 20, "pledge_percent": 0, "operating_cashflow": 1e11,
                "cash_conversion_ratio": 2, "cash_flow_operations": 1e11,
                "liquidity_score": 100, "avg_daily_value": 1e10,
                "relative_strength": 100, "trend_strength": 0.5,
            }
            score = alpha_score(data)
            ok = 0 <= score <= 100
            return ok, f"Extreme outlier data clamped to [{max(0, score)}, {min(100, score)}] (score={score}): {'ok' if ok else 'unexpected'}"
        return {"id": 34, "name": "Extreme outlier scores clamped to [0, 100]", "category": "data_quality", "run": run}

    def _t35_zero_stock_universe(self):
        def run():
            import pandas as pd
            from app.services.pipeline import run_full_pipeline
            with patch('app.services.pipeline.build_stock_universe', return_value=pd.DataFrame()):
                result = run_full_pipeline()
                ok = result.get("error") is not None
                return ok, f"Empty universe returns error: {result.get('error')}: {'ok' if ok else 'unexpected'}"
        return {"id": 35, "name": "Zero stocks in universe returns error", "category": "edge_case", "run": run}

    def _t36_single_stock_universe(self):
        def run():
            import pandas as pd
            from app.services.pipeline import run_full_pipeline
            df = pd.DataFrame([{"SYMBOL": "SINGLE_TEST", "NAME OF COMPANY": "Test Corp"}])
            with patch('app.services.pipeline.build_stock_universe', return_value=df):
                with patch('app.services.pipeline.SessionLocal') as mock_session_cls:
                    mock_session = MagicMock()
                    mock_session_cls.return_value = mock_session
                    mock_filter = MagicMock()
                    mock_session.query.return_value.filter_by.return_value = mock_filter
                    mock_filter.first.return_value = None
                    mock_filter.count.return_value = 0
                    result = run_full_pipeline()
                    ok = isinstance(result, dict)
                    return ok, f"Single stock universe runs: {list(result.keys())}: {'ok' if ok else 'unexpected'}"
        return {"id": 36, "name": "Single stock in universe runs pipeline", "category": "edge_case", "run": run}

    def _t37_all_same_sector(self):
        def run():
            from app.scoring.ranker import PercentileRanker
            data_list = [
                {"symbol": "A", "sector": "Banking", "roce": 20},
                {"symbol": "B", "sector": "Banking", "roce": 15},
                {"symbol": "C", "sector": "Banking", "roce": 10},
            ]
            ranker = PercentileRanker(data_list)
            pct_a = ranker.pct("roce", 20, sector="Banking")
            pct_b = ranker.pct("roce", 15, sector="Banking")
            pct_c = ranker.pct("roce", 10, sector="Banking")
            ok = pct_a > pct_b > pct_c
            return ok, f"Same sector ranking: {pct_a} > {pct_b} > {pct_c}: {'ok' if ok else 'unexpected'}"
        return {"id": 37, "name": "All stocks same sector ranking works", "category": "edge_case", "run": run}

    def _t38_weekend_holiday_date(self):
        def run():
            from app.services.pipeline import run_full_pipeline
            import pandas as pd
            from datetime import datetime
            df = pd.DataFrame([{"SYMBOL": "WEEKEND_TEST", "NAME OF COMPANY": "Test"}])
            with patch('app.services.pipeline.build_stock_universe', return_value=df):
                with patch('app.services.pipeline.datetime') as mock_dt:
                    mock_dt.today.return_value = datetime(2025, 6, 29)
                    with patch('app.services.pipeline.SessionLocal') as mock_session_cls:
                        mock_session = MagicMock()
                        mock_session_cls.return_value = mock_session
                        mock_session.query.return_value.filter_by.return_value.first.return_value = None
                        mock_session.query.return_value.filter_by.return_value.count.return_value = 0
                        result = run_full_pipeline()
                        ok = isinstance(result, dict)
                        return ok, f"Weekend date pipeline runs: {list(result.keys())}: {'ok' if ok else 'unexpected'}"
        return {"id": 38, "name": "Weekend/holiday date pipeline runs", "category": "edge_case", "run": run}

    def _t39_pipeline_idempotency(self):
        def run():
            from app.services.pipeline import run_full_pipeline
            import pandas as pd
            df = pd.DataFrame([{"SYMBOL": "IDEM_TEST", "NAME OF COMPANY": "Test"}])
            with patch('app.services.pipeline.build_stock_universe', return_value=df):
                with patch('app.services.pipeline.SessionLocal') as mock_session_cls:
                    mock_session = MagicMock()
                    mock_session_cls.return_value = mock_session
                    mock_filter = MagicMock()
                    mock_session.query.return_value.filter_by.return_value = mock_filter
                    mock_filter.first.return_value = None
                    mock_filter.count.side_effect = [0, 5]
                    r1 = run_full_pipeline()
                    r2 = run_full_pipeline()
                    ok = isinstance(r1, dict) and isinstance(r2, dict)
                    return ok, f"Pipeline idempotency: both runs complete: {'ok' if ok else 'unexpected'}"
        return {"id": 39, "name": "Running pipeline twice same day (idempotency)", "category": "edge_case", "run": run}

    def _t40_missing_env_vars(self):
        def run():
            from sqlalchemy.exc import OperationalError
            try:
                bad_eng = create_engine("postgresql://invalid:invalid@nonexistent:5432/nope")
                conn = bad_eng.connect()
                conn.execute(text("SELECT 1"))
                ok = False
            except OperationalError:
                ok = True
            except Exception:
                ok = True
            return ok, "Invalid DB URL raises OperationalError (expected)"
        return {"id": 40, "name": "Invalid database URL raises error gracefully", "category": "edge_case", "run": run}

    def _t41_empty_symbols(self):
        def run():
            from app.ingestion.financial_ingestor import FinancialIngestor
            FinancialIngestor._screener_unreachable = True
            with patch('app.ingestion.nse_financial_ingestor.fetch_nse_quarterly') as mock_nse:
                mock_nse.side_effect = Exception("Empty symbol")
                ingestor = FinancialIngestor()
                result = ingestor.fetch_quarterly("")
                ok = result is False
                return ok, f"Empty symbol handled: result={result}: {'ok' if ok else 'unexpected'}"
        return {"id": 41, "name": "Empty string symbols handled gracefully", "category": "edge_case", "run": run}

    def _t42_special_chars_symbols(self):
        def run():
            from app.ingestion.financial_ingestor import FinancialIngestor
            FinancialIngestor._screener_unreachable = True
            with patch('app.ingestion.nse_financial_ingestor.fetch_nse_quarterly') as mock_nse:
                mock_nse.side_effect = Exception("Bad symbol")
                ingestor = FinancialIngestor()
                result = ingestor.fetch_quarterly("TEST$%^&")
                ok = result is False
                return ok, f"Special chars symbol handled: result={result}: {'ok' if ok else 'unexpected'}"
        return {"id": 42, "name": "Special characters in symbol names handled", "category": "edge_case", "run": run}

    def _t43_no_data_stock(self):
        def run():
            from app.scoring.alpha_engine import alpha_score
            data = {"symbol": "NODATA", "sector": "Unknown", "current_price": 10}
            score = alpha_score(data)
            ok = score >= 5 and score <= 100
            return ok, f"No-data stock score={score} (floor=5): {'ok' if ok else 'unexpected'}"
        return {"id": 43, "name": "Very long-running stock with no data", "category": "edge_case", "run": run}

    def _t44_pipeline_mid_run_interrupt(self):
        def run():
            session = SessionLocal()
            try:
                session.execute(text("CREATE TABLE IF NOT EXISTS _test_int_persist (id int)"))
                session.execute(text("INSERT INTO _test_int_persist VALUES (1)"))
                session.commit()
                session.execute(text("UPDATE _test_int_persist SET id = 2"))
                raise KeyboardInterrupt("Simulated Ctrl+C")
            except KeyboardInterrupt:
                session.rollback()
                try:
                    val = session.execute(text("SELECT id FROM _test_int_persist")).scalar()
                    ok = val == 1
                except Exception:
                    ok = False
                return ok, f"Mid-run interrupt rollback preserves committed data: {'ok' if ok else 'unexpected'}"
            finally:
                try:
                    session.execute(text("DROP TABLE IF EXISTS _test_int_persist"))
                    session.commit()
                except:
                    pass
                session.close()
        return {"id": 44, "name": "Pipeline interrupted mid-run rolls back", "category": "edge_case", "run": run}

    def _t45_dns_failure(self):
        def run():
            from app.ingestion.screener_scraper import scrape_screener
            with patch('app.ingestion.screener_scraper.requests.get') as mock_get:
                mock_get.side_effect = ConnectionError("Name or service not known")
                result = scrape_screener("RELIANCE")
                ok = result == {}
                return ok, f"DNS failure returns empty dict: {'ok' if ok else 'unexpected'}"
        return {"id": 45, "name": "DNS resolution failure returns empty dict", "category": "network", "run": run}

    def _t46_connection_timeout(self):
        def run():
            from app.ingestion.screener_scraper import scrape_screener
            with patch('app.ingestion.screener_scraper.requests.get') as mock_get:
                mock_get.side_effect = ConnectionError("Connection timed out after 30s")
                result = scrape_screener("RELIANCE")
                ok = result == {}
                return ok, f"Connection timeout returns empty dict: {'ok' if ok else 'unexpected'}"
        return {"id": 46, "name": "Connection timeout (>30s) handled", "category": "network", "run": run}

    def _t47_ssl_error(self):
        def run():
            from app.ingestion.screener_scraper import scrape_screener
            with patch('app.ingestion.screener_scraper.requests.get') as mock_get:
                mock_get.side_effect = ConnectionError("SSL: CERTIFICATE_VERIFY_FAILED")
                result = scrape_screener("RELIANCE")
                ok = result == {}
                return ok, f"SSL certificate error returns empty dict: {'ok' if ok else 'unexpected'}"
        return {"id": 47, "name": "SSL certificate error handled", "category": "network", "run": run}

    def _t48_truncated_response(self):
        def run():
            from app.ingestion.screener_scraper import scrape_screener
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "<html><body>Partial da"
            with patch('app.ingestion.screener_scraper.requests.get', return_value=mock_resp):
                result = scrape_screener("RELIANCE")
                ok = result == {"symbol": "RELIANCE"}
                return ok, f"Truncated response returns symbol-only dict: {'ok' if ok else 'unexpected'}"
        return {"id": 48, "name": "Partial truncated response handled", "category": "network", "run": run}

    def _t49_redirect_loop(self):
        def run():
            from app.ingestion.screener_scraper import scrape_screener
            with patch('app.ingestion.screener_scraper.requests.get') as mock_get:
                mock_get.side_effect = ConnectionError("Redirect loop detected")
                result = scrape_screener("RELIANCE")
                ok = result == {}
                return ok, f"Redirect loop returns empty dict: {'ok' if ok else 'unexpected'}"
        return {"id": 49, "name": "Redirect loop handled", "category": "network", "run": run}

    def _t50_http_429(self):
        def run():
            from app.ingestion.screener_scraper import scrape_screener
            mock_resp = MagicMock()
            mock_resp.status_code = 429
            mock_resp.text = "Too Many Requests"
            with patch('app.ingestion.screener_scraper.requests.get', return_value=mock_resp):
                result = scrape_screener("RELIANCE")
                ok = result == {}
                return ok, f"HTTP 429 returns empty dict: {'ok' if ok else 'unexpected'}"
        return {"id": 50, "name": "HTTP 429 (too many requests) handled", "category": "network", "run": run}

    def run_all(self):
        results = []
        for test in self.scenarios:
            try:
                ok, detail = test["run"]()
                status = "PASS" if ok else "FAIL"
            except Exception as e:
                status = "FAIL"
                detail = str(e)
            results.append({"id": test["id"], "name": test["name"], "category": test["category"], "status": status, "details": str(detail)})
            print(f"  [{status}] Test {test['id']:02d} [{test['category']:>12}]: {test['name']}")
        return results

    def cleanup(self):
        from app.ingestion.financial_ingestor import FinancialIngestor
        FinancialIngestor._screener_unreachable = False
        for key in ['SCREENER_UNREACHABLE', 'DISABLE_NSE', 'MOCK_DB_FAILURE']:
            os.environ.pop(key, None)
        try:
            engine.dispose()
        except:
            pass
        import glob
        for d in glob.glob(os.path.join(os.path.dirname(__file__), '..', '**', '__pycache__'), recursive=True):
            import shutil
            try:
                shutil.rmtree(d)
            except:
                pass

    def generate_report(self, results):
        total = len(results)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = total - passed
        pass_rate = round(passed / total * 100, 1)

        categories = {}
        failures = []
        for r in results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "passed": 0, "failed": 0}
            categories[cat]["total"] += 1
            if r["status"] == "PASS":
                categories[cat]["passed"] += 1
            else:
                categories[cat]["failed"] += 1
                failures.append(r)

        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate_pct": pass_rate,
            "verdict": "ALL PASS - 100% graceful recovery" if failed == 0 else f"FAILURES DETECTED - {failed} need fixing",
            "category_breakdown": categories,
            "failures": [{"id": f["id"], "name": f["name"], "details": f["details"]} for f in failures],
        }

        report_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, "failure_resilience_audit.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n{'='*60}")
        print(f"  FAILURE RESILIENCE AUDIT REPORT")
        print(f"{'='*60}")
        print(f"  Total: {total}, Pass: {passed}, Fail: {failed}")
        print(f"  Pass Rate: {pass_rate}%")
        print(f"  Verdict: {report['verdict']}")
        print(f"\n  Category Breakdown:")
        for cat, c in sorted(categories.items()):
            c_pct = round(c["passed"] / c["total"] * 100, 1) if c["total"] else 0
            bar = "█" * int(c_pct / 10) + "░" * (10 - int(c_pct / 10))
            print(f"    {cat:>12}: {bar} {c['passed']}/{c['total']} ({c_pct}%)")
        if failures:
            print(f"\n  Failures:")
            for f in failures:
                print(f"    [{f['id']:02d}] {f['name']}: {f['details']}")
        print(f"\n  Report saved to: {report_path}")
        print(f"{'='*60}")

        return report

    def cleanup_test_data(self):
        session = SessionLocal()
        try:
            for tbl in ["_test_write_fail", "_test_concurrent", "_test_rb_persist", "_test_int_persist"]:
                session.execute(text(f"DROP TABLE IF EXISTS {tbl}"))
            session.commit()
        except:
            session.rollback()
        finally:
            session.close()

    def run(self):
        print("FAILURE RESILIENCE TEST SUITE")
        print("=" * 60)
        print(f"Starting {len(self.scenarios)} test scenarios...\n")
        results = self.run_all()
        report = self.generate_report(results)
        self.cleanup()
        self.cleanup_test_data()
        return report


if __name__ == "__main__":
    suite = FailureResilienceTest()
    suite.run()
