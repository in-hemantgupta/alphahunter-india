import json
import asyncio
from datetime import date
from sqlalchemy.orm import Session

from app.llm_engine.groq_client import query_groq, GroqError
import asyncio
from app.models.llm_analysis import LLMAnalysis
from app.models.stock import Stock
from app.services.pipeline import get_stock_data_for_scoring


BATCH_PROMPT_TEMPLATE = """You are an expert financial analyst. Analyze the following Indian stocks and rate each on 6 dimensions from 0-100.

For each stock, consider:
- **management_confidence**: How confident is management? (capital allocation quality, return on capital, debt management)
- **narrative_consistency**: Are the financial trends consistent and improving? (revenue/profit acceleration, margin stability)
- **sentiment**: Overall market and business sentiment (returns, volume trends, promoter actions)
- **governance_quality**: Corporate governance strength (promoter holding, pledge %, debt levels)
- **hidden_risks**: Unseen risks based on financial patterns (high leverage, declining margins, cashflow issues)
- **annual_report_quality**: Overall corporate quality and transparency (composite of fundamentals)

Return ONLY valid JSON array (no markdown, no explanation):
[
  {{
    "symbol": "RELIANCE",
    "management_confidence": 85,
    "narrative_consistency": 75,
    "sentiment": 80,
    "governance_quality": 90,
    "hidden_risks": 20,
    "annual_report_quality": 85
  }},
  ...
]

Stocks to analyze:
{stock_data}
"""


def _build_batch_prompt(stocks_batch: list[dict]) -> str:
    lines = []
    for s in stocks_batch:
        lines.append(
            f"Symbol: {s['symbol']} | Name: {s['company_name'][:40]} | "
            f"ROCE:{s.get('roce',0):.1f}% D/E:{s.get('debt_equity',0):.2f} "
            f"RevAcc:{s.get('revenue_acceleration',0):.1f}% "
            f"PatAcc:{s.get('pat_acceleration',0):.1f}% "
            f"MarginExp:{s.get('margin_expansion',0):.1f}% "
            f"PromoterΔ:{s.get('promoter_change',0):+.1f}% "
            f"Pledge:{s.get('pledge_percent',0):.1f}% "
            f"1yReturn:{s.get('returns_1y',0):.1f}% "
            f"6mReturn:{s.get('returns_6m',0):.1f}% "
            f"VolumeRatio:{s.get('volume_ratio',0):.2f}"
        )
    return BATCH_PROMPT_TEMPLATE.format(stock_data="\n".join(lines))


def _parse_llm_response(response_text: str) -> list[dict]:
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
        cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                return []
    return []


async def enrich_llm_batch(
    session: Session, stocks_data: list[dict], batch_size: int = 8
) -> dict:
    """Run LLM analysis on stocks in batches. Groups stocks and calls Groq API.
    Respects Groq free tier rate limits: ~2s between calls."""
    today = date.today()
    total = len(stocks_data)
    processed = 0
    failed = 0
    skipped = 0

    for i in range(0, total, batch_size):
        batch_dict = stocks_data[i : i + batch_size]

        symbols_in_batch = [s["symbol"] for s in batch_dict]

        existing = {
            r[0]
            for r in session.query(LLMAnalysis.symbol)
            .filter(
                LLMAnalysis.symbol.in_(symbols_in_batch),
                LLMAnalysis.date == today,
            )
            .all()
        }
        batch_needed = [s for s in batch_dict if s["symbol"] not in existing]
        skipped += len(batch_dict) - len(batch_needed)

        if not batch_needed:
            continue

        prompt = _build_batch_prompt(batch_needed)
        try:
            response = await query_groq(prompt)
        except GroqError as e:
            print(f"Groq API error for {symbols_in_batch}: {e}")
            failed += len(batch_needed)
            await asyncio.sleep(5)
            continue
        except Exception as e:
            print(f"LLM batch failed for {symbols_in_batch}: {e}")
            failed += len(batch_needed)
            continue

        results = _parse_llm_response(response)

        for r in results:
            symbol = r.get("symbol", "")
            if not symbol:
                continue
            record = LLMAnalysis(
                symbol=symbol,
                date=today,
                annual_score=r.get("annual_report_quality"),
                concall_score=r.get("narrative_consistency"),
                governance_score=r.get("governance_quality"),
                narrative_score=r.get("narrative_consistency"),
                risk_score=r.get("hidden_risks"),
                sentiment_score=r.get("sentiment"),
                management_confidence=r.get("management_confidence"),
                final_score=None,
            )
            session.merge(record)
            processed += 1

        session.commit()

        if (i // batch_size + 1) % 5 == 0:
            print(f"  LLM enriched {min(i + batch_size, total)}/{total} stocks")

        await asyncio.sleep(2.5)

    return {
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "total": total,
    }


async def run_llm_enrichment(session: Session, limit: int | None = None, symbols: list[str] | None = None) -> dict:
    """Fetch stocks (by limit or specific symbols), build scoring data, and run LLM enrichment."""
    if symbols:
        stocks = session.query(Stock).filter(Stock.symbol.in_(symbols)).all()
    elif limit:
        stocks = session.query(Stock).order_by(Stock.market_cap.desc().nullslast()).limit(limit).all()
    else:
        stocks = session.query(Stock).all()

    stocks_data = []
    for stock in stocks:
        data = get_stock_data_for_scoring(stock.symbol, session)
        if data:
            stocks_data.append(data)

    if not stocks_data:
        return {"error": "No stock data available", "total": 0}

    result = await enrich_llm_batch(session, stocks_data)
    return result
