def breakout_score(

    current_price,

    high_52w

):

    score = 0

    ratio = (

        current_price

        /

        high_52w
    )

    if ratio > 0.95:

        score = 5

    elif ratio > 0.90:

        score = 3

    return score
