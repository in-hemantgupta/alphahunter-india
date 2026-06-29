from app.agents.market_observer import observe_market

from app.agents.agent_router import route_agent


async def run():

    anomalies = observe_market()

    validation = await route_agent(anomalies)

    return validation
