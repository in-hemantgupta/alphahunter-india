def block_score(data):
    if data["recent_bulk_buy"]:
        return 100
    return 20
