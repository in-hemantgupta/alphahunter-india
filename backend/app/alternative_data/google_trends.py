from pytrends.request import TrendReq

pytrends = TrendReq()


def trend_score(keyword):

    pytrends.build_payload(

        [keyword]
    )

    data = pytrends.interest_over_time()

    recent = data.iloc[-30:].mean()[0]

    older = data.iloc[-90:-30].mean()[0]

    growth = (

        recent - older

    ) / older

    if growth > 0.25:

        return 100

    return 40
