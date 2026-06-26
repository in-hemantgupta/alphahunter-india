def volume_accumulation_score(

    volume_20d,

    volume_90d

):

    score = 0

    ratio = (

        volume_20d

        /

        volume_90d
    )

    if ratio > 2:

        score = 7

    elif ratio > 1.5:

        score = 5

    elif ratio > 1.2:

        score = 3

    return score
