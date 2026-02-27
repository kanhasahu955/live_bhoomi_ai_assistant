"""
Retrieval for Live Bhoomi: build listing context from DB (reference: agentic_rag_contracts).
We use MongoDB listing fetch as "retrieval"; optional vector search can be added later.
"""
import re

from app.db.listings import build_listing_context, build_listing_context_and_references

# Keywords that suggest the user is asking about properties/listings (not just saying hi)
PROPERTY_QUERY_HINTS = (
    "property", "properties", "listing", "listings", "house", "flat", "apartment",
    "rent", "sale", "buy", "price", "bedroom", "bathroom", "bhk", "sqft", "area",
    "location", "city", "locality", "berhampur", "how many", "show", "find", "search",
    "suggest", "recommend", "available", "budget",
)


def needs_listing_context(message: str) -> bool:
    """
    Return False for greetings and short non-property messages so we skip DB fetch
    and respond quickly (e.g. "hi", "hello", "thanks").
    """
    q = message.strip()
    if not q or len(q) > 500:
        return True  # empty or very long: keep default behavior
    lower = q.lower()
    # Obvious greetings / small talk -> no listing context
    if lower in ("hi", "hello", "hey", "hey there", "hi there", "thanks", "thank you", "ok", "okay", "bye", "goodbye"):
        return False
    if re.match(r"^(hi|hello|hey|thanks|thank you)[\s,!.]*$", lower):
        return False
    # Very short and no property-related word -> skip DB to speed up stream
    if len(q) <= 20 and not any(h in lower for h in PROPERTY_QUERY_HINTS):
        return False
    return True


# Exact phrases that get an instant canned reply (no LLM) for fast WebSocket/stream
SIMPLE_GREETINGS = frozenset(
    {"hi", "hello", "hey", "hey there", "hi there", "thanks", "thank you", "ok", "okay", "bye", "goodbye"}
)


def is_simple_greeting(message: str) -> bool:
    """True if message is a short greeting we can reply to instantly without calling the LLM."""
    q = message.strip().lower()
    if not q or len(q) > 30:
        return False
    if q in SIMPLE_GREETINGS:
        return True
    if re.match(r"^(hi|hello|hey|thanks|thank you)[\s,!.]*$", q):
        return True
    return False


def get_greeting_reply(message: str) -> str:
    """Instant reply for simple greetings (no LLM call)."""
    q = message.strip().lower()
    if "thank" in q or "thanks" in q:
        return "You're welcome! Ask me about properties anytime."
    if "bye" in q or "goodbye" in q:
        return "Goodbye! Come back when you need property suggestions."
    if "ok" in q or "okay" in q:
        return "Got it. What would you like to know about properties?"
    return "Hi! I'm the Live Bhoomi assistant. Ask me about properties—by location, price, type, or \"how many\" in an area."


def _extract_location_phrase(query: str) -> str | None:
    """Extract a place phrase from patterns like 'in X', 'at X', 'X location', 'near X'."""
    q = query.strip()
    if not q:
        return None
    # "how many properties in berhampur lanjipalli" -> "berhampur lanjipalli"
    for pattern in [
        r"\b(?:in|at|near)\s+([a-zA-Z\s]+?)(?:\s+location|\s+area|,|\.|\?|$)",
        r"(?:properties?|listings?)\s+(?:in|at|near)\s+([a-zA-Z\s]+?)(?:\?|$|,)",
        r"([a-zA-Z][a-zA-Z\s]+?)\s+(?:location|area)\b",
        r"\b(?:in|at|near)\s+([a-zA-Z][a-zA-Z\s]*?)\s*$",  # "in berhampur lanjipalli" at end
    ]:
        m = re.search(pattern, q, re.IGNORECASE)
        if m:
            phrase = m.group(1).strip()
            if len(phrase) >= 2 and phrase.lower() not in ("sale", "rent", "buy"):
                return phrase
    return None


