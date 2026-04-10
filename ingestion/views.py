from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from markets.models import DocumentChunk, Market, SourceDocument
from .api import ingest_polymarket_markets
from .forms import TextIngestionForm
from .models import IngestionJob
from .services import clear_knowledge_base, ingest_text_document
from .kalshi import ingest_kalshi_markets


def ingestion_home(request):
    return render(
        request,
        "ingestion/home.html",
        {
            "text_form": TextIngestionForm(),
            "jobs": IngestionJob.objects.order_by("-started_at")[:20],
            "market_count": Market.objects.count(),
            "document_count": SourceDocument.objects.count(),
            "chunk_count": DocumentChunk.objects.count(),
            "active_market_count": Market.objects.filter(is_active=True).count(),
        },
    )


def ingest_api_view(request):
    if request.method != "POST":
        return redirect("ingestion:home")

    try:
        ingest_polymarket_markets(limit=100, active=True, closed=False)
        messages.success(request, "Polymarket markets ingested successfully.")
    except Exception as exc:
        messages.error(request, f"Polymarket ingestion failed: {exc}")

    return redirect("ingestion:home")


def ingest_text_view(request):
    if request.method != "POST":
        return redirect("ingestion:home")

    form = TextIngestionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid text submission.")
        return redirect("ingestion:home")

    title = form.cleaned_data["title"]
    text = form.cleaned_data["text"]

    job = IngestionJob.objects.create(
        method="text",
        status="running",
        source_name=title,
    )

    try:
        ingest_text_document(
            title=title,
            raw_text=text,
            source_type="text",
        )
        job.status = "success"
        job.records_created = 1
        job.finished_at = timezone.now()
        job.save()
        messages.success(request, "Text document ingested successfully.")
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = timezone.now()
        job.save()
        messages.error(request, f"Text ingestion failed: {exc}")

    return redirect("ingestion:home")


def clear_knowledge_base_view(request):
    if request.method != "POST":
        return redirect("ingestion:home")

    job = IngestionJob.objects.create(
        method="clear",
        status="running",
        source_name="manual clear",
    )

    try:
        result = clear_knowledge_base()
        job.status = "success"
        job.details = (
            f"Deleted {result['deleted_markets']} markets, "
            f"{result['deleted_documents']} documents, and "
            f"{result['deleted_chunks']} chunks."
        )
        job.finished_at = timezone.now()
        job.save()
        messages.success(request, job.details)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = timezone.now()
        job.save()
        messages.error(request, f"Clear failed: {exc}")

    return redirect("ingestion:home")

def ingest_kalshi_view(request):
    if request.method != "POST":
        return redirect("ingestion:home")

    try:
        job = ingest_kalshi_markets(limit=100)
        total = (job.records_created or 0) + (job.records_updated or 0)

        if total == 0:
            messages.warning(
                request,
                "Kalshi request completed, but no markets were saved."
            )
        else:
            messages.success(
                request,
                f"Kalshi markets ingested successfully. "
                f"Created: {job.records_created}, updated: {job.records_updated}."
            )
    except Exception as exc:
        messages.error(request, f"Kalshi ingestion failed: {exc}")

    return redirect("ingestion:home")
