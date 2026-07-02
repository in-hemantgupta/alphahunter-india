def promoter_behavior_score(data):
    """
    Promoter Holding Trend Analysis
    As per RESEARCH_BIBLE.md Section 15.

    Reads quarter-over-quarter promoter_change (the only promoter-trend
    signal actually populated by shareholding ingestion). A prior version
    read promoter_change_3y, a field nothing ever wrote, so this always
    returned the neutral 50 regardless of real promoter behavior.
    """
    promoter_change = data.get("promoter_change")
    if promoter_change is None:
        return None  # Rule 1: no shareholding filing -> exclude

    if promoter_change > 2:
        return 100
    elif promoter_change > 0:
        return 80
    elif promoter_change > -2:
        return 50
    else:
        return 10
