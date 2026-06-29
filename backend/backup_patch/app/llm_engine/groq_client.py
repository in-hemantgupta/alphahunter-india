import httpx

from app.core.config import settings


async def query_groq(prompt):

    async with httpx.AsyncClient() as client:

        response = await client.post(

            "https://api.groq.com/openai/v1/chat/completions",

            headers={

                "Authorization": f"Bearer {settings.GROQ_API_KEY}",

                "Content-Type": "application/json"

            },

            json={

                "model": "llama-3.3-70b-versatile",

                "messages": [{"role": "user", "content": prompt}]

            },

            timeout=60

        )

        return response.json()["choices"][0]["message"]["content"]
