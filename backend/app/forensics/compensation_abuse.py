def compensation_score(data):
    """
    Compensation Abuse Detection
    As per RESEARCH_BIBLE.md Section 22.
    """
    profit_growth = (data.get("profit_growth") or 0)
    comp_growth = (data.get("compensation_growth") or 0)

    if comp_growth > profit_growth * 3:
        return 20
    elif comp_growth > profit_growth * 2:
        return 50
    else:
        return 100
