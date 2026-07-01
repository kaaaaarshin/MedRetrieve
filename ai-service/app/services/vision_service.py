"""
DICOM Vision Service — Server-side DICOM image rendering + GPT-4o Vision analysis.

Fetches a representative key image from dcm4chee via WADO-RS, renders DICOM
pixel data to JPEG using pydicom + Pillow, and sends to GPT-4o Vision for
multi-modal radiology analysis.

PATIENT SAFETY:
- All Vision-based findings are tagged with source="ai_vision"
- Findings are assistive only — require radiologist sign-off
- Falls back gracefully to text-only analysis if image fetch/render fails
"""

import base64
import io
import logging
from typing import Optional

import httpx
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Window/Level presets by modality ─────────────────────────────────────────
# These are standard radiological windowing presets for common modalities.
# Ensures the rendered JPEG has clinically appropriate contrast.

_WINDOW_PRESETS: dict[str, tuple[float, float]] = {
    # modality → (window_center, window_width)
    "CT":  (40, 400),      # soft-tissue window (reasonable default)
    "CR":  (2048, 4096),   # computed radiography — full dynamic range
    "DX":  (2048, 4096),   # digital X-ray
    "XR":  (2048, 4096),   # X-ray alias
    "MR":  (0, 0),         # auto — use DICOM header or percentile stretch
    "MG":  (2048, 4096),   # mammography
    "US":  (0, 0),         # ultrasound — auto
    "NM":  (0, 0),         # nuclear medicine — auto
    "PT":  (0, 0),         # PET — auto
}

# CT sub-windows (can be toggled in future versions)
_CT_WINDOWS = {
    "soft_tissue": (40, 400),
    "bone":        (300, 1500),
    "lung":        (-600, 1500),
    "brain":       (40, 80),
    "liver":       (60, 160),
}


async def _get_keycloak_token() -> str:
    """Get a Keycloak service-account token for dcm4chee access."""
    async with httpx.AsyncClient(verify=False, timeout=10) as client:
        r = await client.post(
            f"https://keycloak:8843/realms/dcm4che/protocol/openid-connect/token",
            data={
                "client_id":  "dcm4chee-arc-ui",
                "username":   "admin",
                "password":   "changeit",
                "grant_type": "password",
                "scope":      "openid",
            },
        )
        r.raise_for_status()
        return r.json()["access_token"]


async def _auth_headers() -> dict[str, str]:
    token = await _get_keycloak_token()
    return {"Authorization": f"Bearer {token}"}


# ── WADO-RS helpers ──────────────────────────────────────────────────────────

async def fetch_series_list(study_uid: str) -> list[dict]:
    """QIDO-RS: get series list for a study."""
    url = f"{settings.DCM4CHEE_URL}/rs/studies/{study_uid}/series"
    try:
        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            resp = await client.get(url, headers=await _auth_headers())
            if resp.status_code == 204:
                return []
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("Series query failed for %s: %s", study_uid, e)
        return []


async def fetch_instance_list(study_uid: str, series_uid: str) -> list[dict]:
    """QIDO-RS: get instance list for a series."""
    url = f"{settings.DCM4CHEE_URL}/rs/studies/{study_uid}/series/{series_uid}/instances"
    try:
        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            resp = await client.get(url, headers=await _auth_headers())
            if resp.status_code == 204:
                return []
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("Instance query failed for %s/%s: %s", study_uid, series_uid, e)
        return []


async def fetch_dicom_instance(study_uid: str, series_uid: str, instance_uid: str) -> bytes | None:
    """WADO-RS: fetch a single DICOM instance as raw bytes."""
    url = (
        f"{settings.DCM4CHEE_URL}/rs/studies/{study_uid}"
        f"/series/{series_uid}/instances/{instance_uid}"
    )
    try:
        headers = await _auth_headers()
        headers["Accept"] = "multipart/related; type=\"application/dicom\""
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning("WADO-RS returned %s for %s", resp.status_code, instance_uid)
                return None

            content_type = resp.headers.get("Content-Type", "")
            body = resp.content

            # Parse multipart/related — extract the DICOM part
            if "multipart" in content_type:
                # Extract boundary
                boundary = None
                for part in content_type.split(";"):
                    part = part.strip()
                    if part.lower().startswith("boundary="):
                        boundary = part.split("=", 1)[1].strip('"').strip("'")
                        break

                if boundary:
                    # Split by boundary and find the DICOM part
                    parts = body.split(f"--{boundary}".encode())
                    for part in parts:
                        if b"application/dicom" in part[:500] or b"\x00" in part[:200]:
                            # Find the body after the double CRLF header separator
                            header_end = part.find(b"\r\n\r\n")
                            if header_end >= 0:
                                return part[header_end + 4:]
                            # Try with just \n\n
                            header_end = part.find(b"\n\n")
                            if header_end >= 0:
                                return part[header_end + 2:]
                    # If parsing failed, return raw body (might be single-part)
                    return body
                else:
                    return body
            else:
                return body
    except Exception as e:
        logger.error("WADO-RS fetch failed for %s: %s", instance_uid, e)
        return None


