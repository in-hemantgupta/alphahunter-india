import numpy as np


def annual_volatility(

    returns
):

    return np.std(

        returns

    ) * np.sqrt(252)
