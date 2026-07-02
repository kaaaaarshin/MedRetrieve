Doctor Dictation
        │
        ▼
Deepgram Nova-3 Medical
        │
        ▼
Transcript
        │
        ▼
GLiNER
        │
        ▼
Rule-Based Radiology Extractor
        │
        ▼
Entity Normalization
        │
        ▼
BioClinicalBERT Encoder
        │
        ▼
pgvector Semantic Search
        │
        ▼
Ranked ICD-10 Matches


# MedRetrieve

MedRetrieve is a hybrid clinical NLP pipeline designed for AI-assisted radiology workflows.

The system extracts clinically relevant findings from free-text radiology dictation using a combination of AI-based Named Entity Recognition (GLiNER) and deterministic rule-based extraction. Extracted findings are normalized into canonical medical concepts and semantically matched against ICD-10 using BioClinicalBERT embeddings stored in PostgreSQL with pgvector.

This project is intended as a clinical decision support component rather than an autonomous diagnostic system.


A hybrid clinical NLP pipeline that converts radiology dictation into structured medical findings and retrieves relevant ICD-10 codes using semantic search.

Features:
- Deepgram Nova-3 Medical speech transcription
- GLiNER AI-based medical entity extraction
- Rule-based radiology entity fallback
- Canonical medical entity normalization
- BioClinicalBERT embeddings
- pgvector semantic ICD retrieval
- FastAPI backend

1. pacsdb url to local url (app/core/config.py) 
2. ai_database url changed to local
3. switched .npy and .pkl vector data into a local database
4. added STOPWORD variable to icd_retriever 
5. icd_retrieval in FastAPI is legacy

------------------------------------------------------------------------

• RadGraph        = Best for radiology, but setup/training is heavier
• BioClinicalBERT = Good embeddings, mediocre out-of-the-box NER (CU)
• MedNER          = Varies depending on implementation
• scispaCy        = Fast, stable, production-friendly (Future Change)

------------------------------------------------------------------------

• Local Database name: ray_ai_local

•server to run the retrieval augmentation

activation 
cd ai-service
source .ai/bin/activate

python -m uvicorn app.main:app --reload
