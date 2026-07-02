def alternative_score(data, ranker=None, _debug=False):
    news = data.get("news_score") or 0
    sector_rotation = data.get("sector_rotation") or 50
    contract = data.get("contract_score") or 0
    hiring = data.get("hiring_score") or 0
    patent = data.get("patent_score") or 0
    shipment = data.get("shipment_score") or 0
    insider = data.get("insider_trades") or 0
    compensation = data.get("compensation_quality") or 0

    news_score_val = max(0, min(100, news))
    sr_score = max(0, min(100, sector_rotation))
    contract_score_val = max(0, min(100, contract))
    hiring_score_val = max(0, min(100, hiring))
    patent_score_val = max(0, min(100, patent))
    shipment_score_val = max(0, min(100, shipment))
    insider_score = max(0, min(100, 50 + insider * 10))
    comp_score = max(0, min(100, compensation))

    weights = {
        "news_sentiment": 0.25,
        "sector_rotation": 0.20,
        "insider_activity": 0.15,
        "contract_wins": 0.12,
        "hiring_intensity": 0.10,
        "patent_activity": 0.08,
        "shipment_trends": 0.05,
        "management_quality": 0.05,
    }

    score = (
        news_score_val * weights["news_sentiment"] +
        sr_score * weights["sector_rotation"] +
        insider_score * weights["insider_activity"] +
        contract_score_val * weights["contract_wins"] +
        hiring_score_val * weights["hiring_intensity"] +
        patent_score_val * weights["patent_activity"] +
        shipment_score_val * weights["shipment_trends"] +
        comp_score * weights["management_quality"]
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "news_sentiment": {"raw": news, "score": news_score_val, "weight": weights["news_sentiment"]},
                "sector_rotation": {"raw": sector_rotation, "score": sr_score, "weight": weights["sector_rotation"]},
                "insider_activity": {"raw": insider, "score": insider_score, "weight": weights["insider_activity"]},
                "contract_wins": {"raw": contract, "score": contract_score_val, "weight": weights["contract_wins"]},
                "hiring_intensity": {"raw": hiring, "score": hiring_score_val, "weight": weights["hiring_intensity"]},
                "patent_activity": {"raw": patent, "score": patent_score_val, "weight": weights["patent_activity"]},
                "shipment_trends": {"raw": shipment, "score": shipment_score_val, "weight": weights["shipment_trends"]},
                "management_quality": {"raw": compensation, "score": comp_score, "weight": weights["management_quality"]},
            }
        }

    return final
