import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from config.apps.statistiques.forms import QuestionForm
from config.apps.statistiques.services import (
    execute_intent,
    extract_intent,
    get_analytics_summary,
    get_dashboard_metrics,
)


def chat_view(request):
    metrics = get_dashboard_metrics()
    if request.method == "POST":
        form = QuestionForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"error": "Question invalide."}, status=400)
        intent = extract_intent(form.cleaned_data["question"])
        if intent.get("needs_clarification"):
            return JsonResponse({
                "answer": "Je peux répondre à cette question, mais j’ai besoin de plus de précision sur l’indicateur ou l’année.",
                "table": [],
                "chart": None,
                "metadata": {"fictitious": True, "rows_used": 0, "metrics": metrics},
            })
        result = execute_intent(intent)
        result.setdefault("metadata", {})["metrics"] = metrics
        return JsonResponse(result)

    if request.method == "GET" and request.GET.get("mode") == "analytics":
        region = request.GET.get("region") or None
        year = request.GET.get("year") or None
        if year:
            year = int(year)
        summary = get_analytics_summary(region=region, year=year)
        return JsonResponse({"summary": summary})

    return render(request, "statistiques/chat.html", {"metrics": metrics})
