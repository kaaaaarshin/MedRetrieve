from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.drug_service import search_drugs, get_drugs_by_indication

router = APIRouter(prefix="/drugs", tags=["Drug DB"])


@router.get("/search")
async def search(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    return await search_drugs(db, q, limit=limit)


@router.get("/by-indication")
async def by_indication(
    indication: str = Query(..., min_length=3),
    limit: int = Query(5, le=20),
    db: AsyncSession = Depends(get_db),
):
    return await get_drugs_by_indication(db, indication, limit=limit)
