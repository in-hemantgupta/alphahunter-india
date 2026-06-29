import pandas as pd
from app.portfolio.risk_engine \

    import risk_score

from app.portfolio.position_sizing \

    import size_position


def build_portfolio(

    ranked_stocks
):

    portfolio = []

    for stock in ranked_stocks:

        risk = \

            risk_score(stock)

        allocation = \

            size_position(

                stock["score"],

                risk
            )

        portfolio.append({

            "symbol":

            stock["symbol"],

            "allocation":

            allocation
        })

    return portfolio
