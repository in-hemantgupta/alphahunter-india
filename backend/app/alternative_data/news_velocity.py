def news_score(data):
    if (data.get("news_mentions_growth") or 0) > 40:
        return 100
    return 30
