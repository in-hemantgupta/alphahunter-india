import math
from collections import defaultdict


class PercentileRanker:
    """Computes percentile ranks for numeric metrics across all stocks.
    Supports both universe-level and sector-level ranking.
    
    Sector-level ranking compares stocks only within the same sector,
    which is essential for financial metrics like ROCE, operating margin,
    debt/equity that vary naturally across sectors.
    
    Universe-level ranking is appropriate for price/technical signals
    like relative strength, trend strength, and volume patterns."""

    def __init__(self, all_data: list[dict]):
        self._metrics: dict[str, list[float]] = {}
        self._sector_metrics: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

        for data in all_data:
            sector = data.get("sector", "Unknown")
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    if key not in self._metrics:
                        self._metrics[key] = []
                    self._metrics[key].append(value)
                    self._sector_metrics[sector][key].append(value)

    def percentile(self, metric: str, value, higher_is_better: bool = True, sector: str = None) -> float:
        if sector and sector in self._sector_metrics:
            values = self._sector_metrics[sector].get(metric)
        else:
            values = self._metrics.get(metric)

        if not values or value is None:
            return 50

        count = len(values)
        less = sum(1 for v in values if v < value)
        equal = sum(1 for v in values if v == value)
        rank = ((less + 0.5 * equal) / count) * 100
        return rank if higher_is_better else 100 - rank

    def pct(self, metric: str, value, sector: str = None) -> float:
        return self.percentile(metric, value, sector=sector)

    def inverse_pct(self, metric: str, value, sector: str = None) -> float:
        return self.percentile(metric, value, higher_is_better=False, sector=sector)

    def zscore(self, metric: str, value, sector: str = None) -> float:
        """Compute z-score for a value, optionally sector-normalized.
        Returns z-score clamped to [-3, 3], or 0 if insufficient data."""
        if sector and sector in self._sector_metrics:
            values = self._sector_metrics[sector].get(metric)
        else:
            values = self._metrics.get(metric)

        if not values or value is None or len(values) < 5:
            return 0.0

        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(var) if var > 0 else 1.0
        return max(-3.0, min(3.0, (value - mean) / std))

    def z_to_score(self, metric: str, value, sector: str = None, higher_is_better: bool = True) -> float:
        """Convert value to 0-100 score via z-score → sigmoid mapping."""
        z = self.zscore(metric, value, sector)
        if not higher_is_better:
            z = -z
        return 100 / (1 + math.exp(-z))
