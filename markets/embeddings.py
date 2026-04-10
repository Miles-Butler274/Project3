import os

import numpy as np
import requests


GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
GEMINI_EMBEDDING_TASK_TYPE = os.getenv("GEMINI_EMBEDDING_TASK_TYPE", "RETRIEVAL_DOCUMENT")
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _get_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return api_key


def _truncate_text(text: str, max_chars: int = 8000) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def embed_text(
    text: str,
    task_type: str | None = None,
) -> list[float]:
    api_key = _get_api_key()
    model = GEMINI_EMBEDDING_MODEL
    task = task_type or GEMINI_EMBEDDING_TASK_TYPE

    url = f"{GEMINI_API_BASE}/{model}:embedContent"

    payload = {
        "model": f"models/{model}",
        "content": {
            "parts": [
                {
                    "text": _truncate_text(text),
                }
            ]
        },
    }

    if task:
        payload["taskType"] = task

    response = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=30,
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()

    data = response.json()
    values = data.get("embedding", {}).get("values")
    if not isinstance(values, list) or not values:
        raise RuntimeError(f"Invalid embedding response: {data}")

    return [float(x) for x in values]


def embed_query(text: str) -> list[float]:
    return embed_text(text, task_type="RETRIEVAL_QUERY")


def cosine_similarity(a, b) -> float:
    a = np.array(a or [], dtype=float)
    b = np.array(b or [], dtype=float)

    if a.size == 0 or b.size == 0:
        return 0.0

    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0

    return float(np.dot(a, b) / denom)
