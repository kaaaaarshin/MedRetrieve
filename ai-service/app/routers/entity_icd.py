from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_database import get_ai_db

from app.schemas.entity import (
    EntityRequest,
    EntityResponse,
    ICDMatch,
)

from app.services.nlp.entity_extractor import extract_entities
from app.services.nlp.icd_retriever import retrieve_icd


router = APIRouter(
    prefix="/entity-icd",
    tags=["Entity ICD"],
)


@router.post("/", response_model=EntityResponse)
async def entity_icd(
    data: EntityRequest,
    db: AsyncSession = Depends(get_ai_db),
):
    entities = extract_entities(
        data.transcript
    )

    matches = []

    for entity in entities:

        results = await retrieve_icd(
            db=db,
            entity=entity,
        )

        matches.extend(results)

    return EntityResponse(
        entities=entities,
        matches=[
            ICDMatch(**m)
            for m in matches
        ],
    )