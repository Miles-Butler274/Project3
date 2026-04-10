from django.utils import timezone

from markets.embeddings import embed_text
from markets.models import DocumentChunk, Market, SourceDocument

from .utils import clean_text, safe_float, split_text_into_chunks

import time
import requests

from markets.embeddings import embed_text as _embed_text


def embed_text_with_backoff(text: str, retries: int = 5):
    delay = 1.0

    for attempt in range(retries):
        try:
            return _embed_text(text)
        except Exception as exc:
            msg = str(exc)
            if "429" not in msg or attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2

def ingest_text_document(
    title: str,
    raw_text: str,
    source_type: str = "text",
    source_url: str = "",
):
    cleaned = clean_text(raw_text)

    doc = SourceDocument.objects.create(
        title=title,
        source_type=source_type,
        source_url=source_url,
        raw_text=raw_text,
        cleaned_text=cleaned,
        embedding=embed_text_with_backoff(f"{title}\n{cleaned}"),
    )

    chunks = split_text_into_chunks(cleaned or raw_text)

    chunk_objects = []
    for idx, chunk_text in enumerate(chunks):
        chunk_objects.append(
            DocumentChunk(
                document=doc,
                chunk_index=idx,
                text=chunk_text,
                embedding=embed_text(f"{title}\n{chunk_text}"),
            )
        )

    if chunk_objects:
        DocumentChunk.objects.bulk_create(chunk_objects)

    return doc


def upsert_market_from_dict(data: dict):
    market_id = str(data.get("market_id") or data.get("id") or "").strip()
    if not market_id:
        raise ValueError("Missing market_id")

    question = clean_text(data.get("question", ""))
    description = clean_text(data.get("description", ""))

    embedding_input = f"{question}\n{description}"
    embedding = embed_text(embedding_input)

    defaults = {
        "question": question,
        "description": description,
        "category": clean_text(data.get("category", "")),
        "probability": safe_float(data.get("probability")),
        "volume": safe_float(data.get("volume")),
        "url": data.get("url", "") or "",
        "is_active": bool(data.get("is_active", True)),
        "last_ingested_at": timezone.now(),
        "embedding": embedding,
    }

    obj, created = Market.objects.update_or_create(
        market_id=market_id,
        defaults=defaults,
    )
    return obj, created


def clear_knowledge_base():
    deleted_chunks = DocumentChunk.objects.count()
    deleted_docs = SourceDocument.objects.count()
    deleted_markets = Market.objects.count()

    DocumentChunk.objects.all().delete()
    SourceDocument.objects.all().delete()
    Market.objects.all().delete()

    return {
        "deleted_chunks": deleted_chunks,
        "deleted_documents": deleted_docs,
        "deleted_markets": deleted_markets,
    }
