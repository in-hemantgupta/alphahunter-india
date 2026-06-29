from app.scoring.fundamental_score import fundamental_score
from app.scoring.growth_score import growth_score
from app.scoring.management_score import management_score
from app.scoring.institutional_score import institutional_score
from app.scoring.technical_score import technical_score
from app.scoring.penalty_engine import penalty_engine


def alpha_score(stock):
    """
    FGQMATL Framework - Unified Alpha Score
    Combines 7 layers as per RESEARCH_BIBLE.md Section 90.

    Formula:
        alpha_score = (
            fundamental_score * 0.18 +
            growth_score * 0.20 +
            management_score * 0.18 +
            institutional_score * 0.14 +
            alternative_score * 0.10 +
            technical_score * 0.08 +
            llm_score * 0.12
        )

    Output: 0 -> 100 score
    """
    # Calculate individual layer scores
    f_score = fundamental_score(stock)
    g_score = growth_score(stock)
    q_score = management_score(stock)
    m_score = institutional_score(stock)
    a_score = alternative_score(stock)
    t_score = technical_score(stock)
    l_score = llm_score(stock)

    # Apply FGQMATL weights
    composite = (
        f_score * 0.18 +
        g_score * 0.20 +
        q_score * 0.18 +
        m_score * 0.14 +
        a_score * 0.10 +
        t_score * 0.08 +
        l_score * 0.12
    )

    # Apply penalties
    penalty = penalty_engine(stock)
    final_score = max(0, composite - penalty)

    return min(100, round(final_score, 2))


def alternative_score(stock):
    """
    Alternative Data Score - Layer 5 of FGQMATL
    Per RESEARCH_BIBLE.md Section 58.
    """
    google_trend = stock.get("google_trend_score") or 0
    contract = stock.get("contract_score") or 0
    shipment = stock.get("shipment_score") or 0
    hiring = stock.get("hiring_score") or 0
    patent = stock.get("patent_score") or 0
    news = stock.get("news_score") or 0

    score = (
        hiring * 0.20 +
        contract * 0.20 +
        shipment * 0.15 +
        patent * 0.10 +
        google_trend * 0.10 +
        news * 0.10 +
        60 * 0.15
    )

    return min(100, max(0, score))


def llm_score(stock):
    """
    LLM Intelligence Score - Layer 7 of FGQMATL
    Per RESEARCH_BIBLE.md Section 75.
    """
    annual = stock.get("annual_report_score") or 0
    concall = stock.get("concall_score") or 0
    governance = stock.get("governance_score") or 0
    narrative = stock.get("narrative_score") or 0
    risk = stock.get("risk_score") or 0
    mgmt_confidence = stock.get("management_confidence") or 0

    score = (
        annual * 0.20 +
        concall * 0.25 +
        governance * 0.10 +
        narrative * 0.15 +
        risk * 0.10 +
        mgmt_confidence * 0.10 +
        60 * 0.10
    )

    return min(100, max(0, score))


def get_alpha_decision(score):
    """
    Alpha Thresholds as per RESEARCH_BIBLE.md Section 91.
    Returns decision based on score.
    """
    if score < 50:
        return "REJECT", "Weak opportunity"
    elif score < 65:
        return "IGNORE", "Average quality"
    elif score < 75:
        return "WATCHLIST", "Interesting candidate"
    elif score < 85:
        return "RESEARCH_PRIORITY", "Strong candidate"
    elif score < 92:
        return "PORTFOLIO_CANDIDATE", "High conviction hidden alpha"
    else:
        return "MAXIMUM_PRIORITY", "Exceptional asymmetric opportunity"
