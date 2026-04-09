from django.http import JsonResponse
from django.shortcuts import render

from .services import generate_rag_answer


def chat_page(request):
    return render(request, "chat.html")


def chat(request):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({
            "answer": "Ask something about prediction markets.",
            "sources": [],
        })

    try:
        result = generate_rag_answer(query)
        return JsonResponse(result)
    except Exception as exc:
        return JsonResponse(
            {
                "answer": f"Chat generation failed: {exc}",
                "sources": [],
            },
            status=500,
        )
