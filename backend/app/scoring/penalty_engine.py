from app.forensics.cashflow_integrity import cashflow_integrity_score
from app.forensics.working_capital import working_capital_score
from app.forensics.promoter_behavior import promoter_behavior_score
from app.forensics.equity_dilution import dilution_score
from app.forensics.fraud_probability import fraud_probability_score


def _hard_caps(data) -> list:
    """Force max score = 30 if any extreme risk detected.
    Only triggers when ACTUAL DATA exists — missing data NEVER triggers a hard cap.
    Only truly extreme risks qualify: promoter pledge >75%, negative CFO 4Q,
    promoter selling >10%. Other red flags are softer penalties."""
    caps = []

    pledge = data.get("pledge_percent")
    if pledge is not None and pledge > 75:
        caps.append("promoter_pledge_exceeds_75pct")

    cfo_4q_count = data.get("cfo_negative_4q_count", 0)
    if cfo_4q_count is not None and cfo_4q_count >= 4:
        caps.append("negative_cfo_4q")

    promoter_change = data.get("promoter_change")
    if promoter_change is not None and promoter_change < -10:
        caps.append("promoter_selling_gt_10pct")

    return caps


FORENSIC_CHECK_FIELDS = [
    "cash_flow_operations", "pat", "pledge_percent", "promoter_change",
    "debt", "interest_expense", "ebitda", "receivables", "revenue",
    "operating_cashflow", "cash_conversion_ratio",
]


def forensic_penalty(data, ranker=None):
    """Compute penalty (0-100) from forensic signals.
    If <3 forensic-relevant fields populated, returns insufficient_data signal
    so caller drops the forensic layer and reduces confidence by 30%.
    Returns: (total_penalty, detail_dict, hard_caps_list)"""
    populated = sum(1 for f in FORENSIC_CHECK_FIELDS if data.get(f) is not None)
    total_fields = len(FORENSIC_CHECK_FIELDS)
    if populated < 3:
        return 0, {
            "_insufficient_data": True,
            "populated_fields": populated,
            "confidence_multiplier": 0.70,
        }, []

    sector = data.get("sector")
    penalties = []

    hard_cap_list = _hard_caps(data)
    if hard_cap_list:
        penalties.append(("hard_cap_trigger", 50))

    pledge = data.get("pledge_percent") or 0
    if ranker:
        pledge_rank = ranker.pct("pledge_percent", min(pledge, 100))
        if pledge_rank > 80:
            penalties.append(("high_pledge", (pledge_rank - 80) / 20 * 30))
    else:
        if pledge > 25:
            penalties.append(("high_pledge", min(30, pledge * 0.5)))

    promoter_change = data.get("promoter_change") or 0
    if ranker:
        pc_rank = ranker.inverse_pct("promoter_change", min(promoter_change, 20))
        if pc_rank > 70:
            penalties.append(("promoter_selling", (pc_rank - 70) / 30 * 25))
    else:
        if promoter_change < -5:
            penalties.append(("promoter_selling", min(25, abs(promoter_change) * 2)))

    cashflow = data.get("operating_cashflow") or 0
    pat = data.get("pat") or 0
    if pat and pat > 0:
        cash_conversion = min(cashflow / pat, 2) if cashflow > 0 else 0
    else:
        cash_conversion = 0.5 if cashflow > 0 else 0
    if ranker:
        cc_rank = ranker.inverse_pct("cash_conversion_ratio", cash_conversion, sector=sector)
        if cc_rank > 75:
            penalties.append(("cash_mismatch", (cc_rank - 75) / 25 * 20))
    else:
        if cash_conversion < 0.5:
            penalties.append(("cash_mismatch", 20))
        elif cash_conversion < 0.7:
            penalties.append(("cash_mismatch", 10))

    try:
        f_score = fraud_probability_score(data)
        if f_score > 50:
            penalties.append(("fraud_risk", f_score * 0.25))
    except:
        pass

    try:
        cf_score = cashflow_integrity_score(data)
        if cf_score < 40:
            penalties.append(("cashflow_integrity", (40 - cf_score) * 0.5))
    except:
        pass

    try:
        wc_score = working_capital_score(data)
        if wc_score < 40:
            penalties.append(("working_capital", (40 - wc_score) * 0.5))
    except:
        pass

    try:
        d_score = dilution_score(data)
        if d_score < 40:
            penalties.append(("dilution_risk", (40 - d_score) * 0.5))
    except:
        pass

    try:
        pb_score = promoter_behavior_score(data)
        if pb_score < 40:
            penalties.append(("promoter_risk", (40 - pb_score) * 0.5))
    except:
        pass

    debt_val = data.get("debt") or 0
    interest = data.get("interest_expense") or 0
    ebitda_val = data.get("ebitda") or 0
    if ebitda_val and ebitda_val > 0 and interest > 0:
        coverage = ebitda_val / interest
        if coverage < 2:
            penalties.append(("debt_service", min(25, (2 - coverage) * 10)))
    elif debt_val > 0 and ebitda_val and ebitda_val > 0:
        debt_ebitda = debt_val / ebitda_val
        if debt_ebitda > 5:
            penalties.append(("debt_burden", min(20, (debt_ebitda - 5) * 3)))

    receivables = data.get("receivables") or 0
    revenue_val = data.get("revenue") or 0
    if revenue_val and revenue_val > 0 and receivables and receivables > 0:
        rec_ratio = receivables / revenue_val
        if rec_ratio > 1:
            penalties.append(("receivable_overhang", min(20, (rec_ratio - 1) * 20)))

    # PAT declining: 2 consecutive negative quarters
    pat = data.get("pat")
    pat_prev = data.get("pat_prev")
    if pat is not None and pat_prev is not None and pat < 0 and pat_prev < 0:
        penalties.append(("pat_declining", 20))

    # Revenue declining: 3 consecutive declines
    rev = data.get("revenue")
    rev_p1 = data.get("revenue_prev")
    rev_p2 = data.get("revenue_prev2")
    if rev is not None and rev_p1 is not None and rev_p2 is not None:
        if rev < rev_p1 and rev_p1 < rev_p2:
            penalties.append(("revenue_declining", 15))

    total_penalty = sum(p for _, p in penalties)

    # Blend penalty toward 50 when data is sparse to prevent forensic inflation
    confidence_factor = min(1.0, populated / total_fields)
    if total_penalty == 0 and confidence_factor < 0.7:
        total_penalty = 50 * (1 - confidence_factor)

    detail = {k: round(v, 1) for k, v in penalties}
    detail["populated_fields"] = populated

    return min(100, total_penalty), detail, hard_cap_list


