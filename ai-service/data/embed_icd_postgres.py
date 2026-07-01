import asyncio

from app.core.ai_database import AISessionLocal
from app.models.icd_embedding import ICDEmbedding

from app.services.nlp.icd_parser import parse_icd_xml
from app.services.nlp.bioclinicalbert import embed_text


ICD_XML = "/Users/karshin/Downloads/icd102019en.xml"


async def main():

    print("Loading ICD XML...")

    records = parse_icd_xml(ICD_XML)

    print(f"Loaded {len(records)} ICD codes")

    async with AISessionLocal() as db:

        for i, record in enumerate(records, start=1):

            vec = embed_text(
                record["description"]
            )

            db.add(
                ICDEmbedding(
                    code=record["code"],
                    description=record["description"],
                    embedding=list(vec),
                )
            )

            if i % 100 == 0:
                print(
                    f"Embedded {i}/{len(records)}"
                )

        await db.commit()

    print("Done")


if __name__ == "__main__":
    asyncio.run(main())