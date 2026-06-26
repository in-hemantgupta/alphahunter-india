import pandas as pd
def walk_forward_test(data, train_window, test_window):

    results = []

    for i in range(0, len(data) - train_window - test_window, test_window):

        train = data[i:i + train_window]

        test = data[i + train_window:i + train_window + test_window]

        model = train_on(train)

        result = test_model(model, test)

        results.append(result)

    return results
