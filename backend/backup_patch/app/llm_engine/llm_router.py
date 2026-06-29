from app.core.config import settings


class LLMRouter:

    async def query(

        self,

        prompt

    ):

        if not settings.GROQ_API_KEY and not settings.CLOUDFLARE_API_KEY:

            return "LLM not configured"

        try:

            from app.llm_engine.groq_client import query_groq

            return await query_groq(prompt)

        except Exception as e:

            print(f"Groq failed: {e}")

            try:

                from app.llm_engine.cloudflare_client import query_cloudflare

                return await query_cloudflare(prompt)

            except Exception as e2:

                print(f"Cloudflare failed: {e2}")

                return "LLM unavailable"
