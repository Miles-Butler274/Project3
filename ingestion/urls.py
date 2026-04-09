from django.urls import path
from . import views

app_name = "ingestion"

urlpatterns = [
    path("", views.ingestion_home, name="home"),
    path("api/", views.ingest_api_view, name="api"),
    path("text/", views.ingest_text_view, name="text"),
    path("clear/", views.clear_knowledge_base_view, name="clear"),
]
