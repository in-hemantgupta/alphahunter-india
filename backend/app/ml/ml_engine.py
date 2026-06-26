from app.ml.prediction_engine import predict_probability


def ml_predict(model, stock):

    probability = predict_probability(

        model,

        stock

    )

    return probability