# ── DICOM rendering ──────────────────────────────────────────────────────────

def _apply_windowing(pixel_array: np.ndarray, center: float, width: float) -> np.ndarray:
    """Apply window/level to pixel data, returning uint8 array."""
    lower = center - width / 2
    upper = center + width / 2
    clipped = np.clip(pixel_array.astype(np.float64), lower, upper)
    normalized = ((clipped - lower) / (upper - lower) * 255).astype(np.uint8)
    return normalized


def _auto_window(pixel_array: np.ndarray) -> np.ndarray:
    """Auto-window using percentile stretch (P2/P98)."""
    p2 = np.percentile(pixel_array, 2)
    p98 = np.percentile(pixel_array, 98)
    if p98 <= p2:
        p98 = p2 + 1
    clipped = np.clip(pixel_array.astype(np.float64), p2, p98)
    normalized = ((clipped - p2) / (p98 - p2) * 255).astype(np.uint8)
    return normalized


def render_dicom_to_jpeg(dcm_bytes: bytes, modality: str = "CT", quality: int = 85) -> bytes | None:
    """
    Render DICOM pixel data to JPEG bytes.

    Applies appropriate windowing based on modality, handles
    RescaleSlope/RescaleIntercept for CT Hounsfield units.
    """
    try:
        import pydicom
        from PIL import Image

        ds = pydicom.dcmread(io.BytesIO(dcm_bytes))

        if not hasattr(ds, "PixelData"):
            logger.warning("DICOM has no PixelData")
            return None

        pixel_array = ds.pixel_array.astype(np.float64)

        # Apply rescale slope/intercept (CT → Hounsfield units)
        slope = getattr(ds, "RescaleSlope", 1)
        intercept = getattr(ds, "RescaleIntercept", 0)
        if slope != 1 or intercept != 0:
            pixel_array = pixel_array * float(slope) + float(intercept)

        # Apply windowing
        preset = _WINDOW_PRESETS.get(modality.upper(), (0, 0))
        if preset[0] == 0 and preset[1] == 0:
            # Auto-window from DICOM header or percentile stretch
            wc = getattr(ds, "WindowCenter", None)
            ww = getattr(ds, "WindowWidth", None)
            if wc is not None and ww is not None:
                # Handle multi-value window center/width
                if hasattr(wc, "__iter__"):
                    wc = wc[0] if len(wc) > 0 else wc
                if hasattr(ww, "__iter__"):
                    ww = ww[0] if len(ww) > 0 else ww
                img_array = _apply_windowing(pixel_array, float(wc), float(ww))
            else:
                img_array = _auto_window(pixel_array)
        else:
            img_array = _apply_windowing(pixel_array, preset[0], preset[1])

        # Handle PhotometricInterpretation
        photometric = getattr(ds, "PhotometricInterpretation", "MONOCHROME2")
        if photometric == "MONOCHROME1":
            img_array = 255 - img_array

        # Create PIL Image
        img = Image.fromarray(img_array)
        if img.mode != "L" and img.mode != "RGB":
            img = img.convert("L")

        # Resize if very large (>1024px) to keep GPT-4o Vision costs down
        max_dim = 1024
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Save as JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()

    except Exception as e:
        logger.error("DICOM rendering failed: %s", e)
        return None


