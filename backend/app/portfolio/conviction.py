def compute_conviction_weight(score, confidence):
    """Weight by score × confidence.
    score: 0-100
    confidence: 0-1

    High score + high confidence -> high weight
    High score + low confidence -> penalized (incomplete data)
    """
    if score is None:
        return 0
    if confidence is None:
        confidence = 0.3

    return score * confidence


def normalize_conviction(weights_dict):
    """Normalize conviction weights to sum to 1.0.
    weights_dict: {symbol: raw_weight}
    """
    total = sum(weights_dict.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in weights_dict.items()}
