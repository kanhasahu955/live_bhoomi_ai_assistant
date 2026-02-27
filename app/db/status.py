"""
Database status: connection check, database name, list of collections with document counts.
"""
from typing import Any

from config import settings
from app.db.listings import get_db, doc_to_reference


def get_db_status() -> dict[str, Any]:
    """
    Return connection status, database name, and list of collections with counts.
    On failure returns connected=False and error message.
    """
    try:
        db = get_db()
        db_name = db.name
        # Ping to verify connection
        db.client.admin.command("ping")
        collection_names = db.list_collection_names()
        collections = []
        listing_sample: list[dict[str, Any]] = []
        for name in sorted(collection_names):
            coll = db[name]
            try:
                count = coll.estimated_document_count()
            except Exception:
                count = coll.count_documents({})
            collections.append({"name": name, "count": count})
            # Sample from Listing for UI preview
            if name == "Listing" and count > 0:
                for doc in coll.find({}).sort("_id", -1).limit(5):
                    listing_sample.append(doc_to_reference(doc))
        return {
            "connected": True,
            "database": db_name,
            "collections": collections,
            "listingSample": listing_sample,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "connected": False,
            "database": getattr(settings, "MONGO_DB", ""),
            "collections": [],
            "listingSample": [],
            "error": str(e),
        }
