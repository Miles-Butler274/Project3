import re
from collections import Counter

from markets.models import Market, SourceDocument
from .llm import generate_grounded_completion


STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "else",
    "what", "which", "who", "why", "how", "when", "where",
    "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "for", "with", "about", "from",
    "me", "my", "give", "show", "tell", "please",
    "prediction", "predictions", "market", "markets",
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


def split_into_chunks(text: str, chunk_size: int = 800) -> list[str]:
    if not text:
        return []

    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start = end

    return [c for c in chunks if c]


def infer_query_categories(query: str) -> list[str]:
    lowered = query.lower()
    matched = []

    for category, hints in QUERY_CATEGORY_HINTS.items():
        if any(hint in lowered for hint in hints):
            matched.append(category)

    return matched


def format_market_context(market: Market) -> str:
    return f"""
Question: {market.question}
Description: {market.description or "N/A"}
Category: {market.category or "N/A"}
Probability: {market.probability if market.probability is not None else "N/A"}
Volume: {market.volume if market.volume is not None else "N/A"}
URL: {market.url or "N/A"}
""".strip()

def dedupe_by_source(items: list[dict]) -> list[dict]:
    seen = set()
    out = []

    for item in items:
        key = (item["source"], item["title"])
        if key in seen:
            continue

        seen.add(key)
        out.append(item)

    return out


def retrieve_context(query: str, top_k_markets: int = 10, top_k_docs: int = 6) -> dict:
    lowered = query.lower()
    query_tokens = tokenize(query)
    query_categories = infer_query_categories(query)

    market_results = []
    doc_results = []

    # structured retrieval for custom user stories
    if "popular" in lowered:
        for market in Market.objects.filter(is_active=True).order_by("-volume")[:10]:
            market_results.append({
                "score": 1000,
                "title": market.question,
                "source": market.url or market.question,
                "content": format_market_context(market),
            })

    if "underrated" in lowered or "underreviewed" in lowered or "new" in lowered:
        for market in Market.objects.filter(is_active=True).order_by("volume", "-updated_at")[:10]:
            market_results.append({
                "score": 900,
                "title": market.question,
                "source": market.url or market.question,
                "content": format_market_context(market),
            })

    # general market retrieval
    for market in Market.objects.filter(is_active=True):
        combined = f"{market.question}\n{market.description}\n{market.category}"
        score = score_text(query_tokens, combined)

        if market.category and market.category.lower() in query_categories:
            score += 8

        if score > 0:
            market_results.append({
                "score": score,
                "title": market.question,
                "source": market.url or market.question,
                "content": format_market_context(market),
            })

    # document retrieval
    for doc in SourceDocument.objects.all():
        full_text = doc.cleaned_text or doc.raw_text
        for chunk in split_into_chunks(full_text):
            score = score_text(query_tokens, chunk)

            # small category boost if chunk contains related concept hints
            for category in query_categories:
                if category in chunk.lower():
                    score += 2

            if score > 0:
                doc_results.append({
                    "score": score,
                    "title": doc.title,
                    "source": doc.source_url or doc.title,
                    "content": chunk,
                })

    market_results.sort(key=lambda x: x["score"], reverse=True)
    doc_results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "markets": dedupe_by_source(market_results)[:top_k_markets],
        "docs": dedupe_by_source(doc_results)[:top_k_docs],
    }


def build_prompt(query: str, retrieved: dict) -> str:
    market_context = "\n\n".join(
        [f"[MARKET {i+1}]\n{m['content']}" for i, m in enumerate(retrieved["markets"])]
    )
    doc_context = "\n\n".join(
        [f"[DOC {i+1}] {d['title']}\n{d['content']}" for i, d in enumerate(retrieved["docs"])]
    )

    return f"""
You are a prediction market analysis assistant.

Use ONLY the retrieved context below.
Do not invent facts not present in the context.
Do not guarantee outcomes.
Be useful, direct, and grounded.

When answering:
- explain what seems most relevant
- give practical tips on what the user should watch
- mention uncertainty, limitations, or missing information
- if the data is weak, say so clearly

User question:
{query}

Retrieved market context:
{market_context if market_context else "No relevant markets found."}

Retrieved document context:
{doc_context if doc_context else "No relevant documents found."}

Output format:
1. Direct answer
2. Why it matters
3. Tips / what to watch
4. Limits of the available data
""".strip()


def generate_rag_answer(query: str) -> dict:
    retrieved = retrieve_context(query)

    if not retrieved["markets"] and not retrieved["docs"]:
        return {
            "answer": "I could not find relevant information in the ingested dataset.",
            "sources": [],
        }

    prompt = build_prompt(query, retrieved)
    answer = generate_grounded_completion(prompt)

    sources = []
    for item in retrieved["markets"] + retrieved["docs"]:
        if item["source"] and item["source"] not in sources:
            sources.append(item["source"])

    return {
        "answer": answer,
        "sources": sources,
    }
