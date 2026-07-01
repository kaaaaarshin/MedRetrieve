import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Query

from app.services.deepgram_service import stream_transcription, transcribe_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcribe", tags=["Transcription"])

# Accumulate full transcript per order session in memory
_sessions: dict[str, str] = {}


@router.websocket("/stream/{order_id}")
async def transcribe_stream(
    websocket: WebSocket,
    order_id: str,
    sample_rate: int = Query(16000),
):
    """
    WebSocket endpoint for real-time dictation via Deepgram Nova-3 Medical.

    Protocol:
      Client → server:  binary frames (PCM16 audio, mono, sample_rate Hz)
      Server → client:  JSON text frames

    Frame types sent to client:
      {"type": "transcript",    "text": "...", "is_final": bool, "speech_final": bool}
      {"type": "utterance_end"}
      {"type": "speech_started"}
      {"type": "error",         "message": "..."}
      {"type": "session_transcript", "full_text": "..."}  — on close
    """
    await websocket.accept()
    logger.info("Transcription session started: order=%s sample_rate=%d", order_id, sample_rate)
    _sessions[order_id] = ""
    accumulated: list[str] = []

    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def audio_generator():
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                return
            yield chunk

    async def on_transcript(event: dict):
        try:
            if event["type"] == "transcript":
                if event.get("speech_final"):
                    accumulated.append(event["text"])
                    _sessions[order_id] = " ".join(accumulated)
                    event["session_transcript"] = _sessions[order_id]
                await websocket.send_text(json.dumps(event))

            elif event["type"] == "utterance_end":
                await websocket.send_text(json.dumps({
                    "type": "utterance_end",
                    "session_transcript": _sessions.get(order_id, ""),
                }))

            else:
                await websocket.send_text(json.dumps(event))

        except Exception as exc:
            logger.warning("WS send error: %s", exc)

    deepgram_task = asyncio.create_task(
        stream_transcription(audio_generator(), on_transcript, sample_rate=sample_rate)
    )

    try:
        while True:
            data = await websocket.receive_bytes()
            await audio_queue.put(data)
    except WebSocketDisconnect:
        logger.info("Client disconnected: order=%s", order_id)
    except Exception as exc:
        logger.warning("WS receive error: %s", exc)
    finally:
        await audio_queue.put(None)
        try:
            await asyncio.wait_for(deepgram_task, timeout=4.0)
        except (asyncio.TimeoutError, Exception):
            deepgram_task.cancel()

        full = _sessions.pop(order_id, "")
        try:
            await websocket.send_text(json.dumps({
                "type": "session_transcript",
                "full_text": full,
            }))
        except Exception:
            pass
        logger.info("Transcription session ended: order=%s transcript_len=%d", order_id, len(full))


@router.post("/file")
async def transcribe_audio_file(
    order_id: str = Form(...),
    file: UploadFile = File(...),
):
    """Upload a recorded audio file for transcription (non-streaming)."""
    audio_bytes = await file.read()
    result = await transcribe_file(audio_bytes, file.content_type or "audio/wav")
    return {
        "order_id": order_id,
        "transcript": result["transcript"],
        "confidence": result["confidence"],
    }


@router.get("/session/{order_id}")
async def get_session_transcript(order_id: str):
    """Get accumulated transcript for an active session."""
    return {"order_id": order_id, "transcript": _sessions.get(order_id, "")}
