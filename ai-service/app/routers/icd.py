from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.ai import ICD10SearchResponse
from app.services.icd_service import search_icd10, get_icd10

router = APIRouter(prefix="/icd", tags=["ICD-10"])


@router.get("/search", response_model=list[ICD10SearchResponse])
async def search(
    q: str = Query(..., min_length=2),
    radiology_only: bool = Query(False),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    results = await search_icd10(db, q, limit=limit, radiology_only=radiology_only)
    return [ICD10SearchResponse(**r) for r in results]


@router.get("/{code}", response_model=ICD10SearchResponse)
async def get_code(code: str, db: AsyncSession = Depends(get_db)):
    result = await get_icd10(db, code)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"ICD-10 code {code} not found")
    return ICD10SearchResponse(**result, score=1.0)
