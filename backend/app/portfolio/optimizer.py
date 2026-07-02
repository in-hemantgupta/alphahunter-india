import numpy as np
from collections import defaultdict
from scipy.optimize import minimize
from app.portfolio.conviction import compute_conviction_weight, normalize_conviction
from app.portfolio.position_sizing import size_position
from app.portfolio.liquidity_tiers import get_market_cap_tier, get_liquidity_allocation_limit


MAX_STOCK = 0.04
MAX_SECTOR = 0.20
MAX_BETA = 1.1
MAX_FACTOR_EXPOSURE = 0.30
MIN_LIQUIDITY_CRORE = 1
BETA_TARGET = 1.0


def optimize_weights(scored_stocks, regime, correlation_matrix=None):
    """Quadratic portfolio optimizer.
    Maximizes alpha, minimizes volatility and correlation overlap.

    scored_stocks: list of dicts with symbol, score, confidence, sector, beta
    regime: current market regime string
    correlation_matrix: optional {sym1: {sym2: corr}}

    Returns: {symbol: weight}
    """
    if not scored_stocks:
        return {}

    # Build candidate list
    candidates = []
    for s in scored_stocks:
        if not s.get("passed_elimination", True):
            continue
        score = s.get("total_score") or s.get("score", 0)
        confidence = s.get("confidence_score", 0.5)
        sector = s.get("sector", "Unknown")
        symbol = s.get("symbol")
        beta = s.get("beta", 1.0)
        market_cap = s.get("market_cap", 0)
        price = s.get("price", 0)

        raw = compute_conviction_weight(score, confidence)
        liquidity_score = s.get("liquidity_score", 0.5)
        dynamic_weight = score / 100 * confidence * liquidity_score

        # Regime adjustment
        if regime == "Bear":
            dynamic_weight *= 0.5
        elif regime == "HighVolatility":
            dynamic_weight *= 0.75

        candidates.append({
            "symbol": symbol,
            "sector": sector,
            "beta": beta,
            "score": score,
            "confidence": confidence,
            "alpha": score * confidence,
            "raw_weight": raw,
            "dynamic_weight": dynamic_weight,
            "market_cap": market_cap,
            "price": price,
        })

    if len(candidates) < 3:
        return {}

    n = min(len(candidates), 100)
    candidates = sorted(candidates, key=lambda x: -x["alpha"])[:n]
    symbols = [c["symbol"] for c in candidates]

    # Expected returns (alpha proxy)
    expected_returns = np.array([c["alpha"] for c in candidates])

    # Covariance matrix (estimated from score similarity if no correlation matrix)
    if correlation_matrix:
        n_sym = len(symbols)
        cov = np.ones((n_sym, n_sym)) * 0.5
        np.fill_diagonal(cov, 1.0)
        for i, s1 in enumerate(symbols):
            for j, s2 in enumerate(symbols):
                if s1 in correlation_matrix and s2 in correlation_matrix[s1]:
                    cov[i][j] = correlation_matrix[s1][s2] ** 2
    else:
        cov = np.eye(len(symbols)) * 0.5
        for i, c in enumerate(candidates):
            cov[i][i] = (1 - c["confidence"]) * 0.5 + 0.1

    # Sector constraints
    sector_indices = defaultdict(list)
    for i, c in enumerate(candidates):
        sector_indices[c["sector"]].append(i)

    # Beta constraint
    betas = np.array([c["beta"] for c in candidates])

    def objective(weights):
        """Maximize alpha - 0.5 * variance - penalty for correlation overlap."""
        ret = -np.dot(weights, expected_returns)
        risk = 0.5 * np.dot(weights, np.dot(cov, weights))
        return ret + risk

    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "ineq", "fun": lambda w: MAX_BETA - np.dot(w, betas)},
    ]

    for sector, indices in sector_indices.items():
        constraints.append({
            "type": "ineq",
            "fun": lambda w, idx=indices: MAX_SECTOR - np.sum(w[idx]),
        })

    bounds = [(0, MAX_STOCK) for _ in range(len(candidates))]
    x0 = np.array([1.0 / min(20, len(candidates))] * len(candidates))

    try:
        result = minimize(
            objective, x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-8},
        )

        if not result.success:
            n_holdings = min(20, len(candidates))
            weights = {candidates[i]["symbol"]: 1.0 / n_holdings for i in range(n_holdings)}
            return weights

        weights = {}
        for i, c in enumerate(candidates):
            w = result.x[i]
            if w > 0.001:
                weights[c["symbol"]] = round(float(w), 4)

        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    except Exception:
        n_holdings = min(20, len(candidates))
        weights = {candidates[i]["symbol"]: 1.0 / n_holdings for i in range(n_holdings)}
        return weights
