import os

import google.generativeai as genai


def get_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-3-flash-preview")


def generate_grounded_completion(prompt: str) -> str:
    model = get_model()
    response = model.generate_content(prompt)
    text = getattr(response, "text", "") or ""

    if not text.strip():
        return "I could not generate a response from the model."

    return text.strip()
