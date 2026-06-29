def promoter_behavior_score(data):
    """
    Promoter Holding Trend Analysis
    As per RESEARCH_BIBLE.md Section 15.
    """
    promoter_change = (data.get("promoter_change_3y") or 0)

    if promoter_change > 2:
        return 100
    elif promoter_change > 0:
        return 80
    elif promoter_change > -2:
        return 50
    else:
        return 10
