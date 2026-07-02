def technical_score(data, ranker=None, _debug=False):
    rs = data.get("relative_strength") or 50
    trend_strength = data.get("trend_strength") or 0
    compression_pattern = data.get("compression_pattern", False)
    breakout_prob = data.get("breakout_probability") or 0.3
    volume_confirmation = data.get("volume_confirmation", False)
    vwap_defense = data.get("vwap_defense", False)

    # Merged momentum: 12-month return excluding last month
    returns_1y = data.get("returns_1y") or 0
    recent_returns = data.get("recent_returns")
    mom_12m_1m = returns_1y
    if recent_returns and len(recent_returns) >= 22:
        one_month_return = sum(recent_returns[:22]) * 100
        mom_12m_1m = returns_1y - one_month_return

    if ranker:
        rs_score = ranker.pct("relative_strength", rs)
        trend_score = ranker.pct("trend_strength", trend_strength)
        compression_score = 85 if compression_pattern else 40
        breakout_score = ranker.pct("breakout_probability", min(breakout_prob, 1))
        vol_score = 80 if volume_confirmation else 40
        mom_score = ranker.pct("mom_12m_1m", min(max(mom_12m_1m, -100), 200))
    else:
        rs_score = min(100, max(0, rs))
        trend_score = min(100, max(0, (trend_strength + 1) * 50))
        compression_score = 85 if compression_pattern else 40
        breakout_score = min(100, breakout_prob * 100)
        vol_score = 80 if volume_confirmation else 40
        mom_score = min(100, max(0, (mom_12m_1m + 50) / 2))

    vwap_score = 80 if vwap_defense else 40

    score = (
        rs_score * 0.20 +
        trend_score * 0.15 +
        compression_score * 0.12 +
        breakout_score * 0.12 +
        vol_score * 0.12 +
        vwap_score * 0.09 +
        mom_score * 0.20
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "relative_strength": {"raw": rs, "score": rs_score, "weight": 0.20},
                "trend_strength": {"raw": trend_strength, "score": trend_score, "weight": 0.15},
                "compression": {"raw": compression_pattern, "score": compression_score, "weight": 0.12},
                "breakout_probability": {"raw": breakout_prob, "score": breakout_score, "weight": 0.12},
                "volume_confirmation": {"raw": volume_confirmation, "score": vol_score, "weight": 0.12},
                "vwap_defense": {"raw": vwap_defense, "score": vwap_score, "weight": 0.09},
                "momentum_12m_excl_1m": {"raw": round(mom_12m_1m, 1), "score": mom_score, "weight": 0.20},
            }
        }

    return final
