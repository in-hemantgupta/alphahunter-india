from app.llm_engine.llm_router import LLMRouter

llm = LLMRouter()


async def generate_hypothesis(anomalies):

    prompt = f"""

    Given market anomalies: {anomalies}

    Generate possible investment hypotheses.

    """

    response = await llm.query(prompt)

    return response
