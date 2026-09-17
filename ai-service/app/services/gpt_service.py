import json
import logging
import base64
from pathlib import Path

from groq import AsyncGroq

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "radiology_system.txt").read_text()

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _client


def _build_user_prompt(
    transcript: str,
    patient_context: dict,
    modality: str,
    body_part: str,
    clinical_indication: str | None,
    prior_reports: list[str] | None,
    few_shot_context: str | None = None,
    dicom_metadata: dict | None = None,
) -> str:
    lines = [
        f"MODALITY: {modality}",
        f"BODY PART: {body_part}",
        f"PATIENT: {patient_context.get('age', '?')}Y / {patient_context.get('sex', '?')}",
    ]
    if patient_context.get("allergies"):
        lines.append(f"ALLERGIES: {patient_context['allergies']}")
    if patient_context.get("current_medications"):
        lines.append(f"CURRENT MEDICATIONS: {patient_context['current_medications']}")
    if clinical_indication:
        lines.append(f"CLINICAL INDICATION: {clinical_indication}")

    # DICOM-level acquisition metadata (technique, contrast, etc.)
    if dicom_metadata:
        tech_lines = []
        if dicom_metadata.get("slice_thickness"):
            tech_lines.append(f"Slice Thickness: {dicom_metadata['slice_thickness']}mm")
        if dicom_metadata.get("contrast_bolus_agent"):
            tech_lines.append(f"Contrast: {dicom_metadata['contrast_bolus_agent']}")
        if dicom_metadata.get("contrast_bolus_route"):
            tech_lines.append(f"Contrast Route: {dicom_metadata['contrast_bolus_route']}")
        if dicom_metadata.get("kvp"):
            tech_lines.append(f"kVp: {dicom_metadata['kvp']}")
        if dicom_metadata.get("tube_current"):
            tech_lines.append(f"Tube Current: {dicom_metadata['tube_current']}mA")
        if dicom_metadata.get("magnetic_field_strength"):
            tech_lines.append(f"Field Strength: {dicom_metadata['magnetic_field_strength']}T")
        if dicom_metadata.get("scanning_sequence"):
            tech_lines.append(f"Sequence: {dicom_metadata['scanning_sequence']}")
        if dicom_metadata.get("repetition_time"):
            tech_lines.append(f"TR: {dicom_metadata['repetition_time']}ms")
        if dicom_metadata.get("echo_time"):
            tech_lines.append(f"TE: {dicom_metadata['echo_time']}ms")
        if dicom_metadata.get("protocol_name"):
            tech_lines.append(f"Protocol: {dicom_metadata['protocol_name']}")
        if dicom_metadata.get("series_description"):
            tech_lines.append(f"Series: {dicom_metadata['series_description']}")
        if dicom_metadata.get("rows") and dicom_metadata.get("columns"):
            tech_lines.append(f"Matrix: {dicom_metadata['rows']}×{dicom_metadata['columns']}")
        if tech_lines:
            lines.append("\nACQUISITION TECHNIQUE:")
            lines.extend(f"  {t}" for t in tech_lines)

    if prior_reports:
        lines.append("\nPRIOR REPORTS (most recent first):")
        for i, r in enumerate(prior_reports[:2], 1):
            lines.append(f"  [{i}] {r[:500]}")
    if few_shot_context:
        lines.append(f"\n{few_shot_context}")

    lines.append(f"\nRADIOLOGIST DICTATION TRANSCRIPT:\n\"{transcript}\"")
    lines.append("\nReturn JSON only.")
    return "\n".join(lines)


async def analyse_transcript(
    transcript: str,
    patient_context: dict,
    modality: str,
    body_part: str,
    clinical_indication: str | None = None,
    prior_reports: list[str] | None = None,
    few_shot_context: str | None = None,
    dicom_metadata: dict | None = None,
) -> dict:
    """Send transcript to Groq (LLaMA 3.3 70B) for radiology analysis."""
    if not settings.GROQ_API_KEY:
        return _empty_suggestion(reason="GROQ_API_KEY not configured. Add it to .env.")

    user_prompt = _build_user_prompt(
        transcript, patient_context, modality, body_part,
        clinical_indication, prior_reports, few_shot_context,
        dicom_metadata,
    )

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=4096,
        )
        raw = response.choices[0].message.content
        return json.loads(raw)
    except Exception as e:
        logger.error("Groq analysis failed: %s", e)
        return _empty_suggestion(reason=str(e))


async def analyse_with_image(
    image_base64: str,
    transcript: str,
    patient_context: dict,
    modality: str,
    body_part: str,
    clinical_indication: str | None = None,
    prior_reports: list[str] | None = None,
    few_shot_context: str | None = None,
    dicom_metadata: dict | None = None,
) -> dict:
    """
    Groq Vision: analyse both a DICOM image and radiologist transcript.

    Uses LLaMA 4 Scout (vision-capable) via Groq's OpenAI-compatible API.
    Sends a multi-part message with:
    1. The rendered DICOM image (base64 JPEG)
    2. The text prompt with patient context, transcript, and metadata

    PATIENT SAFETY: Vision-based findings are marked in the response so the
    radiologist knows which suggestions come from image analysis vs dictation.
    """
    if not settings.GROQ_API_KEY:
        return _empty_suggestion(reason="GROQ_API_KEY not configured. Add it to .env.")

    user_prompt = _build_user_prompt(
        transcript, patient_context, modality, body_part,
        clinical_indication, prior_reports, few_shot_context,
        dicom_metadata,
    )

    # Build multi-modal message content with image + text (OpenAI-compatible format)
    user_content = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_base64}",
            },
        },
        {
            "type": "text",
            "text": (
                "Above is a DICOM image from this study. Analyse BOTH the image "
                "AND the transcript below. In findings_structured, prefix any "
                "finding derived from the image with '[AI-IMAGE]'.\n\n"
                + user_prompt
            ),
        },
    ]

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.GROQ_VISION_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=4096,
        )
        raw = response.choices[0].message.content
        return json.loads(raw)
    except Exception as e:
        logger.error("Groq Vision analysis failed: %s", e)
        return _empty_suggestion(reason=str(e))


async def analyse_incremental(
    full_transcript: str,
    patient_context: dict,
    modality: str,
    body_part: str,
    clinical_indication: str | None = None,
) -> dict:
    """Lightweight real-time analysis on each utterance end."""
    if not settings.GROQ_API_KEY:
        return {}

    prompt = (
        f"MODALITY: {modality}, BODY PART: {body_part}, "
        f"PATIENT: {patient_context.get('age', '?')}Y/{patient_context.get('sex', '?')}\n"
        f"PARTIAL TRANSCRIPT: \"{full_transcript}\"\n\n"
        "Return JSON with only: impression, icd_codes (top 3), urgency_flag, differentials (top 3)."
    )

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content
        return json.loads(raw)
    except Exception as e:
        logger.error("Groq incremental analysis failed: %s", e)
        return {}


def _empty_suggestion(reason: str = "") -> dict:
    return {
        "impression": "",
        "findings_structured": "",
        "icd_codes": [],
        "differentials": [],
        "recommendations": [],
        "drug_suggestions": [],
        "treatment_plan": "",
        "urgency_flag": "ROUTINE",
        "urgency_reason": "",
        "follow_up": "",
        "critical_findings": [],
        "confidence_score": 0.0,
        "_error": reason,
    }
