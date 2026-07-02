from sqlalchemy import Column, String, Float
from app.db.base import Base


class QuarterlyFinancials(Base):
    __tablename__ = "quarterly_financials"

    symbol = Column(String, primary_key=True)
    quarter = Column(String, primary_key=True)
    revenue = Column(Float)
    ebitda = Column(Float)
    operating_profit = Column(Float)
    pat = Column(Float)
    eps = Column(Float)
    roce = Column(Float)
    roe = Column(Float)
    debt_equity = Column(Float)
    operating_margin = Column(Float)
    cash_flow_operations = Column(Float)
    free_cash_flow = Column(Float)
    debt = Column(Float)
    interest_expense = Column(Float)
    inventory = Column(Float)
    receivables = Column(Float)
    # P1B — expanded columns
    total_assets = Column(Float)
    total_equity = Column(Float)
    current_assets = Column(Float)
    current_liabilities = Column(Float)
    depreciation = Column(Float)
    tax_expense = Column(Float)
    employee_cost = Column(Float)
    raw_material_cost = Column(Float)
    cash_equivalents = Column(Float)
    capex = Column(Float)
