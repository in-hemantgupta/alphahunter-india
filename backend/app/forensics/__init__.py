from app.forensics.promoter_behavior import promoter_behavior_score
from app.forensics.pledge_analysis import pledge_score
from app.forensics.equity_dilution import dilution_score
from app.forensics.cashflow_integrity import cashflow_integrity_score

# ponytail: forensics_score() composite and 7 submodules (auditor_risk,
# capital_allocation, related_party, compensation_abuse, insider_transactions,
# working_capital, fraud_probability) were deleted - zero callers anywhere
# outside this package, and every one of them read field names
# (auditor_changed, rpt_growth, compensation_growth, insider_buying/selling,
# receivables_growth, inventory_days, dilution_risk, ...) that pipeline.py
# never populates, so they always returned the same hardcoded constant for
# every stock. The functions kept here are used by
# app.scoring.penalty_engine.forensic_penalty and now return None instead of
# a fabricated score when their inputs are missing.
