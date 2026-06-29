from app.llm_engine.llm_router import LLMRouter

from app.llm_engine.prompt_library import GOVERNANCE_PROMPT


llm = LLMRouter()


async def analyze_governance(

    text
):

    prompt = \

        GOVERNANCE_PROMPT + text

    return await \

        llm.query(

            prompt
        )
