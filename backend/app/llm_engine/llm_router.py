from app.llm_engine.groq_client import query_groq

from app.llm_engine.cloudflare_client import query_cloudflare


class LLMRouter:

    async def query(

        self,

        prompt

    ):

        try:

            return await \

                query_groq(

                    prompt

                )

        except:

            return await \

                query_cloudflare(

                    prompt

                )
