from app.ml.feature_builder import FEATURES


def get_feature_importance(model):

    importances = model.feature_importances_

    return dict(zip(

        FEATURES,

        importances

    ))
