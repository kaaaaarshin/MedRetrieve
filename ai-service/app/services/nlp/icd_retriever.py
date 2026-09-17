import numpy as np

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.icd_embedding import ICDEmbedding
from app.services.nlp.bioclinicalbert import embed_text

STOPWORDS = {
    "with",
    "without",
    "and",
    "the",
    "is",
    "are",
    "was",
    "were",
    "noted",
    "identified",
    "present",
    "evidence",
    "moderate",
    "mild",
    "severe",
    "small",
    "large",
    "left",
    "right",
    "bilateral",
    "adjacent",
    "changes",
    "focal",
    "normal",
    "limits",
    "no",
    "there",
    "shows",
    "showing",
    "demonstrates",
    "demonstrated",
    "findings",
    "consistent",
    "suggestive",
    "likely",
    "within",
    "not"
}


def cosine_similarity(a, b):
    return np.dot(a, b) / (
        np.linalg.norm(a) * np.linalg.norm(b)
    )


async def retrieve_icd(
    db: AsyncSession,
    query: str,
    top_k: int = 10,
):

    query_vec = np.array(
        embed_text(query),
        dtype=np.float32,
    )

    result = await db.execute(
        select(
            ICDEmbedding.code,
            ICDEmbedding.description,
            ICDEmbedding.embedding,
        )
    )

    rows = result.all()

    scored = []

    query_lower = query.lower()

    for code, description, embedding in rows:

        desc_lower = description.lower()

        cosine_score = cosine_similarity(
            query_vec,
            np.array(
                embedding,
                dtype=np.float32,
            ),
        )

        score = cosine_score

        considerations = []

        # Exact phrase match
        if query_lower in desc_lower:
            score += 0.25

            considerations.append(
                "Exact phrase match found (+0.25)"
            )

        # Matched terms (for explainability only)
        matched_terms = []

        for word in query_lower.split():

            word = word.strip(".,;:()[]{}")

            if word in STOPWORDS:
                continue

            if len(word) < 4:
                continue

            if word in desc_lower:
                matched_terms.append(word)

        if matched_terms:
            considerations.append(
                f"Matched keywords: {', '.join(matched_terms)}"
            )

        considerations.append(
            "Semantic similarity match"
        )

        considerations.append(
            f"Confidence score: {cosine_score:.4f}"
        )

        if score >= 0.85:
            scored.append(
            {
                "entity": query,
                "code": code,
                "description": description,
                "score": float(score),
                "considerations": considerations,
                "retrieval_method": "semantic_similarity",
            }
            )
    scored.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return scored[:top_k]