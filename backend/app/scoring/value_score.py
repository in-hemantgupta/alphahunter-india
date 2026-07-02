import math


def value_score(data, ranker=None, _debug=False):
    """Rule 1/5: pb_ratio/ev_ebitda/dividend_yield are not currently computed
    anywhere in pipeline.py (always None) - they used to fall through to a
    hardcoded 50/50/30 "neutral" score on every single stock, which is a
    constant baseline number pretending to be a real reading, diluting the
    real pe_ratio/size signal. Missing components are excluded and the
    remaining weights renormalize instead."""
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

    pe_use = pe if pe is not None else computed_pe

    components = {}  # name -> (score, weight, raw)

    if pe_use is not None and pe_use > 0:
        s = ranker.inverse_pct("pe_ratio", min(pe_use, 100)) if ranker else max(0, 100 - pe_use * 2)
        components["pe_ratio"] = (s, 0.25, pe_use)

    if pb is not None and pb > 0:
        s = ranker.inverse_pct("pb_ratio", min(pb, 20)) if ranker else max(0, 100 - pb * 10)
        components["pb_ratio"] = (s, 0.20, pb)

    if ev_ebitda is not None and ev_ebitda > 0:
        s = ranker.inverse_pct("ev_ebitda", min(ev_ebitda, 50)) if ranker else max(0, 100 - ev_ebitda * 3)
        components["ev_ebitda"] = (s, 0.20, ev_ebitda)

    if dividend_yield is not None:
        components["dividend_yield"] = (min(100, dividend_yield * 20), 0.10, dividend_yield)

    if market_cap is not None and market_cap > 0:
        size_factor = -math.log(market_cap)
        s = ranker.pct("size_factor", size_factor) if ranker else min(100, max(0, 50 + (30 - math.log(market_cap)) * 15))
        components["size_premium"] = (s, 0.25, market_cap)

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
