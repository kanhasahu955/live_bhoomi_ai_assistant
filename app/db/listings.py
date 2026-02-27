"""
Read listings from MongoDB (same DB as Fastify/Prisma).
Prisma MongoDB uses collection name 'Listing' for the Listing model.
"""
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from config import settings


def get_db() -> Database:
    client = MongoClient(settings.MONGO_URL)
    return client[settings.MONGO_DB]


def get_listings_collection() -> Collection:
    return get_db()["Listing"]


def format_listing_for_context(doc: dict[str, Any]) -> str:
    """Turn one listing document into a short text block for RAG context."""
    title = doc.get("title") or "Untitled"
    price = doc.get("price")
    price_str = f"₹{price:,.0f}" if isinstance(price, (int, float)) else str(price)
    city = doc.get("city") or ""
    locality = doc.get("locality") or ""
    state = doc.get("state") or ""
    desc = (doc.get("description") or "")[:200]
    listing_type = doc.get("listingType") or ""
    property_type = doc.get("propertyType") or ""
    beds = doc.get("bedrooms")
    baths = doc.get("bathrooms")
    area = doc.get("area")
    parts = [
        f"Title: {title}",
        f"Price: {price_str}",
        f"Type: {listing_type} / {property_type}",
        f"Location: {locality}, {city}, {state}",
    ]
    if beds is not None:
        parts.append(f"Bedrooms: {beds}")
    if baths is not None:
        parts.append(f"Bathrooms: {baths}")
    if area is not None:
        parts.append(f"Area: {area} sqft")
    if desc:
        parts.append(f"Description: {desc}...")
    return " | ".join(parts)


def fetch_listings(
    limit: int = 25,
    city: str | None = None,
    locality: str | None = None,
    state: str | None = None,
    listing_type: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch listings from MongoDB for RAG context.
    When status is None, returns all non-deleted listings (DRAFT, ACTIVE, etc.).
    """
    coll = get_listings_collection()
    query: dict[str, Any] = {"deletedAt": None}
    if status:
        query["status"] = status
    if city:
        query["city"] = {"$regex": city.strip(), "$options": "i"}
    if locality:
        query["locality"] = {"$regex": locality.strip(), "$options": "i"}
    if state:
        query["state"] = {"$regex": state.strip(), "$options": "i"}
    if listing_type:
        query["listingType"] = listing_type.strip().upper()
    if min_price is not None or max_price is not None:
        price_q: dict[str, Any] = {}
        if min_price is not None:
            price_q["$gte"] = min_price
        if max_price is not None:
            price_q["$lte"] = max_price
        query["price"] = price_q

    cursor = coll.find(query).sort("createdAt", -1).limit(limit)
    return list(cursor)


def doc_to_reference(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a listing document to a reference payload for the API (id, title, price, etc.)."""
    oid = doc.get("_id")
    return {
        "id": str(oid) if oid is not None else "",
        "title": doc.get("title") or "",
        "price": doc.get("price"),
        "city": doc.get("city") or "",
        "locality": doc.get("locality") or "",
        "state": doc.get("state") or "",
        "listingType": doc.get("listingType") or "",
        "propertyType": doc.get("propertyType") or "",
        "bedrooms": doc.get("bedrooms"),
        "bathrooms": doc.get("bathrooms"),
        "area": doc.get("area"),
        "slug": doc.get("slug") or "",
    }


def build_listing_context_and_references(
    limit: int = 20,
    city: str | None = None,
    locality: str | None = None,
    state: str | None = None,
    listing_type: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Fetch listings and return (context string for LLM, references for API response)."""
    docs = fetch_listings(
        limit=limit,
        city=city,
        locality=locality,
        state=state,
        listing_type=listing_type,
        min_price=min_price,
        max_price=max_price,
    )
    if not docs:
        return "No listings found in the database for the current filters.", []
    context = "\n\n".join(format_listing_for_context(d) for d in docs)
    references = [doc_to_reference(d) for d in docs]
    return context, references


def build_listing_context(
    limit: int = 20,
    city: str | None = None,
    locality: str | None = None,
    state: str | None = None,
    listing_type: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
) -> str:
    """Fetch listings and return a single string for the agent prompt."""
    ctx, _ = build_listing_context_and_references(
        limit=limit,
        city=city,
        locality=locality,
        state=state,
        listing_type=listing_type,
        min_price=min_price,
        max_price=max_price,
    )
    return ctx
