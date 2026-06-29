from lightgbm import LGBMClassifier


def train_lightgbm(X_train, y_train):

    model = LGBMClassifier(

        n_estimators=500,

        max_depth=6

    )

    model.fit(X_train, y_train)

    return model
