import json
import os

import google.generativeai as genai

ALLOWED_CATEGORIES = [
    "sports",
    "politics",
    "crypto",
    "economics",
    "entertainment",
    "weather",
    "science",
    "general",
]

def classify_market_category_llm(question: str, description: str = "", ticker: str = "") -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "general"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
Classify this prediction market into exactly one category.

Allowed categories:
- sports
- politics
- crypto
- economics
- entertainment
- weather
- science
- general

Return JSON only in this format:
{{"category": "<one of the allowed categories>"}}

Ticker: {ticker}
Question: {question}
Description: {description}
""".strip()

    try:
        response = model.generate_content(prompt)
        text = (response.text or "").strip()

        # remove accidental markdown fences
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()

        data = json.loads(text)
        category = str(data.get("category", "general")).strip().lower()

        if category in ALLOWED_CATEGORIES:
            return category
    except Exception:
        pass

    return "general"
