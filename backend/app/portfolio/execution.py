"""Execution simulation with India-specific cost model."""

# Cost model (bps)
COST_BPS = {
    "A": 10,    # large cap: 10000cr+
    "B": 30,    # mid cap: 1000-10000cr
    "C": 60,    # small cap: 100-1000cr
    "D": 100,   # micro cap: <100cr
}

IMPACT_BPS = {
    "A": 5,
    "B": 15,
    "C": 30,
    "D": 50,
}

SPREAD_BPS = {
    "A": 5,
    "B": 15,
    "C": 30,
    "D": 50,
}


def get_cost_tier(market_cap):
    """Map market cap to cost tier."""
    if market_cap is None:
        return "D"
    if market_cap >= 10000e7:
        return "A"
    elif market_cap >= 1000e7:
        return "B"
    elif market_cap >= 100e7:
        return "C"
    return "D"


def total_cost_bps(market_cap):
    """Total execution cost in bps (cost + impact + spread)."""
    tier = get_cost_tier(market_cap)
    return COST_BPS[tier] + IMPACT_BPS[tier] + SPREAD_BPS[tier]


def execute_trade(symbol, direction, quantity, price, market_cap=None):
    """Simulate trade execution with costs.
    direction: 'buy' or 'sell'
    Returns: (filled_price, cost_bps)
    """
    bps = total_cost_bps(market_cap)
    cost_pct = bps / 10000

    if direction == "buy":
        filled_price = price * (1 + cost_pct)
    else:
        filled_price = price * (1 - cost_pct)

    return round(filled_price, 2), bps


def simulate_rebalance_cost(current_holdings, target_weights, price_map, market_cap_map):
    """Calculate total cost of rebalance.
    current_holdings: {symbol: weight}
    target_weights: {symbol: weight}
    price_map: {symbol: price}
    market_cap_map: {symbol: market_cap}

    Returns: (total_turnover_pct, total_cost_bps)
    """
    all_symbols = set(current_holdings.keys()) | set(target_weights.keys())
    total_turnover = 0.0
    total_cost = 0

    for sym in all_symbols:
        current_w = current_holdings.get(sym, 0)
        target_w = target_weights.get(sym, 0)
        change = abs(target_w - current_w)
        if change > 0:
            mc = market_cap_map.get(sym)
            direction = "buy" if target_w > current_w else "sell"
            cost_bps = total_cost_bps(mc)
            total_turnover += change
            total_cost += change * cost_bps

    annual_turnover_pct = total_turnover * 100
    avg_cost_bps = total_cost / total_turnover if total_turnover > 0 else 0

    return round(annual_turnover_pct, 1), round(avg_cost_bps, 1)


def realized_pnl(entry_price, exit_price, quantity, direction="buy"):
    """Compute realized PnL for a completed trade."""
    if direction == "buy":
        pnl = (exit_price - entry_price) * quantity
    else:
        pnl = (entry_price - exit_price) * quantity
    return round(pnl, 2)


def unrealized_pnl(entry_price, current_price, quantity):
    """Compute unrealized PnL for an open position."""
    pnl = (current_price - entry_price) * quantity
    return round(pnl, 2)


def cost_drag(total_costs, portfolio_value):
    """Cost drag as percentage of portfolio."""
    if portfolio_value <= 0:
        return 0
    return round(total_costs / portfolio_value * 100, 2)


def turnover_drag(turnover_pct, avg_cost_bps):
    """Annual turnover cost as percentage."""
    return round(turnover_pct * avg_cost_bps / 10000, 2)
