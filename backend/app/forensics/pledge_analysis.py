def pledge_score(data):
    """
    Pledge Analysis Engine
    As per RESEARCH_BIBLE.md Section 16.
    """
    pledged = data.get("pledge_percent")
    if pledged is None:
        return None  # Rule 1: no filing data -> exclude, don't assume clean

    if pledged == 0:
        return 100
    elif pledged < 5:
        return 70
    elif pledged < 10:
        return 40
    else:
        return 0
