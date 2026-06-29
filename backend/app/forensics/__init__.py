from app.forensics.promoter_behavior import promoter_behavior_score
from app.forensics.pledge_analysis import pledge_score
from app.forensics.insider_transactions import insider_score
from app.forensics.equity_dilution import dilution_score
from app.forensics.capital_allocation import capital_allocation_score
from app.forensics.auditor_risk import auditor_risk_score
from app.forensics.related_party import related_party_score
from app.forensics.compensation_abuse import compensation_score
from app.forensics.cashflow_integrity import cashflow_integrity_score
from app.forensics.working_capital import working_capital_score
from app.forensics.fraud_probability import fraud_probability_score


def forensics_score(data):
    """
    Management Forensics Composite Score
    As per RESEARCH_BIBLE.md Sections 12-27.
    """
    promoter = promoter_behavior_score(data)
    pledge = pledge_score(data)
    insider = insider_score(data)
    dilution = dilution_score(data)
    capital = capital_allocation_score(data)
    auditor = auditor_risk_score(data)
    rpt = related_party_score(data)
    comp = compensation_score(data)
    cashflow = cashflow_integrity_score(data)
    working = working_capital_score(data)
    fraud = fraud_probability_score(data)

    # Weighted composite
    composite = (
        promoter * 0.15 +
        pledge * 0.12 +
        insider * 0.10 +
        dilution * 0.08 +
        capital * 0.15 +
        auditor * 0.10 +
        rpt * 0.08 +
        comp * 0.07 +
        cashflow * 0.08 +
        working * 0.07
    )

    # Fraud penalty
    fraud_penalty = fraud * 0.5

    return max(0, min(100, composite - fraud_penalty))
