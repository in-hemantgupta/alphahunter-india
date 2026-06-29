def auditor_risk_score(data):
    """
    Auditor Risk Detection
    As per RESEARCH_BIBLE.md Section 20.
    """
    auditor_changed = (data.get("auditor_changed") or False)
    auditor_resigned = (data.get("auditor_resigned") or False)
    qualifications = (data.get("audit_qualifications") or 0)

    if auditor_resigned:
        return 0
    elif auditor_changed:
        return 30
    elif qualifications > 2:
        return 40
    else:
        return 100
