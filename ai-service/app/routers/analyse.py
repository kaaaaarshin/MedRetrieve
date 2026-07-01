import logging
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.ai_database import get_ai_db
from app.schemas.ai import AnalyseRequest, SuggestionResponse, ICDCode, DrugSuggestion, SOAPNote
from app.services.gpt_service import analyse_transcript, analyse_incremental, analyse_with_image
from app.services.icd_service import validate_and_enrich_codes
from app.services.drug_service import get_drugs_by_indication
from app.services.learning_service import get_few_shot_examples, build_few_shot_context
from app.services.embedding_service import embed
from app.models.knowledge import SuggestionFeedback, VerifiedReport

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyse", tags=["Analysis"])


@router.post("/", response_model=SuggestionResponse)
async def analyse(
    data: AnalyseRequest,
    ris_db: AsyncSession = Depends(get_db),
    ai_db: AsyncSession = Depends(get_ai_db),
):
    patient_ctx = data.patient_context.model_dump()
    radiologist_id = patient_ctx.get("radiologist_id")

    # Merge DICOM metadata into patient context if provided
    dicom_meta = data.dicom_metadata
    if dicom_meta:
        # Enrich patient context with DICOM-level info
        if dicom_meta.get("patient_age") and not patient_ctx.get("age"):
            # Parse DICOM age format (e.g., "045Y" → 45)
            age_str = dicom_meta["patient_age"].replace("Y", "").replace("y", "").strip()
            try:
                patient_ctx["age"] = int(age_str)
            except ValueError:
                pass
        if dicom_meta.get("patient_sex") and not patient_ctx.get("sex"):
            patient_ctx["sex"] = dicom_meta["patient_sex"]

    # Track analysis sources for patient safety
    analysis_sources: list[str] = []

    # Incremental mode — lightweight, real-time while dictating (text-only for speed)
    if data.incremental:
        raw = await analyse_incremental(
            data.transcript, patient_ctx, data.modality, data.body_part, data.clinical_indication
        )
        analysis_sources.append("transcript")
        return SuggestionResponse(
            order_id=data.order_id,
            transcript=data.transcript,
            impression=raw.get("impression", ""),
            findings_structured=raw.get("findings_structured", ""),
            icd_codes=[ICDCode(**c) for c in raw.get("icd_codes", [])],
            differentials=raw.get("differentials", []),
            recommendations=raw.get("recommendations", []),
            drug_suggestions=[],
            treatment_plan="",
            urgency_flag=raw.get("urgency_flag", "ROUTINE"),
            urgency_reason="",
            follow_up="",
            critical_findings=[],
            confidence_score=0.0,
            vision_findings=[],
            analysis_sources=analysis_sources,
        )

    # Retrieve similar verified reports from this centre as few-shot examples
    examples = await get_few_shot_examples(ai_db, data.transcript, data.modality, radiologist_id)
    few_shot_context = build_few_shot_context(examples)

    # Decide: Vision (image + text) or text-only
    if data.image_base64:
        analysis_sources.append("ai_vision")
        analysis_sources.append("transcript")
        raw = await analyse_with_image(
            data.image_base64,
            data.transcript, patient_ctx, data.modality, data.body_part,
            data.clinical_indication, data.prior_reports, few_shot_context,
            dicom_meta,
        )
    else:
        analysis_sources.append("transcript")
        raw = await analyse_transcript(
            data.transcript, patient_ctx, data.modality, data.body_part,
            data.clinical_indication, data.prior_reports, few_shot_context,
            dicom_meta,
        )

    # Validate ICD codes against local RIS DB
    verified_icd = await validate_and_enrich_codes(ris_db, raw.get("icd_codes", []))

    # Drug suggestions — GPT-4o output + DB lookup by impression keywords
    drug_list = []
    impression = raw.get("impression", "")
    if impression:
        db_drugs = await get_drugs_by_indication(ris_db, impression[:100], limit=3)
        for d in raw.get("drug_suggestions", []):
            drug_list.append(DrugSuggestion(
                generic_name=d.get("generic_name", ""),
                dose=d.get("dose"),
                route=d.get("route"),
                indication=d.get("indication"),
            ))
        existing = {d.generic_name.lower() for d in drug_list}
        for d in db_drugs:
            if d["generic_name"].lower() not in existing:
                drug_list.append(DrugSuggestion(
                    generic_name=d["generic_name"],
                    dose=d.get("standard_dose"),
                    route=d.get("route"),
                    indication=d.get("indication"),
                ))

    from fastapi import HTTPException
    
    soap_raw = raw.get("soap", {})
    if "_error" in raw and raw["_error"]:
        raise HTTPException(status_code=500, detail=raw["_error"])
    
    soap = SOAPNote(
        subjective=soap_raw.get("subjective", ""),
        objective=soap_raw.get("objective", ""),
        assessment=soap_raw.get("assessment", ""),
        plan=soap_raw.get("plan", ""),
    )

    # Extract vision-specific findings (lines prefixed with [AI-IMAGE])
    vision_findings: list[str] = []
    findings_text = raw.get("findings_structured", "")
    if findings_text:
        for line in findings_text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("[AI-IMAGE]"):
                vision_findings.append(stripped)

    return SuggestionResponse(
        order_id=data.order_id,
        transcript=data.transcript,
        impression=impression,
        findings_structured=raw.get("findings_structured", ""),
        soap=soap,
        icd_codes=[ICDCode(**c) for c in verified_icd],
        differentials=raw.get("differentials", []),
        recommendations=raw.get("recommendations", []),
        drug_suggestions=drug_list,
        treatment_plan=raw.get("treatment_plan", ""),
        urgency_flag=raw.get("urgency_flag", "ROUTINE"),
        urgency_reason=raw.get("urgency_reason", ""),
        follow_up=raw.get("follow_up", ""),
        critical_findings=raw.get("critical_findings", []),
        confidence_score=raw.get("confidence_score", 0.0),
        vision_findings=vision_findings,
        analysis_sources=analysis_sources,
    )


