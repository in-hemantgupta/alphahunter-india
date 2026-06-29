def patent_score(data):
    if (data.get("new_patents") or 0) > 3:
        return 100
    return 30
