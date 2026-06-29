from app.llm_engine.llm_router import LLMRouter

from app.llm_engine.prompt_library import SHIFT_PROMPT


llm = LLMRouter()


async def compare_reports(

    old_report,

    new_report
):

    prompt = \

        SHIFT_PROMPT + \

        old_report + \

        new_report

    return await \

        llm.query(prompt)
