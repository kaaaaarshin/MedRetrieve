from pydantic import BaseModel


class PatientContext(BaseModel):
    age: int | None = None
    sex: str | None = None
    allergies: str | None = None
    current_medications: str | None = None
    medical_history: str | None = None


class AnalyseRequest(BaseModel):
    transcript: str
    order_id: str
    modality: str
    body_part: str
    clinical_indication: str | None = None
    patient_context: PatientContext = PatientContext()
    prior_reports: list[str] | None = None
    # If True, skips ICD enrichment (faster, use for incremental)
    incremental: bool = False
    # GPT-4o Vision: optional base64-encoded JPEG of a DICOM key image
    image_base64: str | None = None
    # DICOM-level metadata (technique, contrast, slice thickness, etc.)
    dicom_metadata: dict | None = None


class ICDCode(BaseModel):
    code: str
    label: str
    confidence: float = 1.0
    verified: bool = True


class DrugSuggestion(BaseModel):
    generic_name: str
    dose: str | None = None
    route: str | None = None
    indication: str | None = None
    note: str = "FOR REFERRING PHYSICIAN — not a radiologist prescription"


class SOAPNote(BaseModel):
    subjective: str = ""   # patient history, symptoms, clinical indication
    objective: str = ""    # imaging findings — what is seen
    assessment: str = ""   # radiologist interpretation and diagnosis
    plan: str = ""         # recommended next steps / follow-up


class SuggestionResponse(BaseModel):
    order_id: str
    transcript: str
    impression: str
    findings_structured: str
    soap: SOAPNote = SOAPNote()
    icd_codes: list[ICDCode]
    differentials: list[str]
    recommendations: list[str]
    drug_suggestions: list[DrugSuggestion]
    treatment_plan: str
    urgency_flag: str
    urgency_reason: str
    follow_up: str
    critical_findings: list[str]
    confidence_score: float
    # Vision analysis: findings from AI image analysis (tagged for safety)
    vision_findings: list[str] = []
    # Tracks the source of each analysis component: "transcript", "ai_vision", "combined"
    analysis_sources: list[str] = []


class ICD10SearchResponse(BaseModel):
    code: str
    label: str
    category: str | None
    score: float = 1.0


class TranscribeRequest(BaseModel):
    order_id: str
    language: str = "en-IN"
