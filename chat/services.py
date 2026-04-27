import math
import re
from collections import Counter

from markets.embeddings import cosine_similarity, embed_query
from markets.models import DocumentChunk, Market
from .llm import generate_grounded_completion


STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else",
    "what", "which", "who", "why", "how", "when", "where",
    "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "for", "with", "about", "from",
    "me", "my", "give", "show", "tell", "please",
    "prediction", "predictions", "market", "markets",
    "will", "would", "could", "should", "can", "does", "do",
    "this", "that", "these", "those",
}


QUERY_CATEGORY_HINTS = {
    "sports": [
        "sport", "sports", "soccer", "football", "fifa", "nba", "nfl",
        "mlb", "tennis", "olympics", "world cup", "uefa",
    ],
    "politics": [
        "politics", "political", "election", "president", "senate",
        "congress", "campaign", "vote", "voting", "trump", "biden",
    ],
    "crypto": [
        "crypto", "bitcoin", "btc", "ethereum", "eth", "solana",
        "token", "blockchain",
    ],
    "economics": [
        "economy", "economic", "fed", "inflation", "gdp", "tariff",
        "recession", "interest rate",
    ],
    "entertainment": [
        "movie", "film", "tv", "television", "oscar", "grammy",
        "celebrity", "entertainment",
    ],
}


def tokenize(text: str) -> list[str]:
    if not text:
        return []

    words = re.findall(r"[a-zA-Z0-9']+", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def score_text(query_tokens: list[str], text: str) -> int:
    if not text:
        return 0

    counts = Counter(tokenize(text))
    score = 0
    for token in query_tokens:
        score += counts[token]
    return score


def normalize_keyword_score(score: int) -> float:
    if score <= 0:
        return 0.0
    return min(score / 8.0, 1.0)


def infer_query_categories(query: str) -> list[str]:
    lowered = query.lower()
    matched = []

    for category, hints in QUERY_CATEGORY_HINTS.items():
        if any(hint in lowered for hint in hints):
            matched.append(category)

    return matched

def classify_query_intent(query: str) -> str:

    text = query.lower()
    if any(word in text for word in ["how", "why", "explain", "meaning", "reason", "break down"]):
        return "explanation"

    if any(word in text for word in ["imagine", "what if", "scenario", "predict", "creative", "suppose"]):
        return "creative"

    if any(word in text for word in ["what is", "who is", "when", "current price", "probability of", "odds"]):
        return "factual"

    return "general"

def format_market_context(market: Market) -> str:
    return f"""
Question: {market.question}
Description: {market.description or "N/A"}
Category: {market.category or "N/A"}
Probability: {market.probability if market.probability is not None else "N/A"}
Volume: {market.volume if market.volume is not None else "N/A"}
URL: {market.url or "N/A"}
""".strip()


def market_volume_boost(volume) -> float:
    if volume is None:
        return 0.0
    return min(math.log10(max(volume, 1.0)) / 10.0, 0.08)


def dedupe_sources(items: list[dict], key_fields: tuple[str, ...]) -> list[dict]:
    seen = set()
    out = []

    for item in items:
        key = tuple(item.get(field) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)

    return out


def retrieve_context(
    query: str,
    top_k_markets: int = 6,
    top_k_chunks: int = 8,
) -> dict:
    query_tokens = tokenize(query)
    query_categories = infer_query_categories(query)
    query_embedding = embed_query(query)

    market_results = []
    for market in Market.objects.filter(is_active=True):
        combined = f"{market.question}\n{market.description}\n{market.category}"
        keyword_score = normalize_keyword_score(score_text(query_tokens, combined))
        semantic_score = cosine_similarity(query_embedding, market.embedding)

        category_boost = 0.0
        if market.category and market.category.lower() in query_categories:
            category_boost = 0.06

        final_score = (
            semantic_score * 0.72
            + keyword_score * 0.18
            + category_boost
            + market_volume_boost(market.volume)
        )

        if final_score <= 0.12:
            continue

        market_results.append(
            {
                "score": final_score,
                "title": market.question,
                "source": market.url or market.question,
                "url": market.url or "",
                "content": format_market_context(market),
            }
        )

    chunk_results = []
    for chunk in DocumentChunk.objects.select_related("document").all():
        keyword_score = normalize_keyword_score(score_text(query_tokens, chunk.text))
        semantic_score = cosine_similarity(query_embedding, chunk.embedding)

        final_score = semantic_score * 0.80 + keyword_score * 0.20
        if final_score <= 0.10:
            continue

        chunk_results.append(
            {
                "score": final_score,
                "title": chunk.document.title,
                "source": chunk.document.source_url or chunk.document.title,
                "url": chunk.document.source_url or "",
                "content": chunk.text,
            }
        )

    market_results.sort(key=lambda x: x["score"], reverse=True)
    chunk_results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "markets": dedupe_sources(market_results, ("source", "title"))[:top_k_markets],
        "docs": dedupe_sources(chunk_results, ("source", "content"))[:top_k_chunks],
    }


