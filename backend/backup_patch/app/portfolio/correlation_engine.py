import pandas as pd


def correlation_matrix(

    price_data
):

    returns = \

        price_data.pct_change()

    return returns.corr()
