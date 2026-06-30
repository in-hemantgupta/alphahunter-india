def institutional_score(data, _debug=False):

    delivery_ratio = data.get("delivery_ratio") or 1
    volume_ratio = data.get("volume_ratio") or 1
    volume_high = data.get("volume_high", False)
    price_flat = data.get("price_flat", False)
    vwap_defense = data.get("vwap_defense", False)
    price_compression = data.get("price_compression", False)
    seller_exhaustion = data.get("seller_exhaustion", False)
    bulk_deal_positive = data.get("bulk_deal_positive", False)

    if delivery_ratio >= 2.5:
        delivery_score = 100
    elif delivery_ratio >= 2.0:
        delivery_score = 90
    elif delivery_ratio >= 1.5:
        delivery_score = 75
    elif delivery_ratio >= 1.2:
        delivery_score = 60
    elif delivery_ratio >= 1.0:
        delivery_score = 45
    else:
        delivery_score = 25

    if volume_high and price_flat:
        float_absorption = 90
    elif volume_high:
        float_absorption = 65
    elif price_flat:
        float_absorption = 55
    else:
        float_absorption = 35

    if volume_ratio >= 4:
        volume_anomaly = 100
    elif volume_ratio >= 3:
        volume_anomaly = 85
    elif volume_ratio >= 2:
        volume_anomaly = 70
    elif volume_ratio >= 1.5:
        volume_anomaly = 55
    elif volume_ratio >= 1.0:
        volume_anomaly = 40
    else:
        volume_anomaly = 25

    vwap_score = 80 if vwap_defense else 35
    compression_score = 80 if price_compression else 35
    exhaustion_score = 80 if seller_exhaustion else 35
    bulk_score = 90 if bulk_deal_positive else 30

    score = (
        delivery_score * 0.25 +
        float_absorption * 0.20 +
        volume_anomaly * 0.15 +
        vwap_score * 0.15 +
        compression_score * 0.10 +
        exhaustion_score * 0.10 +
        bulk_score * 0.05
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "delivery_ratio": {"raw": delivery_ratio, "score": delivery_score, "weight": 0.25},
                "float_absorption": {"raw": {"volume_high": volume_high, "price_flat": price_flat}, "score": float_absorption, "weight": 0.20},
                "volume_anomaly": {"raw": volume_ratio, "score": volume_anomaly, "weight": 0.15},
                "vwap_defense": {"raw": vwap_defense, "score": vwap_score, "weight": 0.15},
                "price_compression": {"raw": price_compression, "score": compression_score, "weight": 0.10},
                "seller_exhaustion": {"raw": seller_exhaustion, "score": exhaustion_score, "weight": 0.10},
                "bulk_deal": {"raw": bulk_deal_positive, "score": bulk_score, "weight": 0.05},
            }
        }

    return final