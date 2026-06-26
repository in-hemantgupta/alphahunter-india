async def run_research(hypothesis):

    from app.llm_engine.llm_engine import llm_score

    from app.alternative_data.alternative_data_engine import alternative_score

    from app.microstructure.microstructure_engine import microstructure_score

    results = {

        "llm": await llm_score(hypothesis),

        "alternative": alternative_score(hypothesis),

        "microstructure": microstructure_score(hypothesis)

    }

    return results
