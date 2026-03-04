"""Gemini client wrapper used by LangGraph nodes."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from google import genai
from google.genai import types

from pr_flow_agents.logging_utils import get_logger

logger = get_logger(__name__)


class GeminiClient:
    """Thin wrapper around google-genai with debug logging."""

    def __init__(self, api_key: str | None = None) -> None:
        key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self._client = genai.Client(api_key=key)

    def generate_text(self, prompt: str, model: str = "gemini-2.0-flash") -> str:
        logger.debug(
            "gemini_generate_text_start model=%s prompt_chars=%s",
            model,
            len(prompt),
        )
        response = self._client.models.generate_content(
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.1),
        )
        text = (response.text or "").strip()
        logger.debug(
            "gemini_generate_text_done model=%s output_chars=%s",
            model,
            len(text),
        )
        return text

    def generate_json(
        self,
        prompt: str,
        model: str = "gemini-2.0-flash",
        retries: int = 2,
    ) -> Any:
        """Generate strict JSON with small retry loop."""

        last_err: Exception | None = None
        for attempt in range(1, retries + 2):
            logger.debug(
                "gemini_generate_json_attempt attempt=%s model=%s",
                attempt,
                model,
            )
            try:
                text = self.generate_text(prompt, model=model)
                clean = _strip_json_fences(text)
                parsed = json.loads(clean)
                logger.debug("gemini_generate_json_done attempt=%s", attempt)
                return parsed
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.warning(
                    "gemini_generate_json_parse_failed attempt=%s error=%s",
                    attempt,
                    str(exc),
                )

        raise RuntimeError(f"Failed to parse Gemini JSON response: {last_err}")


def _strip_json_fences(text: str) -> str:
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\\s*", "", text)
        text = re.sub(r"\\s*```$", "", text)
    return text.strip()


_default_client: GeminiClient | None = None


def _client() -> GeminiClient:
    global _default_client
    if _default_client is None:
        _default_client = GeminiClient()
    return _default_client


def generate_text(prompt: str, model: str = "gemini-2.0-flash") -> str:
    return _client().generate_text(prompt, model=model)


def generate_json(prompt: str, model: str = "gemini-2.0-flash", retries: int = 2) -> Any:
    return _client().generate_json(prompt, model=model, retries=retries)