def extract_dicom_metadata(dcm_bytes: bytes) -> dict:
    """
    Extract clinically relevant DICOM metadata for AI context.

    Returns patient demographics, acquisition technique, and study-level info.
    """
    try:
        import pydicom
        ds = pydicom.dcmread(io.BytesIO(dcm_bytes), stop_before_pixels=True)

        def _get(tag_name: str, default: str = "") -> str:
            val = getattr(ds, tag_name, None)
            if val is None:
                return default
            return str(val).strip()

        return {
            # Patient
            "patient_age": _get("PatientAge"),
            "patient_sex": _get("PatientSex"),
            "patient_weight": _get("PatientWeight"),
            # Study
            "study_description": _get("StudyDescription"),
            "study_date": _get("StudyDate"),
            "institution_name": _get("InstitutionName"),
            "referring_physician": _get("ReferringPhysicianName"),
            # Series / Acquisition
            "modality": _get("Modality"),
            "series_description": _get("SeriesDescription"),
            "body_part_examined": _get("BodyPartExamined"),
            "protocol_name": _get("ProtocolName"),
            # Technique
            "slice_thickness": _get("SliceThickness"),
            "spacing_between_slices": _get("SpacingBetweenSlices"),
            "kvp": _get("KVP"),
            "exposure_time": _get("ExposureTime"),
            "tube_current": _get("XRayTubeCurrent"),
            "contrast_bolus_agent": _get("ContrastBolusAgent"),
            "contrast_bolus_route": _get("ContrastBolusRoute"),
            "image_orientation_patient": _get("ImageOrientationPatient"),
            "pixel_spacing": _get("PixelSpacing"),
            "rows": _get("Rows"),
            "columns": _get("Columns"),
            "bits_allocated": _get("BitsAllocated"),
            "magnetic_field_strength": _get("MagneticFieldStrength"),
            "scanning_sequence": _get("ScanningSequence"),
            "sequence_variant": _get("SequenceVariant"),
            "repetition_time": _get("RepetitionTime"),
            "echo_time": _get("EchoTime"),
            "manufacturer": _get("Manufacturer"),
            "manufacturer_model_name": _get("ManufacturerModelName"),
            "software_versions": _get("SoftwareVersions"),
        }
    except Exception as e:
        logger.error("DICOM metadata extraction failed: %s", e)
        return {}


# ── High-level API ───────────────────────────────────────────────────────────

async def get_key_image_b64(study_uid: str, modality: str = "CT") -> Optional[str]:
    """
    Fetch a representative key image from dcm4chee and return as base64 JPEG.

    Strategy: pick the middle instance from the first (largest) series.
    This gives a representative slice for cross-sectional imaging.

    Returns None if fetch/render fails — caller should fall back to text-only.
    """
    series_list = await fetch_series_list(study_uid)
    if not series_list:
        logger.warning("No series found for study %s", study_uid)
        return None

    # Pick the first series (often the primary acquisition)
    # QIDO-RS returns series with tags in DICOM JSON format
    first_series = series_list[0]
    series_uid_tag = first_series.get("0020000E", {})
    series_uid = series_uid_tag.get("Value", [None])[0] if series_uid_tag else None
    if not series_uid:
        logger.warning("Could not extract SeriesInstanceUID from QIDO-RS response")
        return None

    # Get instances in this series
    instances = await fetch_instance_list(study_uid, series_uid)
    if not instances:
        logger.warning("No instances in series %s", series_uid)
        return None

    # Pick the middle instance (representative slice)
    mid_idx = len(instances) // 2
    instance = instances[mid_idx]
    instance_uid_tag = instance.get("00080018", {})
    instance_uid = instance_uid_tag.get("Value", [None])[0] if instance_uid_tag else None
    if not instance_uid:
        logger.warning("Could not extract SOPInstanceUID from QIDO-RS response")
        return None

    # Fetch DICOM bytes
    dcm_bytes = await fetch_dicom_instance(study_uid, series_uid, instance_uid)
    if not dcm_bytes:
        return None

    # Render to JPEG
    jpeg_bytes = render_dicom_to_jpeg(dcm_bytes, modality=modality)
    if not jpeg_bytes:
        return None

    return base64.b64encode(jpeg_bytes).decode("ascii")


async def get_study_metadata(study_uid: str) -> dict:
    """
    Fetch DICOM metadata from the first instance of the study.

    Returns a dict of clinically relevant DICOM tags.
    """
    series_list = await fetch_series_list(study_uid)
    if not series_list:
        return {}

    first_series = series_list[0]
    series_uid_tag = first_series.get("0020000E", {})
    series_uid = series_uid_tag.get("Value", [None])[0] if series_uid_tag else None
    if not series_uid:
        return {}

    instances = await fetch_instance_list(study_uid, series_uid)
    if not instances:
        return {}

    # Use the first instance for metadata (metadata is consistent within a series)
    instance = instances[0]
    instance_uid_tag = instance.get("00080018", {})
    instance_uid = instance_uid_tag.get("Value", [None])[0] if instance_uid_tag else None
    if not instance_uid:
        return {}

    dcm_bytes = await fetch_dicom_instance(study_uid, series_uid, instance_uid)
    if not dcm_bytes:
        return {}

    return extract_dicom_metadata(dcm_bytes)
