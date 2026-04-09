from django.db import models


class Market(models.Model):
    market_id = models.CharField(max_length=128, unique=True)
    question = models.TextField()
    description = models.TextField(blank=True)
    category = models.CharField(max_length=128, blank=True)
    probability = models.FloatField(null=True, blank=True)
    volume = models.FloatField(null=True, blank=True)
    url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_ingested_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.question[:80]


class SourceDocument(models.Model):
    SOURCE_TYPES = [
        ("api", "API"),
        ("file", "File"),
        ("text", "Text"),
    ]

    title = models.CharField(max_length=255)
    source_type = models.CharField(max_length=32, choices=SOURCE_TYPES)
    source_url = models.URLField(blank=True)
    raw_text = models.TextField()
    cleaned_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