@router.post("/feedback")
async def submit_feedback(
    feedback: dict,
    ai_db: AsyncSession = Depends(get_ai_db),
):
    """
    Called after radiologist acts on each suggestion field.
    Captures accept / modify / reject per field — raw learning signal.
    """
    record = SuggestionFeedback(
        id=str(uuid.uuid4()),
        order_id=feedback.get("order_id", ""),
        radiologist_id=feedback.get("radiologist_id"),
        modality=feedback.get("modality", ""),
        body_part=feedback.get("body_part", ""),
        session_transcript=feedback.get("transcript"),
        impression_shown=feedback.get("impression_shown"),
        impression_action=feedback.get("impression_action"),
        impression_final=feedback.get("impression_final"),
        icd_shown=feedback.get("icd_shown"),
        icd_accepted=feedback.get("icd_accepted"),
        icd_rejected=feedback.get("icd_rejected"),
        icd_added_by_doctor=feedback.get("icd_added_by_doctor"),
        recommendations_shown=feedback.get("recommendations_shown"),
        recommendations_accepted=feedback.get("recommendations_accepted"),
        recommendations_rejected=feedback.get("recommendations_rejected"),
        urgency_shown=feedback.get("urgency_shown"),
        urgency_accepted=feedback.get("urgency_accepted"),
        urgency_final=feedback.get("urgency_final"),
        quality_score=feedback.get("quality_score"),
    )
    ai_db.add(record)
    await ai_db.flush()
    return {"status": "ok", "feedback_id": record.id}


@router.post("/learn")
async def store_verified_report(
    report: dict,
    ai_db: AsyncSession = Depends(get_ai_db),
):
    """
    Called when a report is verified and delivered.
    Embeds findings+impression and stores as a future few-shot example.
    Over time GPT-4o suggestions align with this centre's style.
    """
    findings = report.get("findings", "")
    impression = report.get("impression", "")
    embed_text = f"{report.get('modality', '')} {report.get('body_part', '')} {findings} {impression}"

    vec = await embed(embed_text)

    record = VerifiedReport(
        id=str(uuid.uuid4()),
        order_id=report.get("order_id", ""),
        radiologist_id=report.get("radiologist_id"),
        modality=report.get("modality", ""),
        body_part=report.get("body_part", ""),
        clinical_indication=report.get("clinical_indication"),
        findings=findings,
        impression=impression,
        icd_codes=report.get("icd_codes"),
        recommendations=report.get("recommendations"),
        urgency_flag=report.get("urgency_flag", "ROUTINE"),
        ai_impression_accepted=report.get("ai_impression_accepted"),
        ai_impression_modified=report.get("ai_impression_modified"),
        fields_accepted=report.get("fields_accepted"),
        fields_modified=report.get("fields_modified"),
        fields_rejected=report.get("fields_rejected"),
        embedding=vec,
    )
    ai_db.add(record)
    await ai_db.flush()
    return {"status": "ok", "report_id": record.id}
