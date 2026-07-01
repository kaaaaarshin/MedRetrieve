from sqlalchemy import Text, Float
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ai_database import AIBase


class ICDEmbedding(AIBase):
    __tablename__ = "icd_embeddings"

    code: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    embedding: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False,
    )   