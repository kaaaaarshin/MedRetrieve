from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

ai_engine = create_async_engine(settings.AI_DATABASE_URL, echo=False, pool_pre_ping=True)
AISessionLocal = async_sessionmaker(ai_engine, class_=AsyncSession, expire_on_commit=False)


class AIBase(DeclarativeBase):
    pass


async def get_ai_db():
    async with AISessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
