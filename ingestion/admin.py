from django.contrib import admin
from .models import IngestionJob


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "method",
        "status",
        "source_name",
        "records_created",
        "records_updated",
        "started_at",
        "finished_at",
    )
    search_fields = ("source_name", "details", "error_message")
    list_filter = ("method", "status")
