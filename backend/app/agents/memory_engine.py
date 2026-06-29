import pandas as pd
from app.core.config import settings


try:

    from qdrant_client import QdrantClient

    client = QdrantClient(

        host=settings.QDRANT_HOST,

        port=settings.QDRANT_PORT

    )

    QDRANT_AVAILABLE = True

except Exception:

    client = None

    QDRANT_AVAILABLE = False


def store_memory(embedding, metadata):

    if not QDRANT_AVAILABLE:

        return

    try:

        client.upsert(

            collection_name="agent_memory",

            points=[{

                "vector": embedding,

                "payload": metadata

            }]

        )

    except Exception:

        pass


def recall_memory(query_embedding):

    if not QDRANT_AVAILABLE:

        return []

    try:

        results = client.search(

            collection_name="agent_memory",

            query_vector=query_embedding,

            limit=5

        )

        return results

    except Exception:

        return []
