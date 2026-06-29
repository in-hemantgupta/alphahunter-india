import httpx

from app.core.config import settings


async def query_cloudflare(prompt):

    async with httpx.AsyncClient() as client:

        response = await client.post(

            settings.CLOUDFLARE_API_KEY,

            json={"prompt": prompt},

            timeout=60

        )

        return response.json()