def confidence_penalty(data):
    """Apply score penalty for low confidence / missing data.
    Penalizes stocks with low liquidity, low confidence, or high missing ratio.
    Returns: penalty (0-25) to subtract from composite BEFORE sigmoid."""
    penalty = 0

    # Liquidity penalty: stocks with low daily value
    avg_val = data.get("avg_daily_value")
    if avg_val is not None and avg_val > 0:
        if avg_val < 50_000_000:  # <5cr daily
            penalty += 5
        elif avg_val < 200_000_000:  # <20cr daily
            penalty += 2

    # Missing ratio penalty: what % of layer keys are populated?
    from app.scoring.alpha_engine import _KEY_MAP, LAYER_WEIGHTS
    total_keys = sum(len(v) for v in _KEY_MAP.values())
    present = 0
    for key in _KEY_MAP:
        for k in _KEY_MAP[key]:
            if data.get(k) is not None:
                present += 1
    missing_ratio = 1 - (present / max(total_keys, 1))
    if missing_ratio > 0.7:
        penalty += 10
    elif missing_ratio > 0.5:
        penalty += 5
    elif missing_ratio > 0.3:
        penalty += 2
    
    # Low market cap penalty
    mcap = data.get("market_cap")
    if mcap is not None and mcap > 0:
        if mcap < 500_000_000:  # <50cr
            penalty += 5
        elif mcap < 2_000_000_000:  # <200cr
            penalty += 2
    
    return min(25, penalty)


def penalty_engine(data, ranker=None, _debug=False):
    penalty, detail, hard_caps = forensic_penalty(data, ranker)
    if _debug:
        return penalty, detail, hard_caps
    return penalty
