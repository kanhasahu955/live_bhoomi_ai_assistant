"""
AI endpoints: text chat and voice (STT -> chat -> TTS).
WebSocket /ai/ws for streaming chat (one message per connection).
"""
import json
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from config import settings
from app.pipeline.chat import chat as run_chat, chat_stream_with_steps
from app.db.status import get_db_status

router = APIRouter(prefix="/ai", tags=["AI"])
class ChatRequest(BaseModel):
    message: str
class ListingReference(BaseModel):
    id: str
    title: str
    price: float | None
    city: str
    locality: str
    state: str
    listingType: str
    propertyType: str
    bedrooms: int | None
    bathrooms: int | None
    area: float | None
    slug: str
class ChatResponse(BaseModel):
    reply: str
    references: list[ListingReference] = []
    steps: list[str] = []


@router.get("/db-status")
async def ai_db_status():
    """
    Return database connection status, database name, list of collections with document counts,
    and a small sample of Listing documents for the UI.
    """
    return get_db_status()


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(body: ChatRequest) -> ChatResponse:
    """
    Send a text message and get AI suggestions based on listings in the database.
    Returns reply and references (listings used as context) for cards/table.
    """
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    reply, refs, steps = await run_chat(body.message.strip())
    ref_models = [ListingReference(**r) for r in refs]
    return ChatResponse(reply=reply, references=ref_models, steps=steps)


@router.websocket("/ws")
async def ai_chat_websocket(websocket: WebSocket):
    """
    WebSocket for streaming chat. Send one JSON message: {"message": "your question"}.
    Server sends JSON lines: {"type":"step","message":"..."}, {"type":"chunk","content":"..."}, then {"type":"done","references":[...]}.
    """
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        data = json.loads(raw)
        message = (data.get("message") or "").strip()
        if not message:
            await websocket.send_json({"type": "error", "detail": "message is required"})
            return
    except (json.JSONDecodeError, KeyError) as e:
        await websocket.send_json({"type": "error", "detail": "Invalid JSON or missing 'message'"})
        return

    from app.rag.retrieval import (
        get_listing_context_and_references_for_query,
        needs_listing_context,
        is_simple_greeting,
        get_greeting_reply,
    )
    from app.pipeline.chat import EMPTY_CONTEXT, STEPS_FETCH, STEPS_GENERATE
    from app.agents.runtime import run_listing_agent_stream

    try:
        # Instant reply for "hi", "hello", etc. — no LLM, no DB (avoids timeout and slowness)
        if is_simple_greeting(message):
            await websocket.send_json({"type": "step", "message": STEPS_GENERATE})
            reply = get_greeting_reply(message)
            await websocket.send_json({"type": "chunk", "content": reply})
            await websocket.send_json({"type": "done", "references": []})
            return
        if needs_listing_context(message):
            await websocket.send_json({"type": "step", "message": STEPS_FETCH})
            context, refs = get_listing_context_and_references_for_query(message, limit=10)
        else:
            context = EMPTY_CONTEXT
            refs = []
        await websocket.send_json({"type": "step", "message": STEPS_GENERATE})
        async for chunk in run_listing_agent_stream(message, context):
            await websocket.send_json({"type": "chunk", "content": chunk})
        await websocket.send_json({"type": "done", "references": refs})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "detail": str(e)})
        except Exception:
            pass


@router.post("/chat/stream")
async def ai_chat_stream(body: ChatRequest) -> StreamingResponse:
    """
    Streams step events then reply chunks as SSE.
    event: step -> data: {"message": "..."}
    event: chunk -> data: {"content": "..."}
    """
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    async def event_stream():
        import json
        async for event_type, value in chat_stream_with_steps(body.message.strip()):
            if event_type == "step":
                yield f"event: step\ndata: {json.dumps({'message': value})}\n\n"
            else:
                yield f"event: chunk\ndata: {json.dumps({'content': value})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/voice", response_model=ChatResponse)
async def ai_voice_upload(audio: UploadFile = File(...)) -> Any:
    """
    Upload an audio file (e.g. webm, mp3, m4a). Returns text reply only.
    For TTS response, use POST /ai/voice with ?tts=1 and accept audio response (future).
    """
    if not settings.OPENAI_API_KEY or settings.VOICE_PROVIDER.lower() == "none":
        raise HTTPException(
            status_code=503,
            detail="Voice input is not configured. Set OPENAI_API_KEY and VOICE_PROVIDER=openai.",
        )
    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio", content, audio.content_type or "audio/webm"),
        )
        text = transcript.text if hasattr(transcript, "text") else str(transcript)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Speech-to-text failed: {e}")

    if not text or not text.strip():
        return ChatResponse(reply="I didn't catch that. Please try again or type your question.")

    reply, refs, steps = await run_chat(text.strip())
    ref_models = [ListingReference(**r) for r in refs]
    return ChatResponse(reply=reply, references=ref_models, steps=steps)


@router.post("/voice/tts", response_class=Response)
async def ai_voice_tts(body: ChatRequest) -> Response:
    """
    Convert text to speech (TTS). Returns audio bytes (mp3).
    Useful after getting a reply from /ai/chat or /ai/voice to play as voice.
    """
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="TTS not configured. Set OPENAI_API_KEY.")
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        resp = await client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=body.message.strip(),
        )
        return Response(
            content=resp.content,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=reply.mp3"},
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"TTS failed: {e}")
