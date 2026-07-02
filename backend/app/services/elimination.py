from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from app.models.price_history import PriceHistory
from app.models.quarterly import QuarterlyFinancials
from app.models.shareholding import ShareholdingPattern
from app.scoring.institutional_score import institutional_score
from app.scoring.alpha_engine import alternative_score, llm_score


def stage_1_liquidity_filter(symbol: str, session: Session) -> Tuple[bool, str]:
    prices = session.query(PriceHistory).filter_by(symbol=symbol).order_by(
        PriceHistory.date.desc()).limit(252).all()

    if not prices:
        return False, "No price data"

    avg_daily_value_rows = [(p.close * p.volume) for p in prices[:30]]
    avg_value = sum(avg_daily_value_rows) / len(avg_daily_value_rows)

    if avg_value < 1_00_00_000:
        return False, f"Liquidity too low: ₹{avg_value/1_00_00_000:.2f}Cr < ₹1Cr"

    # Check trading day coverage: must trade >= 80% of available days
    total_days = len(prices)
    if total_days >= 100:
        zero_volume_days = sum(1 for p in prices if p.volume is None or p.volume == 0)
        trading_pct = (total_days - zero_volume_days) / total_days * 100
        if trading_pct < 80:
            return False, f"Traded only {trading_pct:.0f}% of days (<80%)"

    return True, f"Liquidity OK (avg ₹{avg_value/1_00_00_000:.2f}Cr)"


def stage_2_fundamental_elimination(symbol: str, session: Session) -> Tuple[bool, str]:
    quarterly = session.query(QuarterlyFinancials).filter_by(
        symbol=symbol
    ).order_by(QuarterlyFinancials.quarter.desc()).limit(4).all()

    if not quarterly:
        return False, "No quarterly data"

    latest = quarterly[0]

    roce = latest.roce or 0
    debt_equity = latest.debt_equity or 1

    if roce < 5:
        return False, f"ROCE {roce:.1f}% < 5%"

    if debt_equity > 1.0:
        return False, f"D/E {debt_equity:.2f} > 1.0"

    return True, "Fundamentals OK"


def stage_3_growth_acceleration_filter(symbol: str, session: Session) -> Tuple[bool, str]:
    quarterly = session.query(QuarterlyFinancials).filter_by(
        symbol=symbol
    ).order_by(QuarterlyFinancials.quarter.desc()).limit(4).all()

    if len(quarterly) < 2:
        return False, "Insufficient quarterly data"

    revenues = [q.revenue for q in quarterly if q.revenue]
    if len(revenues) < 2:
        return False, "No revenue data"

    growth_rates = []
    for i in range(len(revenues) - 1):
        if revenues[i+1] > 0:
            growth = ((revenues[i] - revenues[i+1]) / revenues[i+1]) * 100
            growth_rates.append(growth)

    if len(growth_rates) >= 3 and all(growth_rates[i] < growth_rates[i+1] for i in range(len(growth_rates)-1)):
        return False, "Revenue slowing for 3 quarters"

    pats = [q.pat for q in quarterly[:3] if q.pat]
    if len(pats) >= 2 and len(revenues) >= 2:
        pat_trend = pats[0] - pats[1]
        rev_trend = revenues[0] - revenues[1]
        if pat_trend < 0 and rev_trend > 0:
            return False, "PAT falling while revenue rising"

    return True, "Growth OK"


def stage_4_forensics_filter(symbol: str, session: Session) -> Tuple[bool, str]:
    shareholding = session.query(ShareholdingPattern).filter_by(
        symbol=symbol
    ).order_by(ShareholdingPattern.quarter.desc()).limit(2).all()

    if len(shareholding) >= 2:
        latest, prev = shareholding[0], shareholding[1]

        if latest.promoter is not None and prev.promoter is not None:
            promoter_change = latest.promoter - prev.promoter
            if promoter_change < -5:
                return False, f"Promoter holding falling sharply: {promoter_change:.2f}%"

        if latest.pledge is not None and latest.pledge > 10:
            return False, f"Pledge {latest.pledge:.1f}% > 10%"

    return True, "Forensics OK"


def stage_5_microstructure_filter(symbol: str, session: Session, data: Dict) -> Tuple[bool, str]:
    inst_score = institutional_score(data)

    if inst_score < 40:
        return False, f"Institutional score {inst_score:.1f} < 40"

    return True, "Microstructure OK"


def stage_6_alternative_filter(symbol: str, data: Dict) -> Tuple[bool, str]:
    has_real_data = any(data.get(k) for k in ["news_score", "contract_score", "patent_score", "hiring_score", "insider_trades"])
    if not has_real_data:
        return True, "Alternative data unavailable — skipping"

    alt_score = alternative_score(data)
    if alt_score < 40:
        return False, f"Alternative score {alt_score:.1f} < 40"

    return True, "Alternative data OK"


def stage_7_llm_filter(symbol: str, data: Dict) -> Tuple[bool, str]:
    l_score = llm_score(data)
    if l_score is None:
        return True, "LLM analysis unavailable — skipping"

    if l_score < 45:
        return False, f"LLM score {l_score:.1f} < 45"

    return True, "LLM analysis OK"


def stage_8_technical_filter(symbol: str, data: Dict) -> Tuple[bool, str]:
    relative_strength = data.get("relative_strength", 0)
    trend_strength = data.get("trend_strength", 0)
    returns_1y = data.get("returns_1y", 0)

    if returns_1y < -20:
        return False, "Downtrend intact"

    if relative_strength < 40:
        return False, f"Weak relative strength: {relative_strength:.1f}"

    if trend_strength < -0.1:
        return False, "Persistent breakdown"

    return True, "Technical OK"


def run_elimination_pipeline(symbol: str, session: Session, data: Dict) -> Tuple[bool, List[str]]:
    stages = [
        ("Liquidity", lambda: stage_1_liquidity_filter(symbol, session)),
        ("Fundamental", lambda: stage_2_fundamental_elimination(symbol, session)),
        ("Growth", lambda: stage_3_growth_acceleration_filter(symbol, session)),
        ("Forensics", lambda: stage_4_forensics_filter(symbol, session)),
        ("Microstructure", lambda: stage_5_microstructure_filter(symbol, session, data)),
        ("Alternative", lambda: stage_6_alternative_filter(symbol, data)),
        ("LLM", lambda: stage_7_llm_filter(symbol, data)),
        ("Technical", lambda: stage_8_technical_filter(symbol, data)),
    ]

    passed_stages = []
    for stage_name, stage_fn in stages:
        passed, reason = stage_fn()
        if not passed:
            return False, passed_stages + [f"FAILED: {stage_name} - {reason}"]
        passed_stages.append(f"PASSED: {stage_name}")

    return True, passed_stages