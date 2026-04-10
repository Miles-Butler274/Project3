import requests
from django.utils import timezone

from .api import infer_category
from .models import IngestionJob
from .services import upsert_market_from_dict

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"


def _safe_float(value):
    try:
        if value in (None, "", "null"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_probability(item: dict):
    yes_bid = _safe_float(item.get("yes_bid_dollars") or item.get("yes_bid"))
    yes_ask = _safe_float(item.get("yes_ask_dollars") or item.get("yes_ask"))
    last_price = _safe_float(
        item.get("last_price_dollars") or item.get("last_price") or item.get("price")
    )

    if yes_bid is not None and yes_ask is not None:
        return (yes_bid + yes_ask) / 2.0

    if last_price is not None:
        return last_price

    return None


def _extract_volume(item: dict):
    for key in ("volume_fp", "volume", "dollar_volume", "liquidity"):
        value = _safe_float(item.get(key))
        if value is not None:
            return value
    return None


def _build_question(item: dict) -> str:
    ticker = str(item.get("ticker") or "").strip()
    event_title = str(item.get("event_title") or "").strip()
    yes_sub_title = str(item.get("yes_sub_title") or "").strip()
    subtitle = str(item.get("subtitle") or "").strip()
    title = str(item.get("title") or "").strip()

    def clean_leg(text: str) -> str:
        text = text.strip()
        if text.lower().startswith("yes "):
            return text[4:].strip()
        if text.lower().startswith("no "):
            return text[3:].strip()
        return text

    if event_title and yes_sub_title:
        return f"{event_title} — {clean_leg(yes_sub_title)}"
    if event_title and subtitle:
        return f"{event_title} — {subtitle}"
    if event_title:
        return event_title
    if yes_sub_title:
        return clean_leg(yes_sub_title)
    if subtitle:
        return subtitle
    if title and title.lower().count("yes ") <= 1:
        return title
    return ticker


def _build_description(item: dict) -> str:
    parts = []

    for value in [
        item.get("event_sub_title"),
        item.get("event_subtitle"),
        item.get("subtitle"),
        item.get("no_sub_title"),
        item.get("series_ticker"),
        item.get("ticker"),
    ]:
        text = str(value or "").strip()
        if text and text not in parts:
            parts.append(text)

    return " | ".join(parts)


def _infer_kalshi_category(item: dict, question: str, description: str) -> str:
    ticker = str(item.get("ticker") or "").upper()
    event_title = str(item.get("event_title") or "")
    series_ticker = str(item.get("series_ticker") or "")

    combined = " ".join([ticker, event_title, series_ticker, question, description]).strip()

    # First use Kalshi-specific ticker hints
    if "SPORT" in ticker or "NBA" in ticker or "NFL" in ticker or "MLB" in ticker or "SOCCER" in ticker:
        return "sports"

    if "CRYPTO" in ticker or "BTC" in ticker or "ETH" in ticker:
        return "crypto"

    if "ELECTION" in ticker or "POLITIC" in ticker or "PRES" in ticker or "SENATE" in ticker:
        return "politics"

    if "ECON" in ticker or "RATE" in ticker or "INFLATION" in ticker or "GDP" in ticker:
        return "economics"

    # Cross-category and multigame markets are often still sports in your dataset
    if "CROSSCATEGORY" in ticker or "MULTIGAME" in ticker or "MULTI" in ticker:
        guessed = infer_category(combined, description)
        if guessed != "general":
            return guessed

        sports_words = [
            "points", "rebounds", "assists", "goals", "runs scored",
            "lebron", "durant", "brunson", "adebayo", "tatum",
            "warriors", "boston", "chicago", "indiana", "toronto",
        ]
        text = combined.lower()
        if any(word in text for word in sports_words):
            return "sports"

        return "general"

    # Fallback to your existing keyword classifier
    return infer_category(combined, description)


def _api_market_url(ticker: str) -> str:
    ticker = str(ticker or "").strip()
    if not ticker:
        return ""
    return f"{KALSHI_BASE}/markets/{ticker}"


def _kalshi_to_market(item: dict) -> dict:
    ticker = str(item.get("ticker") or "").strip()
    if not ticker:
        raise ValueError("Missing Kalshi ticker")

    question = _build_question(item)
    description = _build_description(item)
    category = _infer_kalshi_category(item, question, description)
    status = str(item.get("status") or "").strip().lower()

    return {
        "market_id": f"kalshi_{ticker}",
        "question": question,
        "description": description,
        "category": category,
        "probability": _extract_probability(item),
        "volume": _extract_volume(item),
        "url": _api_market_url(ticker),
        "is_active": status in {"open", "active", "initialized", "paused"},
    }


def ingest_kalshi_markets(limit: int = 100):
    url = f"{KALSHI_BASE}/markets"
    params = {
        "limit": min(max(int(limit), 1), 1000),
        "status": "open",
    }

    job = IngestionJob.objects.create(
        method="api",
        status="running",
        source_name="Kalshi API",
        details=f"GET {url} with {params}",
    )

    created_count = 0
    updated_count = 0

    try:
        response = requests.get(
            url,
            params=params,
            timeout=20,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()

        data = response.json()
        markets = data.get("markets", [])
        if not isinstance(markets, list):
            raise ValueError("Expected Kalshi response with a 'markets' list")

        for item in markets[:limit]:
            ticker = str(item.get("ticker") or "").strip()
            if not ticker:
                continue

            _, created = upsert_market_from_dict(_kalshi_to_market(item))
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
