def contract_score(data):
    if data["new_order_value"] > data["annual_revenue"] * 0.15:
        return 100
    return 40
