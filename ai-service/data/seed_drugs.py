"""
Seed script: common India-formulary drugs relevant to radiology findings.
Run: python data/seed_drugs.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.models.drug import Drug

DRUGS = [
    # Contrast reaction management
    ("Hydrocortisone", "Solu-Cortef", "Corticosteroid", "Contrast reaction, anaphylaxis", "100-500mg IV", "IV", "Active infection, viral diseases", True, "H"),
    ("Adrenaline (Epinephrine)", "Adrenalin", "Sympathomimetic", "Anaphylaxis, severe contrast reaction", "0.5mg IM (1:1000)", "IM", "None in emergency", True, "H"),
    ("Chlorpheniramine", "Piriton", "Antihistamine", "Mild contrast reaction, allergy", "10mg IV/IM", "IV/IM", "Narrow angle glaucoma", True, "OTC"),
    ("Promethazine", "Phenergan", "Antihistamine", "Contrast reaction, nausea", "25mg IM", "IM", "CNS depression", True, "H"),
    ("Salbutamol", "Asthalin", "Bronchodilator", "Bronchospasm post-contrast", "2.5mg nebulisation", "Inhaled", "Hyperthyroidism", True, "OTC"),

    # Pain management (post-finding recommendations)
    ("Etoricoxib", "Arcoxia", "COX-2 inhibitor NSAID", "Musculoskeletal pain, OA, disc herniation", "60-90mg OD", "Oral", "Renal/hepatic impairment, CV disease", True, "H"),
    ("Diclofenac", "Voveran", "NSAID", "Acute musculoskeletal pain, renal colic", "75mg BD", "Oral/IM", "Peptic ulcer, renal impairment", True, "H"),
    ("Tramadol", "Tramazac", "Opioid analgesic", "Moderate-severe acute pain", "50-100mg TDS", "Oral/IM", "Seizure disorder, MAOI use", True, "H"),
    ("Paracetamol", "Crocin, Dolo", "Analgesic/antipyretic", "Mild-moderate pain, fever", "500-1000mg TDS", "Oral", "Hepatic failure", True, "OTC"),
    ("Pregabalin", "Lyrica", "Neuropathic analgesic", "Neuropathic pain, radiculopathy", "75mg BD", "Oral", "Renal impairment (dose adjust)", True, "H"),

    # Respiratory / pulmonary
    ("Furosemide", "Lasix", "Loop diuretic", "Pulmonary oedema, pleural effusion", "40mg OD", "Oral/IV", "Anuria, severe hypokalaemia", True, "H"),
    ("Prednisolone", "Wysolone", "Corticosteroid", "Pulmonary fibrosis, sarcoidosis", "40-60mg OD tapering", "Oral", "Active TB, uncontrolled diabetes", True, "H"),
    ("Montelukast", "Singulair", "Leukotriene antagonist", "Asthma, allergic rhinitis", "10mg OD", "Oral", "Phenylketonuria", True, "H"),

    # Hepatobiliary
    ("Ursodeoxycholic acid", "Udiliv", "Choleretic", "Gallstones, primary biliary cholangitis", "8-10mg/kg/day BD-TDS", "Oral", "Acute cholecystitis, bile duct obstruction", True, "H"),
    ("Omeprazole", "Prilosec", "PPI", "Peptic ulcer, GERD", "20-40mg OD", "Oral", "None significant", True, "H"),

    # Antibiotics (post-infectious finding)
    ("Amoxicillin-Clavulanate", "Augmentin", "Beta-lactam antibiotic", "Pneumonia, UTI, soft tissue infection", "625mg TDS", "Oral", "Penicillin allergy", True, "H"),
    ("Ciprofloxacin", "Ciplox", "Fluoroquinolone", "UTI, GI infection", "500mg BD", "Oral", "Tendon disease history, epilepsy", True, "H"),
    ("Metronidazole", "Flagyl", "Nitroimidazole antibiotic", "Amoebic liver abscess, anaerobic infection", "400mg TDS x 5-10 days", "Oral", "1st trimester pregnancy", True, "H"),
    ("Piperacillin-Tazobactam", "Zosyn", "Beta-lactam/BLI", "Severe hospital-acquired infection, abscess", "4.5g q6h IV", "IV", "Penicillin allergy", True, "H"),

    # Anticoagulants (PE, DVT)
    ("Rivaroxaban", "Xarelto", "DOAC / Factor Xa inhibitor", "Pulmonary embolism, DVT", "15mg BD x21d, then 20mg OD", "Oral", "Severe renal impairment, active bleeding", True, "H"),
    ("Low Molecular Weight Heparin (Enoxaparin)", "Clexane", "Anticoagulant", "DVT, PE, ACS", "1mg/kg SC BD", "SC", "Active bleeding, HIT", True, "H"),
    ("Warfarin", "Warf", "Vitamin K antagonist", "AF, mechanical valves, DVT/PE (long term)", "Dose per INR", "Oral", "Pregnancy, active bleeding", True, "H"),

    # Oncology support
    ("Ondansetron", "Emeset", "5-HT3 antagonist antiemetic", "Chemotherapy-induced nausea, post-procedure", "8mg BD", "Oral/IV", "Long QT syndrome", True, "H"),
    ("Dexamethasone", "Decadron", "Corticosteroid", "Brain oedema (tumour), raised ICP", "4-8mg BD IV", "IV/Oral", "Active infection", True, "H"),

    # Thyroid
    ("Levothyroxine", "Thyronorm", "Thyroid hormone", "Hypothyroidism, goitre", "50-100mcg OD", "Oral", "Thyrotoxicosis, adrenal insufficiency", True, "H"),
    ("Carbimazole", "Neomercazole", "Antithyroid", "Hyperthyroidism, Graves disease", "10-40mg OD", "Oral", "Agranulocytosis history", True, "H"),

    # Contrast nephropathy prevention
    ("N-Acetylcysteine", "Mucomyst", "Antioxidant/mucolytic", "Contrast-induced nephropathy prevention", "600mg BD (day before and day of)", "Oral", "None significant", True, "H"),
    ("Normal Saline 0.9%", "NS", "IV Fluid", "Hydration pre/post contrast in CKD", "1ml/kg/hr for 12h pre/post", "IV", "Fluid overload, heart failure", True, "H"),
]


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        for row in DRUGS:
            drug = Drug(
                generic_name=row[0],
                brand_names=row[1],
                drug_class=row[2],
                indication=row[3],
                standard_dose=row[4],
                route=row[5],
                contraindications=row[6],
                in_india_formulary=row[7],
                schedule=row[8],
            )
            session.add(drug)
        await session.commit()
        print(f"Seeded {len(DRUGS)} drugs")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