def _parse_price_value(s: str) -> float | None:
    """Parse '20000', '20k', '20,000', '20 lakh' etc. to a number."""
    s = s.strip().replace(",", "").lower()
    if not s:
        return None
    multiplier = 1.0
    if s.endswith("k") or s.endswith("k."):
        multiplier = 1_000
        s = s.rstrip("k.")
    elif s.endswith("lakh") or s.endswith("lac") or s.endswith("lakhs") or s.endswith("lacs"):
        multiplier = 100_000
        s = re.sub(r"\s*(lakhs?|lacs?)\s*$", "", s).strip()
    try:
        return float(s) * multiplier
    except ValueError:
        return None


def _extract_price_filters(query: str) -> tuple[float | None, float | None]:
    """Extract min_price and max_price from phrases like 'under 20000', 'below 20k', 'over 10 lakh'."""
    q = query
    lower = q.lower()
    min_price = max_price = None
    # Max price: "under 20000", "below 20k", "less than 20000", "max 20000", "within 20000", "up to 20000"
    for pattern in [
        r"(?:under|below|less than|max(?:imum)?|within|up to)\s*[\s:]*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\s*k)?)\s*(?:lakhs?|lacs?)?",
        r"(?:properties?|listings?)\s+(?:under|below)\s+([\d,]+(?:\s*k)?)",
    ]:
        m = re.search(pattern, lower, re.IGNORECASE)
        if m:
            val = _parse_price_value(m.group(1))
            if val is not None:
                max_price = val
                break
    # Min price: "over 20000", "above 20000", "min 20000", "from 20000"
    for pattern in [
        r"(?:over|above|min(?:imum)?|from)\s*[\s:]*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\s*k)?)\s*(?:lakhs?|lacs?)?",
    ]:
        m = re.search(pattern, lower, re.IGNORECASE)
        if m:
            val = _parse_price_value(m.group(1))
            if val is not None:
                min_price = val
                break
    # "between X and Y"
    between = re.search(r"between\s+[\s:]*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\s*k)?)\s+and\s+([\d,]+(?:\s*k)?)", lower, re.IGNORECASE)
    if between:
        lo = _parse_price_value(between.group(1))
        hi = _parse_price_value(between.group(2))
        if lo is not None:
            min_price = lo
        if hi is not None:
            max_price = hi
    return min_price, max_price


def _filters_from_query(query: str) -> dict:
    q = query.lower()
    city = state = locality = listing_type = None
    min_price, max_price = _extract_price_filters(query)
    if "rent" in q or "rental" in q:
        listing_type = "RENT"
    elif "sale" in q or "buy" in q:
        listing_type = "SALE"
    # Extract location so we filter by city/locality (e.g. "berhampur lanjipalli" -> city=berhampur, locality=lanjipalli)
    place = _extract_location_phrase(query)
    if place:
        parts = [p.strip() for p in place.split() if p.strip()]
        if len(parts) >= 2:
            city = parts[0]
            locality = parts[1]
        elif len(parts) == 1:
            city = parts[0]
            locality = parts[0]
    return {
        "city": city,
        "locality": locality,
        "state": state,
        "listing_type": listing_type,
        "min_price": min_price,
        "max_price": max_price,
    }


def get_listing_context_for_query(
    query: str,
    limit: int = 20,
) -> str:
    """Build listing context string for the LLM."""
    filters = _filters_from_query(query)
    # When filtering by location or price, fetch more so we don't miss matches
    has_filters = filters.get("city") or filters.get("locality") or filters.get("min_price") is not None or filters.get("max_price") is not None
    effective_limit = 30 if has_filters else limit
    return build_listing_context(limit=effective_limit, **filters)


def get_listing_context_and_references_for_query(
    query: str,
    limit: int = 20,
) -> tuple[str, list[dict]]:
    """Build listing context and references for the LLM and API response."""
    filters = _filters_from_query(query)
    has_filters = filters.get("city") or filters.get("locality") or filters.get("min_price") is not None or filters.get("max_price") is not None
    effective_limit = 30 if has_filters else limit
    return build_listing_context_and_references(limit=effective_limit, **filters)
