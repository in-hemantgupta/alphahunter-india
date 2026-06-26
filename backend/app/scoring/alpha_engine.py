from app.scoring.fundamental_score import fundamental_score
from app.scoring.growth_score import growth_score
from app.scoring.management_score import management_score
from app.scoring.penalty_engine import penalty_engine
from app.microstructure.microstructure_engine import microstructure_score
from app.alternative_data.alternative_data_engine import alternative_score
from app.technical.relative_strength import relative_strength_score
from app.technical.breakout_detection import breakout_score
from app.technical.volatility_analysis import volatility_score
from app.technical.volume_accumulation import volume_accumulation_score
from app.technical.base_detection import base_formation_score


def _compute_technical_score(stock):
    rs = relative_strength_score(stock.get("stock_return", 0), stock.get("benchmark_return", 0))
    bo = breakout_score(stock.get("current_price", 0), stock.get("high_52w", 1))
    vol = volatility_score(stock.get("recent_returns", []))
    va = volume_accumulation_score(stock.get("volume_20d", 1), stock.get("volume_90d", 1))
    base = base_formation_score(stock.get("price_series", []))
    raw = rs + bo + vol + va + base
    return min(100, raw * 3.3)


def alpha_score(stock):
    fundamental = fundamental_score(stock)
    growth = growth_score(stock)
    management = management_score(stock)
    institutional = microstructure_score(stock)
    alternative = alternative_score(stock)
    technical = _compute_technical_score(stock)
    llm = stock.get("llm_score", 0)
    penalty = penalty_engine(stock)

    final = (
        fundamental * 0.18
        + growth * 0.20
        + management * 0.18
        + institutional * 0.14
        + alternative * 0.10
        + technical * 0.08
        + llm * 0.12
        - penalty
    )

    return max(0, min(100, final))
