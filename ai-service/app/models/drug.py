from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Drug(Base):
    __tablename__ = "ai_drugs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    generic_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    brand_names: Mapped[str | None] = mapped_column(Text, nullable=True)   # comma-separated
    drug_class: Mapped[str | None] = mapped_column(String(200), nullable=True)
    indication: Mapped[str | None] = mapped_column(Text, nullable=True)
    standard_dose: Mapped[str | None] = mapped_column(String(200), nullable=True)
    route: Mapped[str | None] = mapped_column(String(50), nullable=True)   # oral/IV/IM
    contraindications: Mapped[str | None] = mapped_column(Text, nullable=True)
    in_india_formulary: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule: Mapped[str | None] = mapped_column(String(10), nullable=True)  # H/H1/X/OTC
