def rank_stocks(records):

    sorted_stocks = sorted(

        records,

        key=lambda x:

        x["total_score"],

        reverse=True
    )

    return sorted_stocks[:50]
