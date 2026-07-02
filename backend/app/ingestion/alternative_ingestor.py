from datetime import date
from sqlalchemy.orm import Session

from app.alternative_data.job_hiring_tracker import hiring_score
from app.alternative_data.news_velocity import news_score
from app.models.alternative_signals import AlternativeSignal
from app.models.stock import Stock
import asyncio
import httpx


async def _enrich_one_async(stock, today):
    ns = news_score(stock.company_name)
    return {
        "symbol": stock.symbol,
        "news_score": ns,
    }


async def enrich_hiring_async(session: Session, limit: int = 500) -> dict:
    """Enrich hiring scores asynchronously. Skips stocks with existing today's data."""
    today = date.today()
    existing_symbols = {
        r[0] for r in session.query(AlternativeSignal.symbol)
        .filter(AlternativeSignal.hiring_score.isnot(None), AlternativeSignal.date == today)
        .all()
    }
    stocks = session.query(Stock).filter(~Stock.symbol.in_(existing_symbols)).order_by(Stock.market_cap.desc().nullslast()).limit(limit).all()
    processed = 0
    skipped = 0
    failed = 0

    for idx, stock in enumerate(stocks):
        if not stock.company_name:
            failed += 1
            continue

        existing = session.query(AlternativeSignal).filter_by(
            symbol=stock.symbol, date=today
        ).first()

        if existing and existing.hiring_score is not None:
            skipped += 1
            continue

        hs = await hiring_score(stock.company_name)

        if existing:
            existing.hiring_score = hs
        else:
            record = AlternativeSignal(
                symbol=stock.symbol,
                date=today,
                hiring_score=hs,
            )
            session.add(record)

        if hs is not None:
            processed += 1
        else:
            failed += 1

        if (idx + 1) % 50 == 0:
            session.commit()
            if idx > 0 and (idx + 1) % 200 == 0:
                print(f"  Hiring enriched {idx+1}/{len(stocks)} stocks")

    session.commit()

    from app.alternative_data.job_hiring_tracker import close_client
    await close_client()

    return {
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "total": len(stocks),
    }


def enrich_news(session: Session, limit: int = 2395) -> dict:
    """Fast: update only news scores for stocks missing them. No rate limits."""
    today = date.today()
    existing_symbols = {
        r[0] for r in session.query(AlternativeSignal.symbol)
        .filter(AlternativeSignal.news_score.isnot(None), AlternativeSignal.date == today)
        .all()
    }
    stocks = session.query(Stock).filter(~Stock.symbol.in_(existing_symbols)).order_by(Stock.market_cap.desc().nullslast()).limit(limit).all()
    today = date.today()
    processed = 0
    skipped = 0
    failed = 0

    for idx, stock in enumerate(stocks):
        existing = session.query(AlternativeSignal).filter_by(
            symbol=stock.symbol, date=today
        ).first()

        if existing and existing.news_score is not None:
            skipped += 1
            continue

        if not stock.company_name:
            failed += 1
            continue

        ns = news_score(stock.company_name)

        if existing:
            existing.news_score = ns
        else:
            record = AlternativeSignal(
                symbol=stock.symbol,
                date=today,
                news_score=ns,
            )
            session.add(record)

        if ns is not None:
            processed += 1
        else:
            failed += 1

        if (idx + 1) % 50 == 0:
            session.commit()

    session.commit()

    return {
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "total": len(stocks),
    }


async def enrich_hiring_async(session: Session, limit: int = 500) -> dict:
    """Enrich hiring scores asynchronously. Skips stocks with existing today's data."""
    today = date.today()
    existing_symbols = {
        r[0] for r in session.query(AlternativeSignal.symbol)
        .filter(AlternativeSignal.hiring_score.isnot(None), AlternativeSignal.date == today)
        .all()
    }
    stocks = session.query(Stock).filter(~Stock.symbol.in_(existing_symbols)).order_by(Stock.market_cap.desc().nullslast()).limit(limit).all()
    processed = 0
    skipped = 0
    failed = 0

    for idx, stock in enumerate(stocks):
        if not stock.company_name:
            failed += 1
            continue

        existing = session.query(AlternativeSignal).filter_by(
            symbol=stock.symbol, date=today
        ).first()

        if existing and existing.hiring_score is not None:
            skipped += 1
            continue

        hs = await hiring_score(stock.company_name)

        if existing:
            existing.hiring_score = hs
        else:
            record = AlternativeSignal(
                symbol=stock.symbol,
                date=today,
                hiring_score=hs,
            )
            session.add(record)

        if hs is not None:
            processed += 1
        else:
            failed += 1

        if (idx + 1) % 50 == 0:
            session.commit()
            if idx > 0 and (idx + 1) % 200 == 0:
                print(f"  Hiring enriched {idx+1}/{len(stocks)} stocks")

    session.commit()

    return {
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "total": len(stocks),
    }
