import re
import html
import unicodedata

def preprocess_text(text: str) -> str:
    """
    Advanced data cleaning pipeline to execute before chunking and embedding.
    """
    if not text:
        return ""

    # 1. Unescape HTML entities (e.g., turns &amp; into &, &quot; into ")
    text = html.unescape(text)

    # 2. Normalize Unicode (standardizes stylized quotes, dashes, and ligatures)
    text = unicodedata.normalize("NFKC", text)

    # 3. Strip raw HTML tags (commonly found in API descriptions)
    text = re.sub(r'<[^>]+>', ' ', text)

    # 4. Remove zero-width spaces and invisible characters that confuse LLMs
    text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', text)

    # 5. Normalize whitespace and linebreaks (your original logic, preserved)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def split_text_into_chunks(
    text: str,
    target_size: int = 700,
    overlap: int = 120,
) -> list[str]:
    text = preprocess_text(text)
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return [text]

    chunks = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= target_size:
            current = candidate
            continue
        if current:
            chunks.append(current.strip())
        if len(paragraph) <= target_size:
            current = paragraph
            continue
        start = 0
        while start < len(paragraph):
            end = min(start + target_size, len(paragraph))
            piece = paragraph[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= len(paragraph):
                break
            start = max(end - overlap, start + 1)
        current = ""
    if current.strip():
        chunks.append(current.strip())

    return chunks

def safe_float(value):
    try:
        if value in (None, "", "null"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None



