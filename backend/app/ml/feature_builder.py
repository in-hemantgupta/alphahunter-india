FEATURES = [

    "revenue_growth",

    "pat_growth",

    "ebitda_growth",

    "roce",

    "roe",

    "debt_equity",

    "microstructure_score",

    "delivery_percent",

    "alternative_score",

    "llm_score",

    "sector_strength",

    "promoter_change",

    "fii_change",

    "volume_ratio"
]


def build_features(stock):

    return [

        stock[x]

        for x in FEATURES

    ]
