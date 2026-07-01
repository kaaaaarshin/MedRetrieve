from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Ray AI Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database (shared with RIS)
    DATABASE_URL: str = "postgresql+asyncpg://karshin@localhost/ray_ai_local"

    # Deepgram
    DEEPGRAM_API_KEY: str = ""
    DEEPGRAM_MODEL: str = "nova-3-medical"   # medical model for radiology terms

    # AI Models (Groq)
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    # AI Vector DB (pgvector)
    AI_DATABASE_URL: str = "postgresql+asyncpg://karshin@localhost:5432/ray_ai_local"

    # Embedding model
    EMBEDDING_DIMENSIONS: int = 768

    # Redis
    REDIS_URL: str = "redis://redis:6379/1"  # db=1, separate from RIS

    # RIS API
    RIS_API_URL: str = "http://ris-api:8000/api/v1"

    # dcm4chee
    DCM4CHEE_URL: str = "http://arc:8080/dcm4chee-arc/aets/DCM4CHEE"

    class Config:
        env_file = ".env"


settings = Settings()
