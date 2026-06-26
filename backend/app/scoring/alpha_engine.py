from app.scoring.fundamental_score import fundamental_score

from app.scoring.growth_score import growth_score

from app.scoring.management_score import management_score

from app.scoring.institutional_score import institutional_score

from app.scoring.technical_score import technical_score

from app.scoring.penalty_engine import penalty_engine


def alpha_score(stock):

    fundamental = fundamental_score(stock)

    growth = growth_score(stock)

    management = management_score(stock)

    institutional = institutional_score(stock)

    technical = technical_score(stock)

    alternative = stock.get("alternative_score", 0)

    llm = stock.get("llm_score", 0)

    penalty = penalty_engine(stock)

    final = (

        fundamental * 0.18

        + growth * 0.20

        + management * 0.18

        + institutional * 0.14

        + alternative * 0.10

        + technical * 0.08

        + llm * 0.12

        - penalty

    )

    return max(0, min(100, final))
