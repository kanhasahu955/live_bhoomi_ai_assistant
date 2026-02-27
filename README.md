# Live Bhoomi AI Backend

Python FastAPI service that **reads your database** and provides **AI suggestions by text and voice**, using the same patterns as `agentic_rag_contracts` (configs, agents, RAG, pipeline).

## Features

- **Text chat**: `POST /ai/chat` – send a message, get listing suggestions based on MongoDB data.
- **Voice input**: `POST /ai/voice` – upload an audio file (e.g. webm/mp3), get a text reply (STT → AI → response).
- **Text-to-speech**: `POST /ai/voice/tts` – convert a text reply to speech (mp3) for playback.

The AI uses **only** listings from your MongoDB (same DB as the Fastify backend). It suggests properties by city, type (sale/rent), price, and other criteria.

## Setup

1. **Environment**  
   Copy `.env.example` to `.env` and set:
   - `MONGO_URL`, `MONGO_DB` – same MongoDB as your Fastify app (Prisma uses collection `Listing`).
   - `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL` – for the LLM (e.g. OpenRouter).
   - Optional voice: `OPENAI_API_KEY`, `VOICE_PROVIDER=openai` for STT (Whisper) and TTS.

2. **Install and run**
   ```bash
   cd python_backend
   uv sync   # or: pip install -e .
   uv run uvicorn main:app --reload --host 0.0.0.0 --port 8001
   ```
   Or: `python main.py` (runs on port 8001).

3. **Docs**  
   Open http://localhost:8001/docs for Swagger UI.

## Project layout (reference: agentic_rag_contracts)

- `configs/agents.yaml` – agent definitions (listing_agent, system_prompt path).
- `configs/models.yaml` – LLM config (primary: OpenRouter model, temperature, max_tokens). Env overrides.
- `configs/prompts/system/` – system prompt for the listing agent (`listing_agent.md`).
- `app/config_loader.py` – load YAML/prompt files (`get_agents_config`, `get_models_config`).
- `app/db/listings.py` – read listings from MongoDB, format for RAG context.
- `app/rag/retrieval.py` – build listing context for a user query (filters: city, type, price).
- `app/agents/tools.py` – tools (e.g. `search_listings`) for the agent.
- `app/agents/runtime.py` – LLM (OpenRouter) + system prompt + context → response.
- `app/pipeline/chat.py` – pipeline: retrieve context → run agent → return text.
- `app/api/routes.py` – FastAPI routes: `/ai/chat`, `/ai/voice`, `/ai/voice/tts`.
- `main.py` – FastAPI app and CORS.

## API summary

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ai/chat` | Body: `{"message": "..."}`. Returns `{"reply": "..."}`. |
| POST | `/ai/chat/stream` | Body: `{"message": "..."}`. Streams reply as Server-Sent Events (`text/event-stream`). |
| POST | `/ai/voice` | Form: `audio` file. Returns `{"reply": "..."}` (text). |
| POST | `/ai/voice/tts` | Body: `{"message": "..."}`. Returns `audio/mpeg`. |
