def news_score(data):
    if data["news_mentions_growth"] > 40:
        return 100
    return 30
