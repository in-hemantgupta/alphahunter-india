def penalty_engine(data):

    penalty = 0

    if data.get("promoter_declining", False):

        penalty += 15

    if data.get("pledge_percent", 0) > 10:

        penalty += 35

    if data.get("auditor_changed", False):

        penalty += 40

    if data.get("dilution_rate", 0) > 15:

        penalty += 20

    if data.get("cash_conversion", 1) < 0.6:

        penalty += 25

    if data.get("governance_red_flags", False):

        penalty += 30

    return penalty
