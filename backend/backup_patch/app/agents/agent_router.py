from app.agents.market_observer import observe_market

from app.agents.hypothesis_generator import generate_hypothesis

from app.agents.research_agent import run_research

from app.agents.validation_agent import validate

from app.agents.portfolio_agent import portfolio_action

from app.agents.learning_agent import learn


async def route_agent(anomalies):

    hypothesis = await generate_hypothesis(anomalies)

    research = await run_research(hypothesis)

    validation = validate(research)

    if validation > 80:

        portfolio_action(validation)

    learn(validation, None)

    return validation
