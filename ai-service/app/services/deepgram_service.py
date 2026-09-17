"""
Deepgram Nova-3 Medical — live streaming + file transcription.
Uses raw WebSocket connection directly to avoid Deepgram SDK version issues.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Callable

import websockets

from app.core.config import settings

logger = logging.getLogger(__name__)

_DG_WSS = "wss://api.deepgram.com/v1/listen"


async def stream_transcription(
    audio_chunks: AsyncGenerator[bytes, None],
    on_transcript: Callable[[dict], None],
    language: str = "en-IN",
    sample_rate: int = 16000,
) -> None:
    """
    Stream PCM16 audio to Deepgram Nova-3 Medical and call on_transcript for each result.
    Frontend sends 16kHz mono PCM16 binary frames over WebSocket.
    """
    if not settings.DEEPGRAM_API_KEY:
        await on_transcript({"type": "error", "message": "DEEPGRAM_API_KEY not configured"})
        return

    params = "&".join([
        "model=nova-3-medical",
        "encoding=linear16",
        f"sample_rate={sample_rate}",
        f"language={language}",
        "smart_format=true",
        "punctuate=true",
        "interim_results=true",
        "utterance_end_ms=1200",
        "vad_events=true",
        "channels=1",
    ])
    url = f"{_DG_WSS}?{params}"
    headers = {"Authorization": f"Token {settings.DEEPGRAM_API_KEY}"}

    try:
        async with websockets.connect(url, additional_headers=headers, ping_interval=10) as dg_ws:
            logger.info("Deepgram connection open — Nova-3 Medical, %d Hz", sample_rate)

            async def _receive_loop():
                async for raw in dg_ws:
                    try:
                        data = json.loads(raw)
                        kind = data.get("type", "")

                        if kind == "Results":
                            ch   = data.get("channel", {})
                            alts = ch.get("alternatives", [{}])
                            alt  = alts[0] if alts else {}
                            text = alt.get("transcript", "").strip()
                            if text:
                                await on_transcript({
                                    "type":         "transcript",
                                    "text":         text,
                                    "is_final":     data.get("is_final", False),
                                    "speech_final": data.get("speech_final", False),
                                    "confidence":   alt.get("confidence", 0.0),
                                    "words":        alt.get("words", []),
                                })
                        elif kind == "UtteranceEnd":
                            await on_transcript({"type": "utterance_end"})
                        elif kind == "SpeechStarted":
                            await on_transcript({"type": "speech_started"})
                        # Metadata / other frames — silently ignored
                    except json.JSONDecodeError:
                        pass
                    except Exception as exc:
                        logger.warning("Deepgram receive error: %s", exc)

            recv_task = asyncio.create_task(_receive_loop())

            try:
                async for chunk in audio_chunks:
                    try:
                        await dg_ws.send(chunk)
                    except websockets.exceptions.ConnectionClosed:
                        break
            finally:
                # Ask Deepgram for final results, then close cleanly
                try:
                    await dg_ws.send(json.dumps({"type": "CloseStream"}))
                    await asyncio.wait_for(recv_task, timeout=3.0)
                except (asyncio.TimeoutError, Exception):
                    recv_task.cancel()

            logger.info("Deepgram connection closed cleanly")

    except websockets.exceptions.WebSocketException as exc:
        logger.error("Deepgram WebSocket error: %s", exc)
        await on_transcript({"type": "error", "message": f"Deepgram connection failed: {exc}"})
    except Exception as exc:
        logger.error("Deepgram unexpected error: %s", exc)
        await on_transcript({"type": "error", "message": str(exc)})


async def transcribe_file(audio_bytes: bytes, mimetype: str = "audio/wav") -> dict:
    """One-shot file transcription using Deepgram REST API."""
    import httpx
    if not settings.DEEPGRAM_API_KEY:
        return {"transcript": "", "confidence": 0.0}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.deepgram.com/v1/listen"
            "?model=nova-3-medical&smart_format=true&punctuate=true&language=en-IN",
            headers={
                "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
                "Content-Type": mimetype,
            },
            content=audio_bytes,
        )
        r.raise_for_status()
        data = r.json()

    try:
        alt = data["results"]["channels"][0]["alternatives"][0]
        return {"transcript": alt.get("transcript", ""), "confidence": alt.get("confidence", 0.0)}
    except (KeyError, IndexError):
        return {"transcript": "", "confidence": 0.0}
