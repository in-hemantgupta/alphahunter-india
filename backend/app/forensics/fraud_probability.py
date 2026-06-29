def fraud_probability_score(data):
    """
    Fraud Probability Heuristics
    As per RESEARCH_BIBLE.md Section 25.
    """
    auditor_risk = (data.get("auditor_risk") or 0)
    cashflow_risk = (data.get("cashflow_risk") or 0)
    promoter_behavior = (data.get("promoter_behavior_risk") or 0)
    receivable_risk = (data.get("receivable_risk") or 0)
    dilution_risk = (data.get("dilution_risk") or 0)

    fraud_probability = (
        auditor_risk * 0.20 +
        cashflow_risk * 0.20 +
        promoter_behavior * 0.20 +
        receivable_risk * 0.20 +
        dilution_risk * 0.20
    )

    return min(100, fraud_probability)
