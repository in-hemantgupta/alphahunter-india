from app.llm_engine.llm_router import LLMRouter
from app.llm_engine.prompt_library import COMPARE_PROMPT

llm = LLMRouter()

async def compare_concalls(old, new):
    prompt = COMPARE_PROMPT + old + new
    return await llm.query(prompt)
