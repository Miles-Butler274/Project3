from django.urls import path
from .views import chat, chat_page, rate_answer

urlpatterns = [
    path("", chat_page),
    path("api/", chat),
    path("api/rate/", rate_answer),
]
