from qdrant_client import QdrantClient


client = QdrantClient(host="localhost", port=6333)


def store_memory(embedding, metadata):

    client.upsert(

        collection_name="agent_memory",

        points=[{

            "vector": embedding,

            "payload": metadata

        }]

    )


def recall_memory(query_embedding):

    results = client.search(

        collection_name="agent_memory",

        query_vector=query_embedding,

        limit=5

    )

    return results
