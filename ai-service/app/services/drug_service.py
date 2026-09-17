from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drug import Drug


async def search_drugs(db: AsyncSession, query: str, limit: int = 10) -> list[dict]:
    term = f"%{query}%"
    result = await db.execute(
        select(Drug).where(
            or_(
                Drug.generic_name.ilike(term),
                Drug.brand_names.ilike(term),
                Drug.indication.ilike(term),
                Drug.drug_class.ilike(term),
            )
        ).limit(limit)
    )
    drugs = result.scalars().all()
    return [_to_dict(d) for d in drugs]


async def get_drugs_by_indication(db: AsyncSession, indication: str, limit: int = 5) -> list[dict]:
    term = f"%{indication}%"
    result = await db.execute(
        select(Drug)
        .where(Drug.indication.ilike(term))
        .where(Drug.in_india_formulary == True)  # noqa
        .limit(limit)
    )
    return [_to_dict(d) for d in result.scalars().all()]


def _to_dict(d: Drug) -> dict:
    return {
        "id": d.id,
        "generic_name": d.generic_name,
        "brand_names": d.brand_names,
        "drug_class": d.drug_class,
        "indication": d.indication,
        "standard_dose": d.standard_dose,
        "route": d.route,
        "contraindications": d.contraindications,
        "schedule": d.schedule,
        "note": "FOR REFERRING PHYSICIAN — not a radiologist prescription",
    }
