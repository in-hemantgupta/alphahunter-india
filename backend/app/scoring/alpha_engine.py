from app.scoring.fundamental_score import fundamental_score
from app.scoring.growth_score import growth_score
from app.scoring.management_score import management_score
from app.scoring.institutional_score import institutional_score
from app.scoring.technical_score import technical_score
from app.scoring.alternative_score_module import alternative_score
from app.scoring.value_score import value_score
from app.scoring.quality_score import quality_score
from app.scoring.lowvol_score import lowvol_score
from app.scoring.penalty_engine import penalty_engine, forensic_penalty, FORENSIC_CHECK_FIELDS, confidence_penalty

__all__ = [
    'fundamental_score', 'growth_score', 'management_score',
    'institutional_score', 'technical_score',
    'value_score', 'quality_score',
    'lowvol_score',
    'penalty_engine', 'forensic_penalty', 'alpha_score', 'get_score_breakdown',
    'LAYER_WEIGHTS',
]

LAYER_WEIGHTS = {
    "growth": 0.35,
    "technical": 0.30,
    "forensic": 0.25,
    "value": 0.10,
}

_FUNDAMENTAL_KEYS = ["roce", "debt_equity", "operating_margin", "margin_stability", "revenue", "pat"]
_GROWTH_KEYS = ["revenue_acceleration", "pat_acceleration", "margin_expansion", "cashflow_improvement", "eps", "revenue"]
_QUALITY_KEYS = ["roce", "roe", "debt_equity", "operating_margin"]
_TECHNICAL_KEYS = ["relative_strength", "trend_strength", "compression_pattern", "breakout_probability", "mom_12m_1m"]
_MICROSTRUCTURE_KEYS = ["delivery_ratio", "volume_ratio", "vwap_defense"]
_MANAGEMENT_KEYS = ["promoter_change", "pledge_percent", "roce_trend", "operating_cashflow", "dilution_rate"]
_FORENSIC_KEYS = ["cash_conversion_ratio", "pledge_percent", "promoter_change", "debt", "interest_expense", "ebitda", "receivables", "revenue"]
_LOWVOL_KEYS = ["beta", "atr_14", "high_52w", "current_price"]
_VALUE_KEYS = ["pe_ratio", "pb_ratio", "ev_ebitda", "dividend_yield", "market_cap"]

_KEY_MAP = {
    "quality": _QUALITY_KEYS,
    "growth": _GROWTH_KEYS,
    "technical": _TECHNICAL_KEYS,
    "microstructure": _MICROSTRUCTURE_KEYS,
    "management": _MANAGEMENT_KEYS,
    "forensic": _FORENSIC_KEYS,
    "lowvol": _LOWVOL_KEYS,
    "value": _VALUE_KEYS,
}

_SCORE_FN_MAP = {
    "quality": quality_score,
    "growth": growth_score,
    "technical": technical_score,
    "microstructure": institutional_score,
    "management": management_score,
    "lowvol": lowvol_score,
    "value": value_score,
}


def _layer_populated(data, keys):
    present = 0
    for k in keys:
        v = data.get(k)
        if v is not None and v != 0 and v != "" and v is not False:
            present += 1
    return present, len(keys)


def _compute_confidence(data, total_keys_count):
    populated = 0
    for key in LAYER_WEIGHTS:
        keys = _KEY_MAP.get(key, [])
        p, _ = _layer_populated(data, keys)
        populated += p
    data_ratio = min(1.0, populated / max(total_keys_count, 1))

    freshness = 1.0
    if data.get("recent_returns") is not None:
        freshness = min(1.0, len([r for r in data["recent_returns"] if r is not None]) / max(len(data["recent_returns"]), 1))

    liquidity = 1.0
    lscore = data.get("liquidity_score")
    if lscore is not None:
        liquidity = min(1.0, lscore / 100)

    mcap = data.get("market_cap")
    mcap_factor = 1.0
    if mcap is not None and mcap > 0:
        mcap_factor = min(1.0, mcap / 100_000_000_000)

    return round(data_ratio * freshness * liquidity * mcap_factor, 3)


