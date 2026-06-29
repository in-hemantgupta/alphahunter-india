def working_capital_score(data):
    """
    Working Capital Stress Engine
    As per RESEARCH_BIBLE.md Section 24.
    """
    receivables_growth = (data.get("receivables_growth") or 0)
    revenue_growth = (data.get("revenue_growth") or 0)
    inventory_days = (data.get("inventory_days") or 0)

    if receivables_growth > revenue_growth * 2:
        return 30
    elif inventory_days > 90:
        return 50
    else:
        return 100
