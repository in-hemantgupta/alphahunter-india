import numpy as np


def annual_volatility(

    returns
):

    return np.std(

        returns

    ) if len(

        returns

    ) > 1 else 0 * np.sqrt(252)
