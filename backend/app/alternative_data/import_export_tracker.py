def shipment_score(data):
    if (data.get("shipment_growth") or 0) > 20:
        return 100
    return 50
