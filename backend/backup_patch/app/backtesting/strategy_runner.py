import pandas as pd
from app.scoring.alpha_engine import alpha_score


def run_strategy(snapshot):

    ranked = []

    for stock in snapshot:

        score = alpha_score(stock)

        ranked.append({

            "symbol": stock["symbol"],

            "score": score

        })

    return ranked[:15]
