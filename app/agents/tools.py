"""
Tools for the listing agent (reference: agentic_rag_contracts).
"""
from app.db.listings import fetch_listings, build_listing_context


def search_listings(
    city: str | None = None,
    locality: str | None = None,
    state: str | None = None,
    listing_type: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 15,
) -> str:
    """Fetch listings from DB and return formatted context."""
    return build_listing_context(
        limit=limit,
        city=city,
        locality=locality,
        state=state,
        listing_type=listing_type,
        min_price=min_price,
        max_price=max_price,
    )


def get_listing_stats() -> str:
    """Return a short summary of listing counts (optional)."""
    docs = fetch_listings(limit=100, status="ACTIVE")
    total = len(docs)
    by_city: dict[str, int] = {}
    for d in docs:
        c = (d.get("city") or "Unknown").strip()
        by_city[c] = by_city.get(c, 0) + 1
    lines = [f"Total active listings in context: {total}"]
    for c, n in sorted(by_city.items(), key=lambda x: -x[1])[:5]:
        lines.append(f"  {c}: {n}")
    return "\n".join(lines)
