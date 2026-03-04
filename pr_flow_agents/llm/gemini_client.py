"""Thin wrapper around the google-genai Gemini client."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from google import genai
from google.genai import types


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def generate_text(prompt: str, model: str = "gemini-2.5-flash") -> str:
    """Simple text generation wrapper."""

    client = _get_client()
    resp = client.models.generate_content(
        model=model,
        contents=types.Part.from_text(text=prompt),
        config=types.GenerateContentConfig(
            temperature=0.1,
            top_p=0.95,
            top_k=20,
        ),
    )
    # Flatten text parts
    parts: List[str] = []
    for cand in resp.candidates or []:
        for part in cand.content.parts or []:
            if part.text:
                parts.append(part.text)
    return "\n".join(parts).strip()


def generate_json(
    prompt: str, model: str = "gemini-2.5-flash", max_retries: int = 2
) -> Any:
    """Call Gemini with a JSON-only contract and parse the response.

    We keep this intentionally strict: the prompt must ask for a pure JSON
    object or array. We then attempt to parse the model output as JSON and
    retry a couple of times on failure.
    """

    import json

    last_err: Exception | None = None

    for _ in range(max_retries + 1):
        text = generate_text(prompt, model=model)
        try:
            return json.loads(text)
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"Failed to parse Gemini JSON response: {last_err}")
