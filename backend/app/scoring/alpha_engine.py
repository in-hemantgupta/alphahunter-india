from app.scoring.fundamental_score import fundamental_score
from app.scoring.growth_score import growth_score
from app.scoring.management_score import management_score
from app.scoring.institutional_score import institutional_score
from app.scoring.technical_score import technical_score
from app.scoring.penalty_engine import penalty_engine


LAYER_WEIGHTS = {
    "fundamental": 0.18,
    "growth": 0.20,
    "quality": 0.18,
    "momentum": 0.14,
    "alternative": 0.10,
    "technical": 0.08,
    "llm": 0.12,
}


def alpha_score(stock):
    f_score = fundamental_score(stock)
    g_score = growth_score(stock)
    q_score = management_score(stock)
    m_score = institutional_score(stock)
    a_score = alternative_score(stock)
    t_score = technical_score(stock)
    l_score = llm_score(stock)

    composite = (
        f_score * LAYER_WEIGHTS["fundamental"] +
        g_score * LAYER_WEIGHTS["growth"] +
        q_score * LAYER_WEIGHTS["quality"] +
        m_score * LAYER_WEIGHTS["momentum"] +
        a_score * LAYER_WEIGHTS["alternative"] +
        t_score * LAYER_WEIGHTS["technical"] +
        l_score * LAYER_WEIGHTS["llm"]
    )

    penalty = penalty_engine(stock)
    final_score = max(0, composite - penalty)

    return min(100, round(final_score, 2))


def alternative_score(stock, _debug=False):
    google_trend = stock.get("google_trend_score") or 0
    contract = stock.get("contract_score") or 0
    shipment = stock.get("shipment_score") or 0
    hiring = stock.get("hiring_score") or 0
    patent = stock.get("patent_score") or 0
    news = stock.get("news_score") or 0
    sector_rotation = stock.get("sector_rotation") or 0

    score = (
        hiring * 0.20 +
        contract * 0.20 +
        shipment * 0.15 +
        patent * 0.10 +
        google_trend * 0.10 +
        sector_rotation * 0.15 +
        news * 0.10
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "hiring": {"raw": "", "score": hiring, "weight": 0.20},
                "government_contracts": {"raw": "", "score": contract, "weight": 0.20},
                "shipment": {"raw": "", "score": shipment, "weight": 0.15},
                "patent": {"raw": "", "score": patent, "weight": 0.10},
                "search_trend": {"raw": "", "score": google_trend, "weight": 0.10},
                "sector_rotation": {"raw": "", "score": sector_rotation, "weight": 0.15},
                "news_velocity": {"raw": "", "score": news, "weight": 0.10},
            }
        }

    return final


def llm_score(stock, _debug=False):
    annual = stock.get("annual_report_score") or 0
    concall = stock.get("concall_score") or 0
    sentiment = stock.get("sentiment_score") or 0
    narrative = stock.get("narrative_score") or 0
    risk = stock.get("risk_score") or 0
    mgmt_confidence = stock.get("management_confidence") or 0
    governance_language = stock.get("governance_language") or 0

    score = (
        annual * 0.20 +
        concall * 0.25 +
        sentiment * 0.10 +
        narrative * 0.15 +
        risk * 0.10 +
        mgmt_confidence * 0.10 +
        governance_language * 0.10
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "annual_report": {"raw": "", "score": annual, "weight": 0.20},
                "concall_analysis": {"raw": "", "score": concall, "weight": 0.25},
                "sentiment": {"raw": "", "score": sentiment, "weight": 0.10},
                "narrative_shift": {"raw": "", "score": narrative, "weight": 0.15},
                "risk_extraction": {"raw": "", "score": risk, "weight": 0.10},
                "management_confidence": {"raw": "", "score": mgmt_confidence, "weight": 0.10},
                "governance_language": {"raw": "", "score": governance_language, "weight": 0.10},
            }
        }

    return final


def get_score_breakdown(data):
    layers = {}
    composite = 0

    for key, weight in LAYER_WEIGHTS.items():
        if key == "fundamental":
            score, dbg = fundamental_score(data, _debug=True)
        elif key == "growth":
            score, dbg = growth_score(data, _debug=True)
        elif key == "quality":
            score, dbg = management_score(data, _debug=True)
        elif key == "momentum":
            score, dbg = institutional_score(data, _debug=True)
        elif key == "alternative":
            score, dbg = alternative_score(data, _debug=True)
        elif key == "technical":
            score, dbg = technical_score(data, _debug=True)
        elif key == "llm":
            score, dbg = llm_score(data, _debug=True)
        else:
            continue

        layers[key] = {
            "score": score,
            "weight": weight,
            "weighted": round(score * weight, 2),
            "components": dbg["components"],
        }
        composite += score * weight

    penalty = penalty_engine(data)
    total = max(0, composite - penalty)

    return {
        "total_score": min(100, round(total, 2)),
        "composite": round(composite, 2),
        "penalty": penalty,
        "layers": layers,
    }


def get_alpha_decision(score):
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