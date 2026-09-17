# test_db_icd.py

import asyncio
from sqlalchemy import text

from app.core.ai_database import AISessionLocal


async def main():

    async with AISessionLocal() as db:

        result = await db.execute(
            text("""
                SELECT code, description
                FROM icd_embeddings
                LIMIT 5
            """)
        )

        for row in result:
            print(row)

asyncio.run(main())