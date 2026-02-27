"""
Live Bhoomi AI Backend – FastAPI app.
Reads listings from the database and gives suggestions by text and voice.
Reference: agentic_rag_contracts (configs, agents, RAG, pipeline).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as ai_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Optional: close DB client on shutdown
    # from app.db.listings import get_db
    # get_db().client.close()


app = FastAPI(
    title="Live Bhoomi AI API",
    description="AI suggestions for property listings – text and voice. Reads from your database.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_router)


@app.get("/")
async def root():
    return {
        "service": "Live Bhoomi AI",
        "docs": "/docs",
        "endpoints": {
            "chat": "POST /ai/chat – text message, get suggestions",
            "chat_stream": "POST /ai/chat/stream – stream reply as SSE",
            "chat_ws": "WebSocket /ai/ws – stream chat over WebSocket",
            "voice": "POST /ai/voice – upload audio, get text reply",
            "tts": "POST /ai/voice/tts – text to speech (mp3)",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


def main():
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )


if __name__ == "__main__":
    main()
