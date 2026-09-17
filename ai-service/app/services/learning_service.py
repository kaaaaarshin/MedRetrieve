import logging
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import VerifiedReport
from app.services.embedding_service import embed

logger = logging.getLogger(__name__)


async def get_few_shot_examples(
    db: AsyncSession,
    transcript: str,
    modality: str,
    radiologist_id: str | None = None,
    top_k: int = 3,
) -> list[dict]:
    """
    Retrieve the most similar verified reports to use as few-shot examples.
    Prefers same radiologist's reports — personalises suggestions to their style.
    Falls back to all radiologists if not enough personal examples.
    """
    vec = await embed(transcript)
    if vec is None:
        return []

    # Try same radiologist first
    if radiologist_id:
        q = (
            select(VerifiedReport, VerifiedReport.embedding.cosine_distance(vec).label("distance"))
            .where(and_(
                VerifiedReport.modality == modality,
                VerifiedReport.radiologist_id == radiologist_id,
                VerifiedReport.embedding.isnot(None),
            ))
            .order_by("distance")
            .limit(top_k)
        )
        result = await db.execute(q)
        rows = result.all()
        if rows:
            return _format(rows)

    # Fall back to all radiologists for this modality
    q = (
        select(VerifiedReport, VerifiedReport.embedding.cosine_distance(vec).label("distance"))
        .where(and_(
            VerifiedReport.modality == modality,
            VerifiedReport.embedding.isnot(None),
        ))
        .order_by("distance")
        .limit(top_k)
    )
    result = await db.execute(q)
    return _format(result.all())


def _format(rows) -> list[dict]:
    return [
        {
            "modality": r.VerifiedReport.modality,
            "body_part": r.VerifiedReport.body_part,
            "clinical_indication": r.VerifiedReport.clinical_indication,
            "findings": r.VerifiedReport.findings,
            "impression": r.VerifiedReport.impression,
            "icd_codes": r.VerifiedReport.icd_codes or [],
            "recommendations": r.VerifiedReport.recommendations or [],
            "urgency_flag": r.VerifiedReport.urgency_flag,
            "similarity": round(1 - float(r.distance), 3),
        }
        for r in rows
        if float(r.distance) < 0.5
    ]


def build_few_shot_context(examples: list[dict]) -> str:
    if not examples:
        return ""
    lines = ["SIMILAR VERIFIED REPORTS FROM THIS CENTRE (learn from these patterns):"]
    for i, r in enumerate(examples, 1):
        lines.append(f"\nExample {i} [{r['modality']} | {r['body_part']} | similarity: {r['similarity']}]:")
        if r["findings"]:
            lines.append(f"  Findings: {r['findings'][:300]}")
        if r["impression"]:
            lines.append(f"  Impression: {r['impression'][:200]}")
        if r["icd_codes"]:
            codes = ", ".join(c.get("code", "") for c in r["icd_codes"][:3])
            lines.append(f"  ICD codes used: {codes}")
        if r["urgency_flag"] != "ROUTINE":
            lines.append(f"  Urgency: {r['urgency_flag']}")
    return "\n".join(lines)
