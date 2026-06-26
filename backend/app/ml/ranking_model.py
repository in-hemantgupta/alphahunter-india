def rank_stocks(model, stocks):

    from app.ml.feature_builder import build_features

    ranked = []

    for stock in stocks:

        features = build_features(stock)

        probability = model.predict_proba(

            [features]

        )[0][1]

        ranked.append({

            "symbol": stock["symbol"],

            "probability": probability

        })

    return sorted(

        ranked,

        key=lambda x: x["probability"],

        reverse=True

    )
