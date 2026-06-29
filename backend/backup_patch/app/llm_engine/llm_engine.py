from app.llm_engine.annual_report_analyzer import analyze_annual_report

from app.llm_engine.concall_analyzer import compare_concalls

from app.llm_engine.governance_analyzer import analyze_governance

from app.llm_engine.management_sentiment import sentiment_score

from app.llm_engine.narrative_shift import compare_reports


async def llm_score(stock):

    text = stock.get("text", "")

    annual = await analyze_annual_report(text) if text else 0

    concall = await compare_concalls("", text) if text else 0

    governance = await analyze_governance(text) if text else 0

    sentiment = sentiment_score(text)

    narrative = await compare_reports("", text) if text else 0

    final = (

        annual * 0.25

        + concall * 0.30

        + governance * 0.20

        + sentiment * 0.15

        + narrative * 0.10

    )

    return final
