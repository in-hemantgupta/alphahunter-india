def technical_score(data, _debug=False):

    rs = data.get("relative_strength") or 50
    trend_strength = data.get("trend_strength") or 0
    compression_pattern = data.get("compression_pattern", False)
    breakout_prob = data.get("breakout_probability") or 0.3
    volume_confirmation = data.get("volume_confirmation", False)

    if rs >= 90:
        rs_score = 100
    elif rs >= 80:
        rs_score = 90
    elif rs >= 70:
        rs_score = 75
    elif rs >= 60:
        rs_score = 60
    elif rs >= 50:
        rs_score = 45
    elif rs >= 40:
        rs_score = 30
    else:
        rs_score = 15

    if trend_strength >= 0.3:
        trend_score = 100
    elif trend_strength >= 0.2:
        trend_score = 85
    elif trend_strength >= 0.1:
        trend_score = 70
    elif trend_strength >= 0.05:
        trend_score = 55
    elif trend_strength >= 0:
        trend_score = 40
    elif trend_strength >= -0.1:
        trend_score = 25
    else:
        trend_score = 10

    compression_score = 85 if compression_pattern else 40

    if breakout_prob >= 0.8:
        breakout_score = 100
    elif breakout_prob >= 0.7:
        breakout_score = 85
    elif breakout_prob >= 0.6:
        breakout_score = 70
    elif breakout_prob >= 0.5:
        breakout_score = 55
    elif breakout_prob >= 0.4:
        breakout_score = 40
    else:
        breakout_score = 25

    vol_score = 80 if volume_confirmation else 40

    score = (
        rs_score * 0.30 +
        trend_score * 0.25 +
        compression_score * 0.20 +
        breakout_score * 0.15 +
        vol_score * 0.10
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "relative_strength": {"raw": rs, "score": rs_score, "weight": 0.30},
                "trend_strength": {"raw": trend_strength, "score": trend_score, "weight": 0.25},
                "compression": {"raw": compression_pattern, "score": compression_score, "weight": 0.20},
                "breakout_probability": {"raw": breakout_prob, "score": breakout_score, "weight": 0.15},
                "volume_confirmation": {"raw": volume_confirmation, "score": vol_score, "weight": 0.10},
            }
        }

    return final