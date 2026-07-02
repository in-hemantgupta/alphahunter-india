def dilution_score(data):
    """
    Equity Dilution Engine
    As per RESEARCH_BIBLE.md Section 18.
    """
    dilution_rate = data.get("dilution_rate")
    if dilution_rate is None:
        return None  # Rule 1: no share-count history -> exclude, don't assume no dilution

    if dilution_rate < 5:
        return 100
    elif dilution_rate < 10:
        return 70
    elif dilution_rate < 15:
        return 40
    else:
        return 10
