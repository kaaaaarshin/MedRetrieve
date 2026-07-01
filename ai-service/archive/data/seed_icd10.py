import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.ai_database import AISessionLocal

from app.models.icd10 import ICD10Code
from app.models.icd_embedding import ICDEmbedding

from app.services.nlp.bioclinicalbert import embed_text


async def main():

    async with AsyncSessionLocal() as ris_db:

        result = await ris_db.execute(
            select(ICD10Code)
        )

        icd_rows = result.scalars().all()

    async with AISessionLocal() as ai_db:

        for row in icd_rows:

            existing = await ai_db.get(
                ICDEmbedding,
                row.code
            )

            if existing:
                continue

            vec = embed_text(
                row.description
            )

            ai_db.add(
                ICDEmbedding(
                    code=row.code,
                    description=row.description,
                    embedding=vec,
                )
            )

            print(
                f"embedded {row.code}"
            )

        await ai_db.commit()


if __name__ == "__main__":
    asyncio.run(main())