import json
import os
import re

import google.generativeai as genai


def get_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-3-flash-preview")


def _extract_json(text: str) -> dict | None:
    if not text:
        return None

    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass

    brace = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if brace:
        try:
            return json.loads(brace.group(1))
        except Exception:
            pass

    return None


def generate_grounded_completion(prompt: str) -> dict:
    model = get_model()
    response = model.generate_content(prompt)
    text = getattr(response, "text", "") or ""

    if not text.strip():
        return {
            "answer": "I could not generate a response from the model.",
            "key_insights": [],
            "tips": [],
            "limitations": ["The language model returned an empty response."],
        }

    data = _extract_json(text)
    if not data:
        return {
            "answer": text.strip(),
            "key_insights": [],
            "tips": [],
            "limitations": ["The model did not return valid structured JSON."],
        }

    return {
        "answer": str(data.get("answer", "")).strip(),
        "key_insights": [
            str(x).strip() for x in data.get("key_insights", []) if str(x).strip()
        ],
        "tips": [str(x).strip() for x in data.get("tips", []) if str(x).strip()],
        "limitations": [
            str(x).strip() for x in data.get("limitations", []) if str(x).strip()
        ],
    }
