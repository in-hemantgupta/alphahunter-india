def contract_score(data):
    if (data.get("new_order_value") or 0) > (data.get("annual_revenue") or 1) * 0.15:
        return 100
    return 40
