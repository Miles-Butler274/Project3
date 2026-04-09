from django.utils import timezone

from markets.models import Market, SourceDocument
from .utils import clean_text, safe_float


def ingest_text_document(
    title: str,
    raw_text: str,
    source_type: str = "text",
    source_url: str = "",
):
    cleaned = clean_text(raw_text)

    return SourceDocument.objects.create(
        title=title,
        source_type=source_type,
        source_url=source_url,
        raw_text=raw_text,
        cleaned_text=cleaned,
    )


def upsert_market_from_dict(data: dict):
    market_id = str(data.get("market_id") or data.get("id") or "").strip()
    if not market_id:
        raise ValueError("Missing market_id")

    defaults = {
        "question": clean_text(data.get("question", "")),
        "description": clean_text(data.get("description", "")),
        "category": clean_text(data.get("category", "")),
        "probability": safe_float(data.get("probability")),
        "volume": safe_float(data.get("volume")),
        "url": data.get("url", "") or "",
        "is_active": bool(data.get("is_active", True)),
        "last_ingested_at": timezone.now(),
    }

    obj, created = Market.objects.update_or_create(
        market_id=market_id,
        defaults=defaults,
    )
    return obj, created


def clear_knowledge_base():
    deleted_docs = SourceDocument.objects.count()
    deleted_markets = Market.objects.count()

    SourceDocument.objects.all().delete()
    Market.objects.all().delete()

    return {
        "deleted_documents": deleted_docs,
        "deleted_markets": deleted_markets,
    }
