import asyncio

from app.core.ai_database import AISessionLocal
from app.services.nlp.icd_retriever import retrieve_icd


QUERIES = [
    "pulmonary fibrosis",
    "pleural effusion",
    "pneumothorax",
    "pneumonia",
    "cardiomegaly with bilateral pleural effusion and pulmonary edema",
]


async def main():
    async with AISessionLocal() as db:

        for query in QUERIES:

            print(f"\n{'='*60}")
            print(query.upper())
            print('='*60)

            results = await retrieve_icd(
                db,
                query,
                top_k=5,
            )

            for r in results:
                print(
                    f"{r['code']} | "
                    f"{r['description']} | "
                    f"{r['score']:.4f}"
                )


if __name__ == "__main__":
    asyncio.run(main())