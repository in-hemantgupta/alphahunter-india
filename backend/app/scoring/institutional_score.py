def institutional_score(data, ranker=None, _debug=False):
    """Rule 1/5: delivery_ratio has been None for every stock since the fake
    volume-heuristic proxy that used to compute it was deleted (pipeline.py) -
    `delivery_ratio or 1` was silently turning that into a constant
    delivery_score=20 fed into every stock's microstructure layer forever.
    Missing components are excluded and remaining weights renormalize."""
    delivery_ratio = data.get("delivery_ratio")
    volume_ratio = data.get("volume_ratio")
    volume_high = data.get("volume_high", False)
    price_flat = data.get("price_flat", False)
    vwap_defense = data.get("vwap_defense", False)
    price_compression = data.get("price_compression", False)
    seller_exhaustion = data.get("seller_exhaustion", False)
    fii_change = data.get("fii_change")
    dii_change = data.get("dii_change")

    components = {}  # name -> (score, weight, raw)

    if delivery_ratio is not None:
        s = ranker.pct("delivery_ratio", min(delivery_ratio, 5)) if ranker else min(100, (delivery_ratio - 0.5) * 40)
        components["delivery_ratio"] = (s, 0.20, delivery_ratio)

    if volume_ratio is not None:
        s = ranker.pct("volume_ratio", min(volume_ratio, 10)) if ranker else min(100, volume_ratio * 25)
        components["volume_anomaly"] = (s, 0.10, volume_ratio)

    # volume_high/price_flat/vwap_defense/price_compression/seller_exhaustion
    # are deterministic booleans computed from price history whenever prices
    # exist (see pipeline.py) - never "unknown", so a plain default is fine.
    if volume_high and price_flat:
        float_absorption = 90
    elif volume_high:
        float_absorption = 65
    elif price_flat:
        float_absorption = 55
    else:
        float_absorption = 35
    components["float_absorption"] = (float_absorption, 0.15, {"volume_high": volume_high, "price_flat": price_flat})

    components["vwap_defense"] = (80 if vwap_defense else 35, 0.10, vwap_defense)
    components["price_compression"] = (80 if price_compression else 35, 0.10, price_compression)
    components["seller_exhaustion"] = (80 if seller_exhaustion else 35, 0.10, seller_exhaustion)

    if fii_change is not None:
        components["fii_change"] = (min(100, max(0, 50 + fii_change * 5)), 0.15, fii_change)

    if dii_change is not None:
        components["dii_change"] = (min(100, max(0, 50 + dii_change * 5)), 0.10, dii_change)

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