def alpha_score(stock_data, ranker=None):
    weights = dict(LAYER_WEIGHTS)
    layer_scores = {}
    available_weight = 0.0

    for key in weights:
        if key == "forensic":
            pen, detail, _ = forensic_penalty(stock_data, ranker)
            if detail.get("_insufficient_data"):
                present, total = 0, 1
                score = 50
            else:
                score = max(0, 100 - pen)
                present, total = 1, 1
                populated = detail.get("populated_fields", len(FORENSIC_CHECK_FIELDS))
                conf = min(1.0, populated / len(FORENSIC_CHECK_FIELDS))
                if conf < 0.7:
                    score = score * conf + 50 * (1 - conf)
        else:
            score, present, total = _score_layer(key, stock_data, ranker)

        if total > 0 and present / total >= 0.3:
            layer_scores[key] = max(0, min(100, score))
            available_weight += weights[key]
        else:
            layer_scores[key] = None

    composite = 0.0
    total_weight = 0.0
    for key, score in layer_scores.items():
        if score is not None:
            effective_weight = weights[key]
            composite += score * effective_weight
            total_weight += effective_weight

    if total_weight > 0:
        composite /= total_weight

    penalty, _, _ = forensic_penalty(stock_data, ranker)
    conf_penalty = confidence_penalty(stock_data)
    total_penalty = min(40, penalty + conf_penalty)
    penalty_adjusted = composite * max(0, 1 - total_penalty / 100)

    import math
    # Asymmetric sigmoid: gentle below 50 (/14), steep above 50 (/7)
    deviation = penalty_adjusted - 50
    denom = 13 if deviation < 0 else 7
    stretched = 100 / (1 + math.exp(-deviation / denom))
    score = min(100, max(0, round(stretched, 2)))

    _, _, hard_caps = forensic_penalty(stock_data, ranker)
    if hard_caps:
        score = min(score, 30)

    # Apply forensic confidence penalty when insufficient data
    total_keys = sum(len(k) for k in _KEY_MAP.values())
    conf = _compute_confidence(stock_data, total_keys)
    _, forensic_detail, _ = forensic_penalty(stock_data, ranker)
    if forensic_detail.get("_insufficient_data"):
        conf *= forensic_detail.get("confidence_multiplier", 0.70)
    # Graduated floor: no penalty → 10, all others → 8, absolute 5
    # Graduated floor: no penalty → 7 (avoids cluster), absolute 5
    if conf_penalty == 0 and conf > 0.02 and score < 7:
        score = 7
    if score < 5:
        score = 5

    return score


def _score_layer(layer, data, ranker):
    fn = _SCORE_FN_MAP.get(layer)
    if fn:
        s, _ = fn(data, ranker, _debug=True)
        p, t = _layer_populated(data, _KEY_MAP.get(layer, []))
        return s, p, t
    return 0, 0, 1


