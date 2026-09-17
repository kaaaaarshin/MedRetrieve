from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column


from app.core.database import Base


class ICD10Code(Base):
    __tablename__ = "ai_icd10_codes"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    category: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    chapter: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
    )

    is_radiology_common: Mapped[bool] = mapped_column(
        default=False,
    )
