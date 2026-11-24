import json
import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


def is_gemini_enabled() -> bool:
    return bool(get_settings().gemini_api_key)


def _call_gemini(
    prompt: str,
    system_instruction: str = "",
    response_mime_type: str | None = None,
    temperature: float = 0.3,
) -> str | None:
    cfg = get_settings()
    if not cfg.gemini_api_key:
        return None

    url = GEMINI_ENDPOINT_TEMPLATE.format(model=cfg.gemini_model)
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    if response_mime_type:
        payload["generationConfig"]["responseMimeType"] = response_mime_type

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                url,
                params={"key": cfg.gemini_api_key},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Gemini API request failed; falling back to heuristic mode: %s", exc)
        return None

    try:
        candidates = data.get("candidates") or []
        parts = candidates[0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts).strip()
        return text or None
    except (IndexError, KeyError, TypeError) as exc:
        logger.warning("Unexpected Gemini response format: %s", exc)
        return None


def generate_json(prompt: str, system_instruction: str = "") -> dict[str, Any] | None:
    """Call Gemini API expecting JSON output; returns None if unavailable or invalid."""
    raw = _call_gemini(
        prompt=prompt,
        system_instruction=system_instruction,
        response_mime_type="application/json",
        temperature=0.2,
    )
    if not raw:
        return None
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        logger.warning("Gemini returned invalid JSON; falling back to heuristic.")
        return None


def generate_text(prompt: str, system_instruction: str = "", temperature: float = 0.4) -> str | None:
    """Call Gemini API for plain text output; returns None if unavailable."""
    return _call_gemini(
        prompt=prompt,
        system_instruction=system_instruction,
        response_mime_type=None,
        temperature=temperature,
    )