def get_score_breakdown(data, ranker=None):
    weights = dict(LAYER_WEIGHTS)
    layers = {}
    composite = 0
    total_weight = 0.0

    for key in weights:
        if key == "forensic":
            pen, detail, hard_caps = forensic_penalty(data, ranker)
            if detail.get("_insufficient_data"):
                present, total = 0, 1
                score = 50
                components = {}
            else:
                score = max(0, 100 - pen)
                present, total = 1, 1
                populated = detail.get("populated_fields", len(FORENSIC_CHECK_FIELDS))
                conf = min(1.0, populated / len(FORENSIC_CHECK_FIELDS))
                if conf < 0.7:
                    score = score * conf + 50 * (1 - conf)
                components = {k: {"raw": "", "score": v, "weight": 0} for k, v in detail.items() if k != "populated_fields"}
        else:
            score, dbg = _score_layer_debug(key, data, ranker)
            present, total = dbg["present"], dbg["total"]
            components = dbg["components"]

        if total > 0 and present / total >= 0.3:
            layers[key] = {
                "score": score,
                "weight": weights[key],
                "weighted": round(score * weights[key], 2),
                "components": components,
                "data_quality": f"{present}/{total}",
            }
            composite += score * weights[key]
            total_weight += weights[key]

    if total_weight > 0:
        for key in layers:
            layers[key]["effective_weight"] = round(layers[key]["weight"] / total_weight, 4)
            layers[key]["effective_weighted"] = round(layers[key]["score"] * layers[key]["weight"] / total_weight, 2)

    penalty, pen_detail, _ = forensic_penalty(data, ranker)
    conf_penalty = confidence_penalty(data)
    total_penalty = min(40, penalty + conf_penalty)
    penalty_adjusted = composite * max(0, 1 - total_penalty / 100)

    # Sigmoid stretch: map [0,100] to wider distribution
    # Asymmetric: gentle below 50 (/14), steep above 50 (/7)
    import math
    deviation = penalty_adjusted - 50
    denom = 13 if deviation < 0 else 7
    stretched = 100 / (1 + math.exp(-deviation / denom))
    final_score = min(100, max(0, round(stretched, 2)))

    # Apply hard caps: score forced <= 30 if any extreme risk triggered
    if hard_caps:
        final_score = min(final_score, 30)

    # Apply forensic confidence penalty when insufficient data
    total_keys = sum(len(k) for k in _KEY_MAP.values())
    confidence = _compute_confidence(data, total_keys)
    _, forensic_detail, _ = forensic_penalty(data, ranker)
    if forensic_detail.get("_insufficient_data"):
        confidence *= forensic_detail.get("confidence_multiplier", 0.70)
    # Graduated floor: no penalty → 7 (avoids cluster), absolute 5
    if conf_penalty == 0 and confidence > 0.02 and final_score < 7:
        final_score = 7
    if final_score < 5:
        final_score = 5

    return {
        "total_score": final_score,
        "composite": round(composite, 2),
        "penalty": round(penalty, 1),
        "penalty_detail": pen_detail,
        "hard_caps": hard_caps,
        "confidence": round(confidence, 3),
        "layers": layers,
    }


def llm_score(stock, _debug=False):
    annual = stock.get("annual_report_score") or 0
    concall = stock.get("concall_score") or 0
    sentiment = stock.get("sentiment_score") or 0
    narrative = stock.get("narrative_score") or 0
    risk = stock.get("risk_score") or 0
    mgmt_confidence = stock.get("management_confidence") or 0
    governance_language = stock.get("governance_language") or 0

    score = (
        annual * 0.20 +
        concall * 0.25 +
        sentiment * 0.10 +
        narrative * 0.15 +
        risk * 0.10 +
        mgmt_confidence * 0.10 +
        governance_language * 0.10
    )

    final = min(100, max(0, score))

    if _debug:
        return final, {
            "score": final,
            "components": {
                "annual_report": {"raw": "", "score": annual, "weight": 0.20},
                "concall_analysis": {"raw": "", "score": concall, "weight": 0.25},
                "sentiment": {"raw": "", "score": sentiment, "weight": 0.10},
                "narrative_shift": {"raw": "", "score": narrative, "weight": 0.15},
                "risk_extraction": {"raw": "", "score": risk, "weight": 0.10},
                "management_confidence": {"raw": "", "score": mgmt_confidence, "weight": 0.10},
                "governance_language": {"raw": "", "score": governance_language, "weight": 0.10},
            }
        }

    return final


def _score_layer_debug(layer, data, ranker):
    fn = _SCORE_FN_MAP.get(layer)
    if fn:
        score, dbg = fn(data, ranker, _debug=True)
        p, t = _layer_populated(data, _KEY_MAP.get(layer, []))
        dbg["present"] = p
        dbg["total"] = t
        return score, dbg
    return 0, {"present": 0, "total": 1, "components": {}}


