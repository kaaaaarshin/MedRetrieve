"""
DICOM Image Router — provides key-image and metadata endpoints for AI Vision.

These endpoints fetch DICOM data from dcm4chee via WADO-RS, render to JPEG,
and extract clinically relevant metadata. Used by the frontend to feed
the AI analysis pipeline with actual imaging data.

PATIENT SAFETY:
- Images are rendered server-side to ensure consistent quality
- Metadata is extracted from DICOM headers, not user-provided
- All endpoints are read-only — no modification of DICOM data
"""

import logging
from fastapi import APIRouter, HTTPException

from app.services.vision_service import (
    get_key_image_b64,
    get_study_metadata,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dicom", tags=["DICOM Image"])


@router.get("/key-image/{study_uid}")
async def get_key_image(study_uid: str, modality: str = "CT"):
    """
    Fetch a representative key image from dcm4chee for AI Vision analysis.

    Returns a base64-encoded JPEG of the middle slice from the first series.
    The image has appropriate windowing applied based on modality.

    If the study is not found or rendering fails, returns a 404 with
    an explanatory message — the frontend should fall back to text-only analysis.
    """
    if not study_uid or study_uid == "undefined":
        raise HTTPException(status_code=400, detail="Valid study_uid is required")

    try:
        image_b64 = await get_key_image_b64(study_uid, modality=modality)
        if not image_b64:
            raise HTTPException(
                status_code=404,
                detail="Could not fetch or render key image. Study may still be indexing.",
            )
        return {
            "study_uid": study_uid,
            "modality": modality,
            "image_base64": image_b64,
            "format": "jpeg",
            "source": "wado_rs_server_render",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Key image endpoint failed for %s: %s", study_uid, e)
        raise HTTPException(status_code=500, detail="Internal error fetching key image")


@router.get("/metadata/{study_uid}")
async def get_metadata(study_uid: str):
    """
    Extract clinically relevant DICOM metadata from the first instance of a study.

    Returns tags such as:
    - Technique: slice thickness, kVp, tube current, contrast agent
    - Patient: age, sex, weight (from DICOM headers)
    - Acquisition: protocol, sequence parameters, field strength (MR)
    - Equipment: manufacturer, model, software version

    This metadata enriches AI analysis by providing acquisition context
    that the radiologist's dictation may not explicitly mention.
    """
    if not study_uid or study_uid == "undefined":
        raise HTTPException(status_code=400, detail="Valid study_uid is required")

    try:
        metadata = await get_study_metadata(study_uid)
        if not metadata:
            raise HTTPException(
                status_code=404,
                detail="Could not extract metadata. Study may still be indexing.",
            )
        return {
            "study_uid": study_uid,
            "metadata": metadata,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Metadata endpoint failed for %s: %s", study_uid, e)
        raise HTTPException(status_code=500, detail="Internal error extracting metadata")
