"""Rule 5/9: a single place that turns "N layer scores + how stale/reliable
each one is" into one composite number, with the exclusion+redistribution
logic in one spot instead of copy-pasted per caller.

Deliberately NOT wrapping every scalar in every scoring module (quality_score,
management_score, ...) in a Factor - those already exclude missing sub-fields
and renormalize remaining weights via their own components dict (see
management_score.py), which is the same math with less indirection. Wrapping
~40 individual fields across 8 files in Factor objects would be pure
representation churn with no behavior change. Factor is used where it adds
real capability: combining the 8 layer scores in alpha_engine.py, where
freshness now genuinely varies (price data updates daily, shareholding
quarterly) and needs to discount stale layers rather than trust them equally.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


def freshness_decay(freshness_days: Optional[int]) -> float:
    """freshness_days=None means we don't know when the underlying data was
    captured - Rule 1 forbids assuming that means "fresh", so unknown gets
    the same conservative multiplier as the 30-90d bucket, not a free pass."""
    if freshness_days is None:
        return 0.80
    if freshness_days <= 7:
        return 1.0
    if freshness_days <= 30:
        return 0.95
    if freshness_days <= 90:
        return 0.80
    return 0.50


@dataclass
class Factor:
    name: str
    raw_value: Optional[float]
    normalized_score: Optional[float]  # 0-100; None = not computable, excluded from composite
    confidence: float = 1.0            # 0-1, source reliability (not freshness)
    as_of_date: Optional[date] = None
    source: Optional[str] = None

    @property
    def freshness_days(self) -> Optional[int]:
        if self.as_of_date is None:
            return None
        return (date.today() - self.as_of_date).days

    @property
    def effective_weight_multiplier(self) -> float:
        return max(0.0, min(1.0, self.confidence)) * freshness_decay(self.freshness_days)


@dataclass
class CompositeScore:
    score: Optional[float]
    total_weight: float
    coverage: float             # present / total, 0-1
    excluded: list = field(default_factory=list)
    factors: list = field(default_factory=list)  # Factors that contributed


def composite_score(factors: list[Factor], weights: dict, min_coverage: float = 0.3) -> CompositeScore:
    """Rule 5: factors with normalized_score=None are excluded; if fewer than
    min_coverage of the given factors are usable, the whole composite is
    excluded (score=None) rather than scored on a rump sample. Remaining
    factors are weighted by weights[name] * confidence * freshness_decay,
    then renormalized against each other (dynamic redistribution)."""
    total = len(factors)
    present = [f for f in factors if f.normalized_score is not None]
    excluded = [f.name for f in factors if f.normalized_score is None]
    coverage = (len(present) / total) if total else 0.0

    if total == 0 or coverage < min_coverage:
        return CompositeScore(score=None, total_weight=0.0, coverage=coverage, excluded=excluded, factors=[])

    weighted_sum = 0.0
    total_weight = 0.0
    used = []
    for f in present:
        w = weights.get(f.name, 0.0) * f.effective_weight_multiplier
        if w <= 0:
            excluded.append(f.name)
            continue
        weighted_sum += f.normalized_score * w
        total_weight += w
        used.append(f)

    score = (weighted_sum / total_weight) if total_weight > 0 else None
    return CompositeScore(score=score, total_weight=total_weight, coverage=coverage, excluded=excluded, factors=used)


def _demo():
    fresh = Factor("a", raw_value=1, normalized_score=80, as_of_date=date.today())
    stale = Factor("b", raw_value=1, normalized_score=80, as_of_date=date(2020, 1, 1))
    missing = Factor("c", raw_value=None, normalized_score=None)

    assert freshness_decay(None) == 0.80
    assert freshness_decay(3) == 1.0
    assert freshness_decay(20) == 0.95
    assert freshness_decay(60) == 0.80
    assert freshness_decay(400) == 0.50

    # missing factor excluded, remaining two redistribute weight 1:1 (equal
    # scores) but stale contributes less absolute weight than fresh
    result = composite_score([fresh, stale, missing], {"a": 0.5, "b": 0.5, "c": 1.0})
    assert result.score == 80  # both present factors score 80, weighted avg is 80 regardless of multiplier
    assert "c" in result.excluded
    assert result.coverage == 2 / 3

    # below-coverage composite excluded entirely
    only_missing = composite_score([missing, missing], {"c": 1.0})
    assert only_missing.score is None

    print("factor.py self-check passed.")


if __name__ == "__main__":
    _demo()
