"""OpenAI API integration using raw requests. No SDK dependency."""

import logging
from dataclasses import dataclass

import requests as http

logger = logging.getLogger(__name__)

API_URL = "https://api.openai.com/v1/chat/completions"
MODELS_URL = "https://api.openai.com/v1/models"
REQUEST_TIMEOUT = 60


@dataclass
class AIResult:
    success: bool
    changelog: str
    error: str | None
    tokens_used: int


def list_models(api_key: str) -> list[str]:
    """Fetch available chat models from OpenAI API."""
    if not api_key:
        return []

    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = http.get(MODELS_URL, headers=headers, timeout=REQUEST_TIMEOUT)
    except http.RequestException:
        logger.warning("Failed to fetch models from OpenAI")
        return []

    if response.status_code != 200:
        logger.warning("OpenAI models endpoint returned %d", response.status_code)
        return []

    try:
        data = response.json()
        models = [m["id"] for m in data.get("data", [])]
        # Filter to chat-capable models (gpt, o1, o3, o4, chatgpt)
        chat_prefixes = ("gpt-", "o1", "o3", "o4", "chatgpt-")
        chat_models = [m for m in models if m.startswith(chat_prefixes)]
        chat_models.sort()
        return chat_models
    except (KeyError, ValueError):
        logger.warning("Unexpected response from OpenAI models endpoint")
        return []


def generate_changelog(
    system_prompt: str,
    changeset: str,
    api_key: str,
    model: str,
) -> AIResult:
    """Send changeset to OpenAI and return generated changelog."""
    if not api_key:
        return AIResult(
            success=False,
            changelog="",
            error="OpenAI API key is not configured",
            tokens_used=0,
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": changeset},
        ],
        "max_completion_tokens": 2000,
    }

    try:
        response = http.post(
            API_URL,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except http.Timeout:
        return AIResult(
            success=False,
            changelog="",
            error="OpenAI request timed out. Try again or use a smaller diff.",
            tokens_used=0,
        )
    except http.ConnectionError:
        return AIResult(
            success=False,
            changelog="",
            error="Could not connect to OpenAI API.",
            tokens_used=0,
        )
    except http.RequestException as e:
        return AIResult(
            success=False,
            changelog="",
            error=f"Request error: {e}",
            tokens_used=0,
        )

    # Handle HTTP errors
    if response.status_code == 401:
        return AIResult(
            success=False,
            changelog="",
            error="OpenAI API key is invalid. Check addon configuration.",
            tokens_used=0,
        )
    if response.status_code == 429:
        return AIResult(
            success=False,
            changelog="",
            error="Rate limited by OpenAI. Try again in a few minutes.",
            tokens_used=0,
        )
    if response.status_code != 200:
        try:
            err_body = response.json()
            err_msg = err_body.get("error", {}).get("message", response.text[:200])
        except Exception:
            err_msg = response.text[:200]
        return AIResult(
            success=False,
            changelog="",
            error=f"OpenAI API error ({response.status_code}): {err_msg}",
            tokens_used=0,
        )

    # Parse success response
    try:
        data = response.json()
        changelog = data["choices"][0]["message"]["content"].strip()
        tokens_used = data.get("usage", {}).get("total_tokens", 0)
        logger.info("Changelog generated. Tokens used: %d", tokens_used)
        return AIResult(
            success=True,
            changelog=changelog,
            error=None,
            tokens_used=tokens_used,
        )
    except (KeyError, IndexError) as e:
        return AIResult(
            success=False,
            changelog="",
            error=f"Unexpected OpenAI response format: {e}",
            tokens_used=0,
        )
