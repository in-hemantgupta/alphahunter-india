import pandas as pd
from app.ml.feature_builder import build_features

from app.ml.label_engine import create_label


def build_dataset(stocks, benchmark_returns):

    X = []

    y = []

    for stock in stocks:

        features = build_features(stock)

        label = create_label(

            stock["future_return"],

            benchmark_returns[stock["symbol"]]

        )

        X.append(features)

        y.append(label)

    return X, y
