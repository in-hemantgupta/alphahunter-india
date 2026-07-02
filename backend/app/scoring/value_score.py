def value_score(data, ranker=None, _debug=False):
    pe = data.get("pe_ratio")
    pb = data.get("pb_ratio")
    ev_ebitda = data.get("ev_ebitda")
    dividend_yield = data.get("dividend_yield")
    market_cap = data.get("market_cap")
    eps = data.get("eps")
    current_price = data.get("current_price")

    computed_pe = None
    if eps is not None and eps > 0 and current_price is not None:
        computed_pe = current_price / eps

    pe_use = pe or computed_pe

    if ranker:
        pe_score = ranker.inverse_pct("pe_ratio", min(pe_use, 100)) if pe_use else 50
        pb_score = ranker.inverse_pct("pb_ratio", min(pb, 20)) if pb else 50
        ev_score = ranker.inverse_pct("ev_ebitda", min(ev_ebitda, 50)) if ev_ebitda else 50
    else:
        pe_score = max(0, 100 - (pe_use or 20) * 2) if pe_use else 50
        pb_score = max(0, 100 - (pb or 3) * 10) if pb else 50
        ev_score = max(0, 100 - (ev_ebitda or 15) * 3) if ev_ebitda else 50
    dy_score = min(100, (dividend_yield or 0) * 20) if dividend_yield else 30

    size_factor = None
    if market_cap and market_cap > 0:
        import math
        size_factor = -math.log(market_cap)

    size_score = 50
    if size_factor is not None and ranker:
        size_score = ranker.pct("size_factor", size_factor)
    elif size_factor is not None:
        size_score = min(100, max(0, 50 + (30 - math.log(market_cap)) * 15))

    score = (
        pe_score * 0.25 +
        pb_score * 0.20 +
        ev_score * 0.20 +
        dy_score * 0.10 +
        size_score * 0.25
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "pe_ratio": {"raw": pe_use, "score": pe_score, "weight": 0.25},
                "pb_ratio": {"raw": pb, "score": pb_score, "weight": 0.20},
                "ev_ebitda": {"raw": ev_ebitda, "score": ev_score, "weight": 0.20},
                "dividend_yield": {"raw": dividend_yield, "score": dy_score, "weight": 0.10},
                "size_premium": {"raw": market_cap, "score": size_score, "weight": 0.25},
            }
        }

    return final