BATCH_NORMALIZE_LAYERS = ["quality", "growth", "technical", "microstructure", "value", "lowvol", "forensic"]


def batch_normalize_scores(scored_data_list: list[dict]) -> list[dict]:
    """Apply cross-sectional z-score normalization to layer scores.
    Recomputes composite and final score for each stock.
    Winsorizes at ±3σ before sigmoid."""
    import math

    if not scored_data_list:
        return scored_data_list

    # Collect all layer scores
    layer_values = {layer: [] for layer in BATCH_NORMALIZE_LAYERS}
    for sd in scored_data_list:
        breakdown = sd.get("_breakdown")
        if not breakdown:
            continue
        layers = breakdown.get("layers", {})
        for layer in BATCH_NORMALIZE_LAYERS:
            ls = layers.get(layer, {}).get("score")
            if ls is not None:
                layer_values[layer].append(ls)

    # Compute z-scores per layer
    layer_stats = {}
    for layer, vals in layer_values.items():
        if len(vals) < 10:
            layer_stats[layer] = {"mean": 50.0, "std": 10.0}
            continue
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        std = math.sqrt(var) if var > 0 else 10.0
        layer_stats[layer] = {"mean": mean, "std": std}

    # Replace layer scores with z-score mapped values
    weights = LAYER_WEIGHTS
    for sd in scored_data_list:
        breakdown = sd.get("_breakdown")
        if not breakdown:
            continue
        layers = breakdown.get("layers", {})

        composite = 0.0
        total_weight = 0.0
        for layer, info in layers.items():
            raw_score = info.get("score")
            if raw_score is None:
                continue
            stats = layer_stats.get(layer, {"mean": 50.0, "std": 10.0})
            z = (raw_score - stats["mean"]) / stats["std"] if stats["std"] > 0 else 0.0
            z = max(-3.0, min(3.0, z))
            z_score = 100 / (1 + math.exp(-z))
            info["score"] = round(z_score, 2)
            info["z_normalized"] = True
            weighted = z_score * weights.get(layer, 0)
            info["weighted"] = round(weighted, 2)
            composite += weighted
            total_weight += weights.get(layer, 0)

        if total_weight > 0:
            composite /= total_weight

        data_sd = sd
        penalty, pen_detail, _ = forensic_penalty(data_sd, None)
        conf_penalty = confidence_penalty(data_sd)
        total_penalty = penalty + conf_penalty * 1.5
        penalty_adjusted = composite * max(0, 1 - total_penalty / 100)
        deviation = penalty_adjusted - 50
        denom = 14 if deviation < 0 else 7
        stretched = 100 / (1 + math.exp(-deviation / denom))
        final_score = min(100, max(0, round(stretched, 2)))

        _, _, hard_caps = forensic_penalty(data_sd, None)
        if hard_caps:
            final_score = min(final_score, 30)

        total_keys = sum(len(k) for k in _KEY_MAP.values())
        conf = _compute_confidence(data_sd, total_keys)
        _, forensic_detail, _ = forensic_penalty(data_sd, None)
        if forensic_detail.get("_insufficient_data"):
            conf *= forensic_detail.get("confidence_multiplier", 0.70)
        # Graduated floor: no penalty → 7 (avoids cluster), absolute 5
        if conf_penalty == 0 and conf > 0.02 and final_score < 7:
            final_score = 7
        if final_score < 5:
            final_score = 5

        if total_weight > 0:
            for layer in layers:
                layers[layer]["effective_weight"] = round(weights.get(layer, 0) / total_weight, 4)

        breakdown["total_score"] = final_score
        breakdown["composite"] = round(composite, 2)
        breakdown["penalty"] = round(penalty, 1)
        breakdown["penalty_detail"] = pen_detail
        breakdown["hard_caps"] = hard_caps
        breakdown["confidence"] = round(conf, 3)
        sd["total_score"] = final_score
        sd["confidence_score"] = conf
        sd["composite"] = composite

    return scored_data_list
