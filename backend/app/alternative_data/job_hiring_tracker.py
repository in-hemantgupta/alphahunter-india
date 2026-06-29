def hiring_score(data):
    if (data.get("job_postings_growth") or 0) > 30:
        return 100
    return 40
