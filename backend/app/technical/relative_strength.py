def relative_strength_score(

    stock_return,
    benchmark_return

):

    score = 0

    excess = (

        stock_return

        -

        benchmark_return
    )

    if excess > 20:

        score = 8

    elif excess > 10:

        score = 5

    elif excess > 5:

        score = 3

    return score
