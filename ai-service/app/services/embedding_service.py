import asyncio
import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model = None
_lock = asyncio.Lock()


async def get_model():
    global _model

    if _model is None:
        async with _lock:
            if _model is None:
                _model = SentenceTransformer(
                    "pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb"
                )

    return _model


async def embed(text: str) -> list[float]:
    model = await get_model()

    embedding = model.encode(
        text,
        normalize_embeddings=True,
    )

    return embedding.tolist()


async def embed_batch(texts: list[str]) -> list[list[float]]:
    model = await get_model()

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
    )

    return [e.tolist() for e in embeddings]