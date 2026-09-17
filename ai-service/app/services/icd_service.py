import logging
from sqlalchemy import select, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.icd10 import ICD10Code

logger = logging.getLogger(__name__)


async def search_icd10(
    db: AsyncSession,
    query: str,
    limit: int = 10,
    radiology_only: bool = False,
) -> list[dict]:
    """
    Search ICD-10 codes by description.
    Uses trigram similarity if pg_trgm is enabled, else ILIKE fallback.
    """
    q = select(ICD10Code)
    if radiology_only:
        q = q.where(ICD10Code.is_radiology_common == True)  # noqa

    try:
        # Try trigram similarity (pg_trgm extension)
        sim_q = (
            select(
                ICD10Code,
                func.similarity(ICD10Code.description, query).label("sim"),
            )
            .where(func.similarity(ICD10Code.description, query) > 0.1)
            .order_by(text("sim DESC"))
            .limit(limit)
        )
        if radiology_only:
            sim_q = sim_q.where(ICD10Code.is_radiology_common == True)  # noqa
        result = await db.execute(sim_q)
        rows = result.all()
        if rows:
            return [{"code": r.ICD10Code.code, "label": r.ICD10Code.description,
                     "category": r.ICD10Code.category, "score": float(r.sim)} for r in rows]
    except Exception:
        pass  # pg_trgm not available, fall back

    # ILIKE fallback
    term = f"%{query}%"
    result = await db.execute(
        q.where(
            or_(
                ICD10Code.description.ilike(term),
                ICD10Code.code.ilike(term),
            )
        ).limit(limit)
    )
    codes = result.scalars().all()
    return [{"code": c.code, "label": c.description, "category": c.category, "score": 1.0}
            for c in codes]


async def get_icd10(db: AsyncSession, code: str) -> dict | None:
    code = code.upper().strip()
    row = await db.get(ICD10Code, code)
    if not row:
        return None
    return {"code": row.code, "label": row.description, "category": row.category}


async def validate_and_enrich_codes(
    db: AsyncSession,
    codes: list[dict],
) -> list[dict]:
    """
    Validate GPT-4o suggested ICD codes against local DB.
    Replace unrecognized codes with closest match. Never trust raw GPT codes.
    """
    enriched = []
    for item in codes:
        code = item.get("code", "").upper().strip()
        db_row = await db.get(ICD10Code, code)
        if db_row:
            enriched.append({
                "code": db_row.code,
                "label": db_row.description,
                "confidence": item.get("confidence", 0.8),
                "verified": True,
            })
        else:
            # GPT hallucinated a code — search by label
            label = item.get("label", code)
            matches = await search_icd10(db, label, limit=1)
            if matches:
                enriched.append({
                    "code": matches[0]["code"],
                    "label": matches[0]["label"],
                    "confidence": item.get("confidence", 0.5) * 0.7,
                    "verified": False,
                    "original_code": code,
                })
    return enriched


async def get_all_icd_codes(
    db: AsyncSession,
    radiology_only: bool = True,
) -> list[dict]:

    q = select(ICD10Code)

    if radiology_only:
        q = q.where(ICD10Code.is_radiology_common == True)  # noqa

    result = await db.execute(q)

    rows = result.scalars().all()

    return [
        {
            "code": row.code,
            "description": row.description,
            "category": row.category,
        }
        for row in rows
    ]