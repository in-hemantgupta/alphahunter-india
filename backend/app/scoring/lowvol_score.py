def lowvol_score(data, ranker=None, _debug=False):
    beta = data.get("beta")
    atr_14 = data.get("atr_14")
    returns_1y = data.get("returns_1y") or 0
    current_price = data.get("current_price")
    high_52w = data.get("high_52w")

    max_dd = None
    if high_52w and high_52w > 0 and current_price and current_price > 0:
        max_dd = (current_price - high_52w) / high_52w * 100

    rolling_vol = data.get("rolling_volatility_60d")

    if ranker:
        beta_score = ranker.inverse_pct("beta", min(abs(beta or 1), 3)) if beta is not None else 50
    else:
        beta_score = max(0, 100 - abs(beta or 1) * 25)

    if rolling_vol is not None and ranker:
        vol_score = ranker.inverse_pct("rolling_vol_60d", min(rolling_vol, 10))
    elif rolling_vol is not None:
        vol_score = max(0, 100 - rolling_vol * 15)
    else:
        vol_score = 50

    if atr_14 is not None and ranker:
        atr_score = ranker.inverse_pct("atr_14", min(atr_14, 10))
    else:
        atr_score = 50

    if max_dd is not None and ranker:
        dd_score = ranker.pct("drawdown_52w", min(max(max_dd, -100), 0))
    elif max_dd is not None:
        dd_score = 50 + max_dd / 2
    else:
        dd_score = 50

    score = (
        beta_score * 0.30 +
        vol_score * 0.30 +
        atr_score * 0.20 +
        dd_score * 0.20
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "beta": {"raw": beta, "score": beta_score, "weight": 0.30},
                "rolling_volatility": {"raw": rolling_vol, "score": vol_score, "weight": 0.30},
                "atr_normalized": {"raw": atr_14, "score": atr_score, "weight": 0.20},
                "drawdown_52w": {"raw": max_dd, "score": dd_score, "weight": 0.20},
            }
        }

    return final
