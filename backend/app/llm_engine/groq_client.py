import httpx

from app.core.config import settings


class GroqError(Exception):
    pass


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

        data = response.json()

        if "error" in data:
            raise GroqError(data["error"].get("message", str(data["error"])))

        if "choices" not in data or not data["choices"]:
            raise GroqError(f"Unexpected response: {data}")

        return data["choices"][0]["message"]["content"]
