from app.alternative_data.job_hiring_tracker import hiring_score
from app.alternative_data.government_contracts import contract_score
from app.alternative_data.patent_tracker import patent_score
from app.alternative_data.news_velocity import news_score
from app.alternative_data.import_export_tracker import shipment_score


def alternative_score(stock):
    final = (
        hiring_score(stock) * 0.20
        + contract_score(stock) * 0.20
        + patent_score(stock) * 0.10
        + news_score(stock) * 0.10
        + shipment_score(stock) * 0.15
        + stock.get("sector_rotation_score", 50) * 0.15
        + stock.get("search_trend_score", 50) * 0.10
    )
    return final
