from django.db import models


class IngestionJob(models.Model):
    METHOD_CHOICES = [
        ("api", "API"),
        ("file", "File"),
        ("text", "Text"),
        ("reload", "Reload"),
        ("clear", "Clear"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    method = models.CharField(max_length=32, choices=METHOD_CHOICES)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending")
    source_name = models.CharField(max_length=255, blank=True)
    details = models.TextField(blank=True)
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.method} - {self.status} - {self.started_at}"
