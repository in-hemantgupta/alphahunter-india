def management_score(data):

    promoter_change = data.get("promoter_change") or 0
    pledge_percent = data.get("pledge_percent") or 0
    roce_trend = data.get("roce_trend") or 0
    capex_efficiency = data.get("capex_efficiency") or 0
    operating_cashflow = data.get("operating_cashflow") or 0
    dilution_rate = data.get("dilution_rate") or 0

    if promoter_change > 5:
        promoter_score = 100
    elif promoter_change > 2:
        promoter_score = 90
    elif promoter_change > 0:
        promoter_score = 80
    elif promoter_change > -2:
        promoter_score = 50
    elif promoter_change > -5:
        promoter_score = 30
    else:
        promoter_score = 10

    if roce_trend > 5:
        capital_score = 100
    elif roce_trend > 3:
        capital_score = 90
    elif roce_trend > 1:
        capital_score = 75
    elif roce_trend > 0:
        capital_score = 60
    elif roce_trend > -2:
        capital_score = 40
    else:
        capital_score = 20

    if operating_cashflow > 0:
        cashflow_quality = 80
    else:
        cashflow_quality = 30

    governance_clean = data.get("governance_clean", True)
    governance_score = 85 if governance_clean else 30

    insider_trades = data.get("insider_trades", 0)
    if insider_trades > 0:
        insider_behavior = 80
    elif insider_trades == 0:
        insider_behavior = 60
    else:
        insider_behavior = 30

    if dilution_rate > 15:
        dilution_score = 20
    elif dilution_rate > 10:
        dilution_score = 40
    elif dilution_rate > 5:
        dilution_score = 60
    elif dilution_rate > 0:
        dilution_score = 80
    else:
        dilution_score = 90

    compensation_quality = data.get("compensation_quality", 60)

    score = (
        promoter_score * 0.20 +
        capital_score * 0.20 +
        governance_score * 0.15 +
        cashflow_quality * 0.15 +
        insider_behavior * 0.10 +
        dilution_score * 0.10 +
        compensation_quality * 0.10
    )

    return min(100, max(0, score))
