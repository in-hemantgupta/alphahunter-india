from app.microstructure.delivery_analysis import delivery_score

from app.microstructure.vwap_accumulation import vwap_score

from app.microstructure.float_absorption import float_score

from app.microstructure.volume_anomaly import volume_score

from app.microstructure.price_tightness import tightness_score


def microstructure_score(stock):

    final = (

        delivery_score(stock) * 0.30

        + vwap_score(stock) * 0.20

        + float_score(stock) * 0.25

        + volume_score(stock) * 0.15

        + tightness_score(stock) * 0.10

    )

    return final
