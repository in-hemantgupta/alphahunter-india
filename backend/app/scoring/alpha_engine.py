from datetime import date
from app.scoring.growth_score import growth_score
from app.scoring.management_score import management_score
from app.scoring.institutional_score import institutional_score
from app.scoring.technical_score import technical_score
from app.scoring.alternative_score_module import alternative_score
from app.scoring.value_score import value_score
from app.scoring.quality_score import quality_score
from app.scoring.lowvol_score import lowvol_score
from app.scoring.penalty_engine import penalty_engine, forensic_penalty, FORENSIC_CHECK_FIELDS, confidence_penalty
from app.scoring.factor import freshness_decay, Factor

__all__ = [
    'growth_score', 'management_score',
    'institutional_score', 'technical_score',
    'value_score', 'quality_score',
    'lowvol_score',
    'penalty_engine', 'forensic_penalty', 'alpha_score', 'get_score_breakdown',
    'LAYER_WEIGHTS',
]

# Rule 5: every layer that _KEY_MAP/_SCORE_FN_MAP can actually compute must be
# wired here. quality/management/microstructure/lowvol were computed every run
# but silently dropped from the composite because they weren't in this dict -
# a wired-with-no-effect bug, worse than not computing them at all since it
# made the score look 8-factor while only 4 factors ever moved it.
# Layers with <30% field coverage for a given stock are excluded at scoring
# time (see _score_layer) and the remaining weights are renormalized - that's
# the dynamic redistribution called for by Rule 5, not something bolted on.
LAYER_WEIGHTS = {
    "growth": 0.20,
    "quality": 0.15,
    "technical": 0.15,
    "forensic": 0.15,
    "management": 0.10,
    "microstructure": 0.10,
    "value": 0.08,
    "lowvol": 0.07,
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

# Rule 5/9: which data domain each layer's freshness should be judged by.
# Forensic draws on both financials and shareholding - conservatively use
# whichever of the two is staler, not the fresher one.
_LAYER_AS_OF_FIELD = {
    "growth": "_financials_as_of",
    "quality": "_financials_as_of",
    "technical": "_price_as_of",
    "lowvol": "_price_as_of",
    "microstructure": "_price_as_of",
    "value": "_price_as_of",
    "management": "_shareholding_as_of",
}


def _layer_as_of(layer, data):
    if layer == "forensic":
        candidates = [data.get("_financials_as_of"), data.get("_shareholding_as_of")]
        candidates = [c for c in candidates if c is not None]
        return min(candidates) if candidates else None
    field = _LAYER_AS_OF_FIELD.get(layer)
    return data.get(field) if field else None


def _layer_confidence(layer, data):
    if layer == "management" and data.get("_shareholding_confidence") is not None:
        return data["_shareholding_confidence"]
    if layer in ("growth", "quality") and data.get("_financials_confidence") is not None:
        return data["_financials_confidence"]
    return 1.0


def _layer_freshness_multiplier(layer, data):
    as_of = _layer_as_of(layer, data)
    freshness_days = (date.today() - as_of).days if as_of else None
    return freshness_decay(freshness_days) * _layer_confidence(layer, data)


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
            effective_weight = weights[key] * _layer_freshness_multiplier(key, stock_data)
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
            as_of = _layer_as_of(key, data)
            freshness_mult = _layer_freshness_multiplier(key, data)
            adjusted_weight = weights[key] * freshness_mult
            layers[key] = {
                "score": score,
                "weight": weights[key],
                "weighted": round(score * weights[key], 2),
                "components": components,
                "data_quality": f"{present}/{total}",
                "as_of_date": as_of.isoformat() if as_of else None,
                "freshness_multiplier": round(freshness_mult, 3),
                "confidence": round(_layer_confidence(key, data), 3),
            }
            composite += score * adjusted_weight
            total_weight += adjusted_weight

    if total_weight > 0:
        # Rule 5: renormalize by the weight actually available, same as
        # alpha_score() - previously missing here, so composite silently
        # under-counted whenever any layer was excluded or freshness-discounted
        # instead of redistributing that weight across the remaining layers.
        composite /= total_weight
        for key in layers:
            adjusted_weight = layers[key]["weight"] * layers[key]["freshness_multiplier"]
            layers[key]["effective_weight"] = round(adjusted_weight / total_weight, 4)
            layers[key]["effective_weighted"] = round(layers[key]["score"] * adjusted_weight / total_weight, 2)

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
    """Rule 1/5: LLM annual-report/concall analysis (app/llm_engine) hasn't run
    for most of the universe yet - `annual_report_score or 0` used to treat
    "never analyzed" identically to "analyzed and scored 0", which made
    elimination.py's stage_7_llm_filter (threshold 45) auto-eliminate every
    stock lacking LLM coverage regardless of its actual quality. Returns None
    when no LLM field is populated at all, so the caller can skip the gate
    instead of failing it on absent data."""
    fields = {
        "annual_report_score": ("annual_report", 0.20),
        "concall_score": ("concall_analysis", 0.25),
        "sentiment_score": ("sentiment", 0.10),
        "narrative_score": ("narrative_shift", 0.15),
        "risk_score": ("risk_extraction", 0.10),
        "management_confidence": ("management_confidence", 0.10),
        "governance_language": ("governance_language", 0.10),
    }

    components = {}
    for key, (label, weight) in fields.items():
        val = stock.get(key)
        if val is not None:
            components[label] = (val, weight, val)

    if not components:
        if _debug:
            return None, {"score": None, "components": {}}
        return None

    total_weight = sum(w for _, w, _ in components.values())
    score = sum(s * w for s, w, _ in components.values()) / total_weight

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


def _score_layer_debug(layer, data, ranker):
    fn = _SCORE_FN_MAP.get(layer)
    if fn:
        score, dbg = fn(data, ranker, _debug=True)
        p, t = _layer_populated(data, _KEY_MAP.get(layer, []))
        dbg["present"] = p
        dbg["total"] = t
        return score, dbg
    return 0, {"present": 0, "total": 1, "components": {}}


BATCH_NORMALIZE_LAYERS = list(LAYER_WEIGHTS.keys())


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
            adjusted_weight = weights.get(layer, 0) * _layer_freshness_multiplier(layer, sd)
            weighted = z_score * adjusted_weight
            info["weighted"] = round(weighted, 2)
            composite += weighted
            total_weight += adjusted_weight

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
                adjusted_weight = weights.get(layer, 0) * _layer_freshness_multiplier(layer, sd)
                layers[layer]["effective_weight"] = round(adjusted_weight / total_weight, 4)

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
