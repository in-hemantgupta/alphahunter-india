from app.llm_engine.llm_router import LLMRouter
from app.llm_engine.prompt_library import RISK_PROMPT

llm = LLMRouter()

async def detect_risks(text):
    prompt = RISK_PROMPT + text
    return await llm.query(prompt)
