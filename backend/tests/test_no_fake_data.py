"""Rule 1 regression check: fields that used to be hardcoded fakes must come
back as None from the live pipeline, and the composite score must actually
use all 8 computed layers (not silently drop 4 of them - see alpha_engine.py
LAYER_WEIGHTS history). Run: python -m pytest backend/tests/test_no_fake_data.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import SessionLocal
from app.models.stock import Stock
from app.services.pipeline import get_stock_data_for_scoring
from app.scoring.alpha_engine import get_score_breakdown, LAYER_WEIGHTS


def test_deleted_fakes_are_none_not_fabricated():
    session = SessionLocal()
    try:
        symbols = [s.symbol for s in session.query(Stock).limit(20).all()]
        checked = 0
        for sym in symbols:
            data = get_stock_data_for_scoring(sym, session)
            if not data:
                continue
            assert data.get("governance_clean") is None
            assert data.get("dilution_rate") is None
            assert data.get("auditor_changed") is None
            checked += 1
        assert checked > 0, "no stocks had price data to check against"
    finally:
        session.close()


def test_delivery_ratio_is_real_not_constant():
    """Phase 2 Task 1: delivery_ratio now has a real source (NSE bhavcopy
    DELIV_PER, app/ingestion/nse_bhavcopy.py) - either None (no history yet
    for that symbol) or a genuine ratio, never a fabricated constant."""
    session = SessionLocal()
    try:
        symbols = [s.symbol for s in session.query(Stock).limit(50).all()]
        values = []
        for sym in symbols:
            data = get_stock_data_for_scoring(sym, session)
            if not data:
                continue
            dr = data.get("delivery_ratio")
            if dr is not None:
                assert dr > 0
                values.append(dr)
        if values:
            assert len(set(round(v, 4) for v in values)) > 1, \
                "delivery_ratio is identical across stocks - looks fabricated"
    finally:
        session.close()


def test_all_computed_layers_are_wired():
    assert set(LAYER_WEIGHTS.keys()) == {
        "growth", "quality", "technical", "forensic",
        "management", "microstructure", "value", "lowvol",
    }
    assert abs(sum(LAYER_WEIGHTS.values()) - 1.0) < 1e-9


def test_score_breakdown_produces_valid_composite():
    session = SessionLocal()
    try:
        symbols = [s.symbol for s in session.query(Stock).limit(10).all()]
        scored = 0
        for sym in symbols:
            data = get_stock_data_for_scoring(sym, session)
            if not data:
                continue
            breakdown = get_score_breakdown(data)
            assert 0 <= breakdown["total_score"] <= 100
            scored += 1
        assert scored > 0
    finally:
        session.close()


if __name__ == "__main__":
    test_deleted_fakes_are_none_not_fabricated()
    test_delivery_ratio_is_real_not_constant()
    test_all_computed_layers_are_wired()
    test_score_breakdown_produces_valid_composite()
    print("All checks passed.")
