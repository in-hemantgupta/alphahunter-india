def related_party_score(data):
    """
    Related Party Transaction Engine
    As per RESEARCH_BIBLE.md Section 21.
    """
    rpt_growth = (data.get("rpt_growth") or 0)
    revenue_growth = (data.get("revenue_growth") or 0)

    if rpt_growth > revenue_growth * 2:
        return 20
    elif rpt_growth > revenue_growth:
        return 50
    else:
        return 100
