POSITIVE_TERMS = [
    "expansion",
    "strong demand",
    "capacity increase",
    "new contracts",
    "margin improvement"
]

def sentiment_score(text):
    score = 0
    for word in POSITIVE_TERMS:
        if word in text:
            score += 20
    return score
