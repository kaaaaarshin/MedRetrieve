import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.ai_database import get_ai_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats")
async def stats(ai_db: AsyncSession = Depends(get_ai_db)):
    """Learning loop stats — how much data the system has learned from."""
    r1 = await ai_db.execute(text("SELECT COUNT(*) FROM ai_verified_reports"))
    r2 = await ai_db.execute(text("SELECT COUNT(*) FROM ai_verified_reports WHERE embedding IS NOT NULL"))
    r3 = await ai_db.execute(text("SELECT COUNT(*) FROM ai_suggestion_feedback"))
    r4 = await ai_db.execute(text(
        "SELECT modality, COUNT(*) as cnt FROM ai_verified_reports GROUP BY modality ORDER BY cnt DESC"
    ))
    r5 = await ai_db.execute(text(
        "SELECT impression_action, COUNT(*) as cnt FROM ai_suggestion_feedback "
        "WHERE impression_action IS NOT NULL GROUP BY impression_action"
    ))

    return {
        "verified_reports": {
            "total": r1.scalar(),
            "with_embeddings": r2.scalar(),
        },
        "suggestion_feedback": {
            "total": r3.scalar(),
            "by_action": {row.impression_action: row.cnt for row in r5.fetchall()},
        },
        "reports_by_modality": {row.modality: row.cnt for row in r4.fetchall()},
    }
