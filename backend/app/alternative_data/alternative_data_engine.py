from app.alternative_data.job_hiring_tracker import hiring_score

from app.alternative_data.government_contracts import contract_score

from app.alternative_data.patent_tracker import patent_score

from app.alternative_data.news_velocity import news_score

from app.alternative_data.google_trends import trend_score


def alternative_score(stock):

    final = (

        hiring_score(stock) * 0.30

        + contract_score(stock) * 0.30

        + patent_score(stock) * 0.10

        + news_score(stock) * 0.20

        + trend_score(stock) * 0.10

    )

    return final
