import re

CHEST_FINDINGS = [

    "pleural effusion",
    "pneumothorax",
    "hydropneumothorax",

    "consolidation",
    "airspace consolidation",
    "patchy consolidation",
    "focal consolidation",
    "lobar consolidation",

    "atelectasis",
    "atelectasis",
    "atelectatic",
    "atelectatic changes",
    "compressive atelectatic changes",
    "collapse",

    "pulmonary edema",
    "lung edema",

    "cardiomegaly",

    "fibrosis",
    "fibrotic changes",
    "pulmonary fibrosis",

    "ground glass opacity",
    "ground glass opacities",
    "ground-glass opacity",
    "ground-glass opacities",

    "bronchiectasis",

    "emphysema",

    "interstitial lung disease",

    "pulmonary nodule",

    "lung mass",

    "mediastinal shift",

    "pleural thickening",

    "pleural plaque",

    "hemothorax",

    "empyema",

    "cavitary lesion",

    "pulmonary embolism",

    "hilar enlargement",

    "lymphadenopathy",
]

BRAIN_FINDINGS = [

    "cerebral infarction",
    "acute infarct",

    "ischemic stroke",

    "intracerebral hemorrhage",
    "hemorrhage",

    "subdural hematoma",
    "epidural hematoma",

    "subarachnoid hemorrhage",

    "midline shift",

    "hydrocephalus",

    "cerebral edema",

    "brain metastasis",

    "space occupying lesion",

    "meningioma",

    "glioma",

    "mass effect",

    "encephalomalacia",

    "white matter changes",

    "atrophy",

    "diffusion restriction",
]

ABDOMEN_FINDINGS = [

    "appendicitis",

    "pancreatitis",

    "cholecystitis",

    "gallstones",

    "renal calculus",

    "kidney stone",

    "hydronephrosis",

    "liver cirrhosis",

    "hepatomegaly",

    "splenomegaly",

    "ascites",

    "bowel obstruction",

    "intestinal perforation",

    "diverticulitis",

    "colitis",

    "hepatic lesion",

    "liver mass",

    "renal mass",
]

MSK_FINDINGS = [

    "fracture",

    "dislocation",

    "osteoarthritis",

    "joint effusion",

    "osteomyelitis",

    "avascular necrosis",

    "ligament tear",

    "meniscal tear",

    "disc prolapse",

    "disc herniation",

    "spondylosis",

    "spinal stenosis",

    "compression fracture",
]

FINDING_TO_QUERY = {

    "atelectatic": "atelectasis",
    "atelectatic changes": "atelectasis",
    "compressive atelectatic changes": "atelectasis",

    "consolidation": "pneumonia",
    "airspace consolidation": "pneumonia",
    "patchy consolidation": "pneumonia",
    "focal consolidation": "pneumonia",
    "lobar consolidation": "pneumonia",

    "ground glass opacities": "interstitial lung disease",
    "ground-glass opacity": "interstitial lung disease",

    "fibrotic changes": "pulmonary fibrosis",
}

MEDICAL_FINDINGS = (
    CHEST_FINDINGS
    + BRAIN_FINDINGS
    + ABDOMEN_FINDINGS
    + MSK_FINDINGS
)

PATTERNS = {
    r"\batelect\w*": "atelectasis",
    r"\b\w*\s*pneumothorax\b": "pneumothorax",
    r"\bpleural\s+effusion(s)?\b": "pleural effusion",
    r"\bground[- ]glass\s+opacit(y|ies)\b": "ground glass opacity",
    r"\b(\w+\s+)?consolidation\b": "pneumonia",
    r"\bfibrotic?\s+changes\b": "pulmonary fibrosis",
}

def extract_entities(text: str) -> list[str]:
    text = text.lower()

    findings = []

    # Pattern-based extraction
    for pattern, canonical in PATTERNS.items():
        if re.search(pattern, text):
            findings.append(canonical)

    # Dictionary fallback
    for finding in MEDICAL_FINDINGS:

        pattern = re.escape(finding).replace(
            r"\ ",
            r"\s+",
        )

        if re.search(pattern, text):

            canonical = FINDING_TO_QUERY.get(
                finding,
                finding,
            )

            findings.append(canonical)

    return list(dict.fromkeys(findings))

