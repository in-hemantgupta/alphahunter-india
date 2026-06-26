def validate(research_results):

    confidence = 0

    if research_results["llm"] > 70:

        confidence += 30

    if research_results["alternative"] > 60:

        confidence += 25

    if research_results["microstructure"] > 75:

        confidence += 27

    return confidence