def build_prompt(query: str, retrieved: dict, intent: str = "general") -> str:
    market_context = "\n\n".join(
        f"[MARKET {i + 1}]\n{m['content']}"
        for i, m in enumerate(retrieved["markets"])
    )

    doc_context = "\n\n".join(
        f"[DOC {i + 1}] {d['title']}\n{d['content']}"
        for i, d in enumerate(retrieved["docs"])
    )

    base_instructions = """
You are a prediction market analysis assistant.
Use ONLY the retrieved context below.
Do not invent facts.
Do not guarantee outcomes.
If the evidence is weak or incomplete, say so clearly.
Compare markets only if multiple relevant markets are present.
    """.strip()

    intent_rules = {
        "factual": "BEHAVIOR: The user wants a direct factual lookup. Be extremely concise. State the probabilities, volume, and data points clearly without unnecessary elaboration.",
        "explanation": "BEHAVIOR: The user is asking for an explanation. Break down the reasons, mechanics, or historical context behind the market odds step-by-step.",
        "creative": "BEHAVIOR: The user is exploring hypotheticals. While staying grounded in the provided facts, creatively explore future implications or alternative scenarios related to the query.",
        "general": "BEHAVIOR: Focus on grounded explanation, useful tips, and highlighting uncertainty."
    }

    specific_behavior = intent_rules.get(intent, intent_rules["general"])

    return f"""
{base_instructions}
{specific_behavior}

Return ONLY valid JSON in this exact shape:
{{
  "answer": "short grounded answer formatted according to BEHAVIOR rules",
  "key_insights": ["insight 1", "insight 2"],
  "tips": ["tip 1", "tip 2"],
  "limitations": ["limit 1", "limit 2"]
}}

User question:
{query}

Retrieved market context:
{market_context if market_context else "No relevant markets found."}

Retrieved document context:
{doc_context if doc_context else "No relevant documents found."}
""".strip()

def generate_rag_answer(query: str) -> dict:
    retrieved = retrieve_context(query)

    if not retrieved["markets"] and not retrieved["docs"]:
        return {
            "answer": "I could not find relevant information in the ingested dataset.",
            "key_insights": [],
            "tips": [],
            "limitations": ["No relevant market or document context was retrieved."],
            "sources": [],
        }

    intent = classify_query_intent(query)

    prompt = build_prompt(query, retrieved, intent)

    llm_result = generate_grounded_completion(prompt)

    sources = []
    seen = set()

    for item in retrieved["markets"]:
        url = item.get("url") or ""
        label = item.get("title") or url or "Market source"
        key = ("market", url, label)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "type": "market",
                "label": label,
                "url": url,
            }
        )

    for item in retrieved["docs"]:
        url = item.get("url") or ""
        label = item.get("title") or "Document source"
        key = ("document", url, label)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "type": "document",
                "label": label,
                "url": url,
            }
        )

    return {
        "answer": llm_result.get("answer", "").strip(),
        "key_insights": llm_result.get("key_insights", []),
        "tips": llm_result.get("tips", []),
        "limitations": llm_result.get("limitations", []),
        "sources": sources,
        "intent": intent,
    }
