import numpy as np

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.nlp.bioclinicalbert import embed_text


async def search_icd_by_embedding(
    db: AsyncSession,
    query: str,
    top_k: int = 3,
):
    vec = embed_text(query)

    sql = text("""
        SELECT
            code,
            description,
            embedding <=> CAST(:embedding AS vector) AS distance
        FROM icd_embeddings
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
    """)

    result = await db.execute(
        sql,
        {
            "embedding": str(vec),
            "top_k": top_k,
        },
    )

    rows = result.fetchall()

    return [
        {
            "code": row.code,
            "description": row.description,
            "score": float(1 - row.distance),
        }
        for row in rows
    ]