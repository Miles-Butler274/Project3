import json

import requests
from django.utils import timezone

from .models import IngestionJob
from .services import upsert_market_from_dict

GAMMA_BASE = "https://gamma-api.polymarket.com"


def infer_category(question: str, description: str = "") -> str:
    text = f"{question} {description}".lower()

    if any(
        word in text
        for word in [
            "fifa",
            "soccer",
            "football",
            "nba",
            "nfl",
            "mlb",
            "tennis",
            "olympics",
            "world cup",
            "uefa",
            "champions league",
            "sports",
        ]
    ):
        return "sports"

    if any(
        word in text
        for word in [
            "election",
            "president",
            "senate",
            "congress",
            "campaign",
            "vote",
            "voting",
            "democrat",
            "republican",
            "politics",
            "trump",
            "biden",
        ]
    ):
        return "politics"

    if any(
        word in text
        for word in [
            "bitcoin",
            "btc",
            "ethereum",
            "eth",
            "solana",
            "crypto",
            "token",
            "blockchain",
        ]
    ):
        return "crypto"

    if any(
        word in text
        for word in [
            "fed",
            "inflation",
            "gdp",
            "tariff",
            "recession",
            "economy",
            "interest rate",
            "economic",
        ]
    ):
        return "economics"

    if any(
        word in text
        for word in [
            "movie",
            "film",
            "tv",
            "television",
            "oscar",
            "grammy",
            "celebrity",
            "entertainment",
        ]
    ):
        return "entertainment"

    return "general"


def ingest_polymarket_markets(limit: int = 100, active: bool = True, closed: bool = False):
    url = f"{GAMMA_BASE}/markets"
    params = {
        "limit": limit,
        "active": str(active).lower(),
        "closed": str(closed).lower(),
    }

    job = IngestionJob.objects.create(
        method="api",
        status="running",
        source_name="Polymarket Gamma API",
        details=f"GET {url} with {params}",
    )

    created_count = 0
    updated_count = 0

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        items = response.json()

        if not isinstance(items, list):
            raise ValueError("Expected a list from Polymarket /markets endpoint")

        for item in items:
            question = item.get("question") or ""
            description = item.get("description") or ""

            market_data = {
                "market_id": item.get("id"),
                "question": question,
                "description": description,
                "category": infer_category(question, description),
                "probability": _extract_probability(item),
                "volume": _safe_float(item.get("volume")),
                "url": item.get("url") or "",
                "is_active": item.get("active", True),
            }

            _, created = upsert_market_from_dict(market_data)
            if created:
                created_count += 1
            else:
                updated_count += 1

        job.status = "success"
        job.records_created = created_count
        job.records_updated = updated_count
        job.finished_at = timezone.now()
        job.save()

        return job

    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = timezone.now()
        job.save()
        raise


def _safe_float(value):
    try:
        if value in (None, "", "null"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_probability(item: dict):
    outcomes = item.get("outcomes")
    prices = item.get("outcomePrices")

    try:
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        if isinstance(prices, str):
            prices = json.loads(prices)

        if isinstance(outcomes, list) and isinstance(prices, list):
            for outcome, price in zip(outcomes, prices):
                if str(outcome).strip().lower() == "yes":
                    return _safe_float(price)

            if prices:
                return _safe_float(prices[0])
    except Exception:
        pass

    return _safe_float(item.get("probability"))
