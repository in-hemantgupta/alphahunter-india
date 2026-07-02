def cashflow_integrity_score(data):
    """
    Cash Flow Integrity Engine
    As per RESEARCH_BIBLE.md Section 23.
    """
    cash_conversion = data.get("cash_conversion")
    if cash_conversion is None:
        return None  # Rule 1: no OCF/PAT data -> exclude, don't assume clean conversion

    if cash_conversion >= 0.8:
        return 100
    elif cash_conversion >= 0.6:
        return 70
    elif cash_conversion >= 0.4:
        return 40
    else:
        return 10
