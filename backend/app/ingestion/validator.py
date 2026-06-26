def validate_financials(

    data
):

    if data["ebitda"] > \

        data["revenue"]:

        return False

    if data["roe"] > 200:

        return False

    return True
