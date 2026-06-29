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

    if pledge_percent == 0:
        pledge_score = 100
    elif pledge_percent < 2:
        pledge_score = 90
    elif pledge_percent < 5:
        pledge_score = 80
    elif pledge_percent < 10:
        pledge_score = 60
    elif pledge_percent < 15:
        pledge_score = 40
    else:
        pledge_score = 10

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

    if capex_efficiency > 30:
        capex_score = 100
    elif capex_efficiency > 20:
        capex_score = 85
    elif capex_efficiency > 10:
        capex_score = 70
    elif capex_efficiency > 5:
        capex_score = 55
    elif capex_efficiency > 0:
        capex_score = 40
    else:
        capex_score = 25

    if operating_cashflow > 0:
        cashflow_quality = 80
    else:
        cashflow_quality = 30

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

    governance_clean = data.get("governance_clean", True)
    governance_score = 85 if governance_clean else 30

    insider_behavior = 60

    compensation_quality = 60

    score = (
        promoter_score * 0.20 +
        pledge_score * 0.10 +
        capital_score * 0.20 +
        capex_score * 0.10 +
        cashflow_quality * 0.15 +
        dilution_score * 0.10 +
        governance_score * 0.15
    )

    return min(100, max(0, score))
