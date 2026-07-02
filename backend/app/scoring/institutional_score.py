def institutional_score(data, ranker=None, _debug=False):
    delivery_ratio = data.get("delivery_ratio") or 1
    volume_ratio = data.get("volume_ratio") or 1
    volume_high = data.get("volume_high", False)
    price_flat = data.get("price_flat", False)
    vwap_defense = data.get("vwap_defense", False)
    price_compression = data.get("price_compression", False)
    seller_exhaustion = data.get("seller_exhaustion", False)
    fii_change = data.get("fii_change")
    dii_change = data.get("dii_change")

    if ranker:
        delivery_score = ranker.pct("delivery_ratio", min(delivery_ratio, 5))
        volume_score = ranker.pct("volume_ratio", min(volume_ratio, 10))
    else:
        delivery_score = min(100, (delivery_ratio - 0.5) * 40)
        volume_score = min(100, volume_ratio * 25)

    if volume_high and price_flat:
        float_absorption = 90
    elif volume_high:
        float_absorption = 65
    elif price_flat:
        float_absorption = 55
    else:
        float_absorption = 35

    vwap_score = 80 if vwap_defense else 35
    compression_score = 80 if price_compression else 35
    exhaustion_score = 80 if seller_exhaustion else 35

    fii_score = 50
    dii_score = 50
    if fii_change is not None:
        fii_score = min(100, max(0, 50 + fii_change * 5))
    if dii_change is not None:
        dii_score = min(100, max(0, 50 + dii_change * 5))

    score = (
        delivery_score * 0.20 +
        float_absorption * 0.15 +
        volume_score * 0.10 +
        vwap_score * 0.10 +
        compression_score * 0.10 +
        exhaustion_score * 0.10 +
        fii_score * 0.15 +
        dii_score * 0.10
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "delivery_ratio": {"raw": delivery_ratio, "score": delivery_score, "weight": 0.20},
                "float_absorption": {"raw": {"volume_high": volume_high, "price_flat": price_flat}, "score": float_absorption, "weight": 0.15},
                "volume_anomaly": {"raw": volume_ratio, "score": volume_score, "weight": 0.10},
                "vwap_defense": {"raw": vwap_defense, "score": vwap_score, "weight": 0.10},
                "price_compression": {"raw": price_compression, "score": compression_score, "weight": 0.10},
                "seller_exhaustion": {"raw": seller_exhaustion, "score": exhaustion_score, "weight": 0.10},
                "fii_change": {"raw": fii_change, "score": fii_score, "weight": 0.15},
                "dii_change": {"raw": dii_change, "score": dii_score, "weight": 0.10},
            }
        }

    return final
