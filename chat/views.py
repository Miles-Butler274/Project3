import time
import json
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .services import generate_rag_answer
from analytics.models import UsageLog
from markets.models import Market


def chat_page(request):
    trending_markets = Market.objects.filter(is_active=True).order_by('-volume')[:5]

    return render(request, "chat.html", {"trending_markets": trending_markets})


def chat(request):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse(
            {
                "answer": "Ask something about prediction markets.",
                "key_insights": [],
                "tips": [],
                "limitations": [],
                "sources": [],
            }
        )
    start_time = time.time()

    try:
        result = generate_rag_answer(query)

        latency = (time.time() - start_time) * 1000

        usage_log = UsageLog.objects.create(
            query=query,
            response=result.get("answer", "No answer generated."),
            intent_detected=result.get("intent", "unknown"),
            latency_ms=latency,
            is_successful=True
        )

        result["log_id"] = usage_log.id

        return JsonResponse(result)

    except Exception as exc:
        latency = (time.time() - start_time) * 1000

        error_log = UsageLog.objects.create(
            query=query,
            response=f"ERROR: {str(exc)}",
            latency_ms=latency,
            is_successful=False
        )

        return JsonResponse(
            {
                "answer": f"Chat generation failed: {exc}",
                "key_insights": [],
                "tips": [],
                "limitations": ["The server hit an exception while generating the response."],
                "sources": [],
                "log_id": error_log.id
            },
            status=500,
        )

@csrf_exempt
def rate_answer(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            log_id = data.get("log_id")
            rating = data.get("rating")

            if log_id and rating in ['up', 'down']:
                usage_log = UsageLog.objects.get(id=log_id)
                usage_log.user_rating = rating
                usage_log.save(update_fields=['user_rating'])
                return JsonResponse({"status": "success"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Invalid request"}, status=400)
