from django.contrib import admin
from .models import UsageLog

@admin.register(UsageLog)
class UsageLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'intent_detected', 'user_rating', 'query_snippet', 'latency_ms', 'is_successful')
    list_filter = ('is_successful', 'user_rating', 'intent_detected', 'created_at')

    search_fields = ('query', 'response')
    readonly_fields = ('query', 'response', 'intent_detected', 'user_rating', 'latency_ms', 'is_successful', 'created_at')

    def query_snippet(self, obj):
        return obj.query[:75] + '...' if len(obj.query) > 75 else obj.query
    query_snippet.short_description = "Query"

    def has_add_permission(self, request):
        return False
