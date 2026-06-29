from app.ml.feature_builder import build_features


def predict_probability(model, stock):

    features = build_features(stock)

    probability = model.predict_proba(

        [features]

    )[0][1]

    return probability
