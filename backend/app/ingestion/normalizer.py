STANDARD_SCHEMA = {
    "sales": "revenue",
    "turnover": "revenue",
    "net_profit": "pat"
}

def normalize_data(data, source):
    normalized = {}
    for key, value in data.items():
        standard_key = STANDARD_SCHEMA.get(key, key)
        normalized[standard_key] = value
    return normalized
