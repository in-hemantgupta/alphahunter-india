def dilution_score(data):
    """
    Equity Dilution Engine
    As per RESEARCH_BIBLE.md Section 18.
    """
    dilution_rate = (data.get("dilution_rate_3y") or 0)

    if dilution_rate < 5:
        return 100
    elif dilution_rate < 10:
        return 70
    elif dilution_rate < 15:
        return 40
    else:
        return 10
