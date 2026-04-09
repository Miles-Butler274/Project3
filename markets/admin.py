from django.contrib import admin
from .models import Market, SourceDocument


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ("market_id", "question", "probability", "volume", "is_active", "last_ingested_at")
    search_fields = ("market_id", "question", "description", "category")
    list_filter = ("is_active", "category")


@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "source_type", "created_at")
    search_fields = ("title", "raw_text", "cleaned_text")
    list_filter = ("source_type",)
