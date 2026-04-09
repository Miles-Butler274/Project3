from django.urls import path
from .views import chat, chat_page

urlpatterns = [
    path("", chat_page),
    path("api/", chat),
]
