try:
    # Prefer the standalone package used with Pydantic v2
    from pydantic_settings import BaseSettings  # type: ignore[import]
except ImportError:
    # Fallback for environments that still use Pydantic v1
    from pydantic import BaseSettings  # type: ignore[assignment]

class Settings(BaseSettings):
    MONGO_URL: str
    MONGO_DB: str = "livebhoomi"
    AI_COLLECTION: str = "ai_documents"

    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"

    EMBEDDINGS_PROVIDER: str = "openrouter"  # openrouter | openai
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536

    VOICE_PROVIDER: str = "openai"  # openai | none
    OPENAI_API_KEY: str | None = None
    STT_MODEL: str = "gpt-4o-mini-transcribe"
    TTS_MODEL: str = "gpt-4o-mini-tts"

    LIVEKIT_API_KEY: str | None = None
    LIVEKIT_API_SECRET: str | None = None
    LIVEKIT_URL: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()