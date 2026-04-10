import json

import requests
from django.utils import timezone

from .models import IngestionJob
from .services import upsert_market_from_dict
from .classifier import classify_market_category_llm

GAMMA_BASE = "https://gamma-api.polymarket.com"



import re
from .classifier import classify_market_category_llm


def infer_category(question: str, description: str = "", ticker: str = "") -> str:
    text = f"{question} {description} {ticker}".lower()

    text = re.sub(r"[^a-z0-9\s\.\-\+]", " ", text)
    text = re.sub(r"\s+", " ", text)

    def has_any(words):
        return any(word in text for word in words)

    # ---- SPORTS (expanded heavily) ----
    if has_any([
        # leagues
        "nba", "nfl", "mlb", "nhl", "ufc", "mma",
        "premier league", "la liga", "serie a", "bundesliga",
        "champions league", "uefa", "fifa", "world cup",

        # general sports terms
        "points", "rebounds", "assists", "yards", "touchdown",
        "goals", "runs scored", "strikeouts", "innings",
        "match", "game", "final score", "win by", "over", "under",

        # common player names (important for Kalshi)
        "lebron", "durant", "tatum", "curry", "giannis",
        "brunson", "adebayo", "mitchell", "anthony davis",
        "embiid", "luka", "jokic",

        # teams / cities (very important)
        "boston", "chicago", "miami", "golden state",
        "lakers", "warriors", "celtics", "knicks",
        "dallas", "phoenix", "milwaukee", "toronto",
    ]):
        return "sports"

    # ---- POLITICS ----
    if has_any([
        "election", "president", "senate", "congress",
        "vote", "voting", "poll", "approval rating",
        "democrat", "republican", "campaign",
        "primary", "runoff", "ballot",

        # people
        "trump", "biden", "desantis", "kamala",
        "harris", "rfk", "kennedy",

        # institutions
        "white house", "supreme court", "governor",
    ]):
        return "politics"

    # ---- CRYPTO ----
    if has_any([
        "bitcoin", "btc", "ethereum", "eth", "solana", "sol",
        "doge", "dogecoin", "xrp", "cardano",
        "crypto", "token", "blockchain", "defi",
        "staking", "gas fees", "hashrate",
    ]):
        return "crypto"

    # ---- ECONOMICS / FINANCE ----
    if has_any([
        "inflation", "cpi", "gdp", "fed", "fomc",
        "interest rate", "rate hike", "rate cut",
        "recession", "unemployment",
        "stocks", "s&p", "nasdaq", "dow",
        "bond", "yield", "treasury",
        "tariff", "trade deficit",
        "housing market", "mortgage",
    ]):
        return "economics"

    # ---- ENTERTAINMENT ----
    if has_any([
        "movie", "film", "box office", "opening weekend",
        "tv", "television", "series", "episode",
        "oscar", "academy awards", "grammy",
        "emmy", "celebrity", "netflix",
        "streaming", "show",
    ]):
        return "entertainment"

    # ---- EXTRA: WEATHER / RANDOM / EVENTS ----
    if has_any([
        "hurricane", "storm", "rainfall", "temperature",
        "earthquake", "wildfire",
    ]):
        return "weather"

    # ---- EXTRA: SCIENCE / TECH ----
    if has_any([
        "ai", "artificial intelligence", "openai", "gpt",
        "spacex", "nasa", "rocket", "launch",
        "quantum", "chip", "semiconductor",
    ]):
        return "science"

    return classify_market_category_llm(
        question=question,
        description=description,
        ticker=ticker,
    )

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
                "category": infer_category(
                    question,
                    description,
                    str(item.get("id") or ""),
                ),
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
