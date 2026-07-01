from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    transcribe,
    analyse,
    icd,
    drugs,
    admin,
    dicom_image,
    entity_icd,
)

from app.routers import transcript_icd

@asynccontextmanager

async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transcribe.router, prefix="/api/v1")
"""
app.include_router(analyse.router, prefix="/api/v1")
app.include_router(icd.router, prefix="/api/v1")
app.include_router(drugs.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(dicom_image.router, prefix="/api/v1")
app.include_router(entity_icd.router, prefix="/api/v1")
"""


app.include_router(entity_icd.router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "deepgram_configured": bool(settings.DEEPGRAM_API_KEY),
        "gpt4o_configured": bool(settings.OPENAI_API_KEY),
    }

app.include_router(
    transcript_icd.router,
    prefix="/api/v1"
)