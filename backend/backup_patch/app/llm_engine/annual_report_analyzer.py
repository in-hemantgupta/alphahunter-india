from app.llm_engine.llm_router import LLMRouter

from app.llm_engine.prompt_library import REPORT_PROMPT


llm = LLMRouter()


async def analyze_annual_report(

    text
):

    prompt = \

        REPORT_PROMPT + text

    response = await \

        llm.query(

            prompt
        )

    return response
