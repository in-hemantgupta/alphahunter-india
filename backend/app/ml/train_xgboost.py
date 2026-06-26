from xgboost import XGBClassifier


def train_xgboost(X_train, y_train):

    model = XGBClassifier(

        n_estimators=500,

        max_depth=6

    )

    model.fit(X_train, y_train)

    return model
