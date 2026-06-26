def adjust_weights(error):

    return error


def learn(prediction, outcome):

    error = prediction - outcome

    adjust_weights(error)
