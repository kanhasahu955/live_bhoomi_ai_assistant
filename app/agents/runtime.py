"""
Agent runtime: run LLM with system prompt + listing context (reference: agentic_rag_contracts).
Uses configs/agents.yaml and configs/models.yaml when present; env overrides.
"""
from typing import Any, AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import settings
from app.config_loader import load_prompt, get_agents_config, get_models_config


def _llm_from_config() -> ChatOpenAI:
    """Build LLM from models.yaml with env override. Timeout to avoid hanging on slow APIs."""
    models_cfg = get_models_config()
    llm_cfg = (models_cfg.get("llms") or {}).get("primary") or {}
    return ChatOpenAI(
        model=settings.OPENROUTER_MODEL or llm_cfg.get("model", "openai/gpt-4o-mini"),
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL or llm_cfg.get("base_url", "https://openrouter.ai/api/v1"),
        temperature=llm_cfg.get("temperature", 0.4),
        max_tokens=llm_cfg.get("max_tokens", 512),
        request_timeout=90,
    )


def get_llm() -> ChatOpenAI:
    return _llm_from_config()


def _prompt_path_from_agent() -> str:
    """Resolve listing agent system prompt path from agents.yaml."""
    agents_cfg = get_agents_config()
    listing = (agents_cfg.get("agents") or {}).get("listing_agent") or {}
    return listing.get("system_prompt") or "configs/prompts/system/listing_agent.md"


def build_system_prompt(listing_context: str) -> str:
    """Load listing agent prompt (from config) and inject context."""
    path = _prompt_path_from_agent()
    raw = load_prompt(path)
    if not raw:
        raw = (
            "You are the Live Bhoomi AI assistant. Use ONLY the listing context below to suggest properties. "
            "Be concise for voice, a bit more detailed for text.\n\nListing context:\n{{LISTING_CONTEXT}}"
        )
    return raw.replace("{{LISTING_CONTEXT}}", listing_context)


async def run_listing_agent(user_message: str, listing_context: str) -> str:
    """
    Run the listing suggestion agent: system prompt (with context) + user message -> LLM -> response text.
    """
    llm = get_llm()
    system_text = build_system_prompt(listing_context)
    messages = [
        SystemMessage(content=system_text),
        HumanMessage(content=user_message),
    ]
    result = await llm.ainvoke(messages)
    return result.content if hasattr(result, "content") else str(result)


async def run_listing_agent_stream(user_message: str, listing_context: str) -> AsyncIterator[str]:
    """Stream LLM response token by token."""
    llm = get_llm()
    system_text = build_system_prompt(listing_context)
    messages = [
        SystemMessage(content=system_text),
        HumanMessage(content=user_message),
    ]
    async for chunk in llm.astream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content
