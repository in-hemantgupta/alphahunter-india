def alternative_score(data, ranker=None, _debug=False):
    """Rule 1/5: insider_trades is real (Phase 2 Task 3, SEBI PIT disclosures
    via app/ingestion/nse_insider_pit.py) but still None for symbols with no
    filings in the trailing window - that's an honest "no signal", not
    missing wiring. compensation_quality has no data source anywhere in the
    system. news/contract/hiring/patent/shipment only exist once the
    alt-data pipeline has run for a stock - `x or 0` used to fold all of
    these into the weighted average as fabricated zeros. Missing components
    are excluded and remaining weights renormalize. Called from
    elimination.py's stage_6, which already skips this entirely when zero
    alt-data fields are present - this handles the partial-coverage case
    the same way."""
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

    raw = {
        "news_sentiment": data.get("news_score"),
        "sector_rotation": data.get("sector_rotation"),
        "insider_activity": data.get("insider_trades"),
        "contract_wins": data.get("contract_score"),
        "hiring_intensity": data.get("hiring_score"),
        "patent_activity": data.get("patent_score"),
        "shipment_trends": data.get("shipment_score"),
        "management_quality": data.get("compensation_quality"),
    }

    components = {}
    for name, val in raw.items():
        if val is None:
            continue
        s = max(0, min(100, 50 + val * 10)) if name == "insider_activity" else max(0, min(100, val))
        components[name] = (s, weights[name], val)

    total_weight = sum(w for _, w, _ in components.values())
    score = sum(s * w for s, w, _ in components.values()) / total_weight if total_weight > 0 else 50

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                name: {"raw": raw, "score": s, "weight": w}
                for name, (s, w, raw) in components.items()
            },
        }

    return final
