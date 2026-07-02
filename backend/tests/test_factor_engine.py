"""Phase 3 regression checks: Factor/composite_score (app/scoring/factor.py)
and the freshness-aware layer composite in alpha_engine.py.
Run: python -m pytest backend/tests/test_factor_engine.py
"""
import sys, os
from datetime import date, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.scoring.factor import Factor, freshness_decay, composite_score


def test_freshness_decay_buckets():
    assert freshness_decay(0) == 1.0
    assert freshness_decay(7) == 1.0
    assert freshness_decay(8) == 0.95
    assert freshness_decay(30) == 0.95
    assert freshness_decay(31) == 0.80
    assert freshness_decay(90) == 0.80
    assert freshness_decay(91) == 0.50
    assert freshness_decay(None) == 0.80  # unknown age is not assumed fresh


def test_missing_factor_excluded_not_scored():
    present = Factor("a", raw_value=10, normalized_score=80, as_of_date=date.today())
    missing = Factor("b", raw_value=None, normalized_score=None)
    result = composite_score([present, missing], {"a": 0.5, "b": 0.5})
    assert result.score == 80
    assert "b" in result.excluded
    assert missing not in result.factors


def test_confidence_weighting_shrinks_contribution():
    high_conf = Factor("a", raw_value=1, normalized_score=100, confidence=1.0, as_of_date=date.today())
    low_conf = Factor("b", raw_value=1, normalized_score=0, confidence=0.1, as_of_date=date.today())
    result = composite_score([high_conf, low_conf], {"a": 0.5, "b": 0.5})
    # low_conf's near-zero weight means the composite should sit close to
    # high_conf's 100, not the naive 50/50 average
    assert result.score > 90


def test_freshness_decay_shrinks_contribution():
    fresh = Factor("a", raw_value=1, normalized_score=100, as_of_date=date.today())
    stale = Factor("b", raw_value=1, normalized_score=0, as_of_date=date.today() - timedelta(days=400))
    result = composite_score([fresh, stale], {"a": 0.5, "b": 0.5})
    # stale carries 0.50x weight vs fresh's 1.0x, so composite should lean
    # toward fresh's 100 rather than sit at the naive midpoint of 50
    assert result.score > 60


def test_layer_redistribution_below_coverage_excludes_composite():
    only_one_of_four = [
        Factor("a", raw_value=1, normalized_score=80, as_of_date=date.today()),
        Factor("b", raw_value=None, normalized_score=None),
        Factor("c", raw_value=None, normalized_score=None),
        Factor("d", raw_value=None, normalized_score=None),
    ]
    result = composite_score(only_one_of_four, {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}, min_coverage=0.3)
    assert result.score is None  # 1/4 = 25% < 30% coverage threshold
    assert result.coverage == 0.25


def test_layer_redistribution_above_coverage_renormalizes():
    two_of_four = [
        Factor("a", raw_value=1, normalized_score=60, as_of_date=date.today()),
        Factor("b", raw_value=1, normalized_score=80, as_of_date=date.today()),
        Factor("c", raw_value=None, normalized_score=None),
        Factor("d", raw_value=None, normalized_score=None),
    ]
    result = composite_score(two_of_four, {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}, min_coverage=0.3)
    assert result.score == 70  # equal weights a/b -> simple average, unaffected by excluded c/d


def test_get_score_breakdown_matches_alpha_score():
    """Regression for the composite-not-renormalized bug: get_score_breakdown
    used to skip dividing by total_weight, silently under-weighting the
    composite whenever any layer was excluded or freshness-discounted, while
    alpha_score() did divide - the two entrypoints must agree."""
    from app.db.database import SessionLocal
    from app.models.stock import Stock
    from app.services.pipeline import get_stock_data_for_scoring
    from app.scoring.alpha_engine import get_score_breakdown, alpha_score

    session = SessionLocal()
    try:
        symbols = [s.symbol for s in session.query(Stock).limit(10).all()]
        checked = 0
        for sym in symbols:
            data = get_stock_data_for_scoring(sym, session)
            if not data:
                continue
            bd = get_score_breakdown(data)
            s2 = alpha_score(data)
            assert abs(bd["total_score"] - s2) < 0.5, f"{sym}: breakdown={bd['total_score']} alpha_score={s2}"
            checked += 1
        assert checked > 0
    finally:
        session.close()


if __name__ == "__main__":
    test_freshness_decay_buckets()
    test_missing_factor_excluded_not_scored()
    test_confidence_weighting_shrinks_contribution()
    test_freshness_decay_shrinks_contribution()
    test_layer_redistribution_below_coverage_excludes_composite()
    test_layer_redistribution_above_coverage_renormalizes()
    test_get_score_breakdown_matches_alpha_score()
    print("All checks passed.")
