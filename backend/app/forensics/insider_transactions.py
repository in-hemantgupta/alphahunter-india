def insider_score(data):
    """
    Insider Transaction Analysis
    As per RESEARCH_BIBLE.md Section 17.
    """
    insider_buying = (data.get("insider_buying") or 0)
    insider_selling = (data.get("insider_selling") or 0)

    if insider_buying > insider_selling * 2:
        return 100
    elif insider_buying > insider_selling:
        return 70
    elif insider_selling > insider_buying * 2:
        return 20
    else:
        return 50
