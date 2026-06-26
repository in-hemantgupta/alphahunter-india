import pandas as pd


def build_stock_universe():

    nse = pd.read_csv(

        "nse_equity.csv"
    )

    bse = pd.read_csv(

        "bse_equity.csv"
    )

    combined = pd.concat(

        [nse, bse]
    )

    combined = \

        combined.drop_duplicates(

            subset=["symbol"]
        )

    return combined
