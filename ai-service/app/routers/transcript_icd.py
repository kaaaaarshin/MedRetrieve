from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.nlp.icd_retriever import retrieve_icd
from app.core.ai_database import get_ai_db

from app.schemas.entity import (
    EntityRequest,
    EntityResponse,
    ICDMatch,
)

from app.services.nlp.gliner_service import (
    extract_entities as gliner_extract,
)

from app.services.nlp.entity_extractor import (
    extract_entities as regex_extract,
    FINDING_TO_QUERY,
)

router = APIRouter(
    prefix="/transcript-icd",
    tags=["Transcript ICD"],
)


@router.post("/", response_model=EntityResponse)
async def transcript_icd(
    data: EntityRequest,
    ai_db: AsyncSession = Depends(get_ai_db),
):

    # AI extraction
    gliner_entities = gliner_extract(
        data.transcript
    )
    # AI extraction
    regex_entities = regex_extract(
        data.transcript
    )
    #Merge
    entities = list(
    dict.fromkeys(
        gliner_entities + regex_entities
        )
    )

    
    

    normalized = []

    for entity in entities:

        entity = entity.lower()

        if "pleural effusion" in entity:
            normalized.append("pleural effusion")

        elif "atelect" in entity:
            normalized.append("atelectasis")

        elif "pneumothorax" in entity:
            normalized.append("pneumothorax")

        elif "ground glass" in entity:
            normalized.append("ground glass opacity")

        elif "fibrotic" in entity or "fibrosis" in entity:
            normalized.append("pulmonary fibrosis")

        elif "consolidation" in entity:
            normalized.append("pneumonia")

        elif "cardiomegaly" in entity:
            normalized.append("cardiomegaly")

        elif "pulmonary edema" in entity:
            normalized.append("pulmonary edema")

        elif "mediastinal shift" in entity:
            normalized.append("mediastinal shift")
        
        else:
            normalized.append(entity)

    entities = list(
    dict.fromkeys(
        normalized
        )
    )

    print("=" * 60)
    print(f"GLiNER ({len(gliner_entities)}): {gliner_entities}")
    print(f"Regex  ({len(regex_entities)}): {regex_entities}")
    print(f"Final  ({len(entities)}): {entities}")
    print("=" * 60)

    matches = []

    for entity in entities: 

        query = FINDING_TO_QUERY.get(
            entity,
            entity,
        )

        entity_matches = await retrieve_icd(
            ai_db,
            query,
            top_k=1,
        )

        for match in entity_matches:
            match["entity"] = entity

        matches.extend(entity_matches)

    # Remove duplicate ICD codes
    seen = set()
    unique_matches = []

    for match in matches:

        code = match["code"]

        if code not in seen:
            seen.add(code)
            unique_matches.append(match)

    return EntityResponse(
        entity_count=len(entities),
        entities=entities,
        matches=[
            ICDMatch(**m)
            for m in unique_matches
        ],
    )

