"""
Chat pipeline: retrieve listing context -> run agent -> return text (reference: agentic_rag workflow).
Skips DB fetch for greetings/short non-property messages so "hi" and stream mode feel instant.
"""
from typing import Any, AsyncIterator

from app.rag.retrieval import (
    get_listing_context_for_query,
    get_listing_context_and_references_for_query,
    needs_listing_context,
    is_simple_greeting,
    get_greeting_reply,
)
from app.agents.runtime import run_listing_agent, run_listing_agent_stream

STEPS_FETCH = "Fetching listings from database..."
STEPS_GENERATE = "Generating response..."

EMPTY_CONTEXT = "(No listings loaded for this query.)"


async def chat(user_message: str, limit_listings: int = 10) -> tuple[str, list[dict[str, Any]], list[str]]:
    """
    Get AI suggestion based on user message. Returns (reply, references, steps).
    Uses limit_listings=10 by default to keep context small and response fast.
    Instant canned reply for simple greetings; skips DB for other short messages.
    """
    if is_simple_greeting(user_message):
        return get_greeting_reply(user_message), [], [STEPS_GENERATE]
    if needs_listing_context(user_message):
        context, references = get_listing_context_and_references_for_query(user_message, limit=limit_listings)
        steps = [STEPS_FETCH, STEPS_GENERATE]
    else:
        context, references = EMPTY_CONTEXT, []
        steps = [STEPS_GENERATE]
    reply = await run_listing_agent(user_message, context)
    return reply, references, steps


async def chat_stream_with_steps(
    user_message: str, limit_listings: int = 10
) -> AsyncIterator[tuple[str, str]]:
    """
    Yields ("step", message) then ("chunk", content) for streaming with step updates.
    Instant reply for simple greetings (no LLM); skips DB for other short messages.
    """
    if is_simple_greeting(user_message):
        yield ("step", STEPS_GENERATE)
        yield ("chunk", get_greeting_reply(user_message))
        return
    if needs_listing_context(user_message):
        yield ("step", STEPS_FETCH)
        context = get_listing_context_for_query(user_message, limit=limit_listings)
    else:
        context = EMPTY_CONTEXT
    yield ("step", STEPS_GENERATE)
    async for chunk in run_listing_agent_stream(user_message, context):
        yield ("chunk", chunk)
