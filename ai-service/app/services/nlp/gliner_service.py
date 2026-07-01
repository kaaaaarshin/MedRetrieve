from gliner import GLiNER

model = GLiNER.from_pretrained(
    "urchade/gliner_medium-v2.1"
)

LABELS = [
    "radiology finding",
    "imaging finding",
    "chest imaging finding",
    "pulmonary finding",
    "thoracic abnormality",
    "medical abnormality",
    "disease",
    "pathology",
]




def extract_entities(text):

    entities = model.predict_entities(
        text,
        LABELS,
        threshold=0.30,
    )

    return [
        entity["text"].lower()
        for entity in entities
    ]

if __name__ == "__main__":

    transcript = """
CT CHEST:

There is a moderate right-sided pleural effusion with adjacent compressive atelectatic changes involving the right lower lobe. A small left apical pneumothorax is present without significant mediastinal shift. Patchy airspace consolidation is seen within the right middle and lower lobes. Multiple bilateral ground-glass opacities with peripheral fibrotic changes and traction bronchiectasis are noted. Mild cardiomegaly with diffuse pulmonary edema is present. Mild pleural thickening with calcified pleural plaques is identified. No cavitary lesion or hilar lymphadenopathy is seen.

MRI BRAIN:

There is an acute cerebral infarction involving the left frontal and parietal lobes with associated diffusion restriction. Mild surrounding cerebral edema and mass effect are present, resulting in approximately 4 mm of midline shift. Chronic encephalomalacia involving the right temporal lobe is noted with mild generalized cerebral atrophy. No intracerebral hemorrhage, epidural hematoma, subdural hematoma, hydrocephalus, or intracranial metastasis is identified.

CT ABDOMEN AND PELVIS:

The liver is enlarged with imaging features suggestive of liver cirrhosis. A well-defined hepatic lesion is noted within segment VI. Mild splenomegaly with moderate ascites is present. Multiple gallstones with associated gallbladder wall thickening are consistent with cholecystitis. Mild acute pancreatitis is seen. A left renal calculus with mild hydronephrosis is present. No bowel obstruction or intestinal perforation is identified.

MRI LUMBAR SPINE:

There is multilevel lumbar spondylosis with diffuse disc herniation causing moderate spinal stenosis at the L4-L5 level. Mild compression fracture involving the superior endplate of L2 is noted. No evidence of osteomyelitis or avascular necrosis. Mild facet joint osteoarthritis is present.
"""
    entities = extract_entities(transcript)

    print(entities)