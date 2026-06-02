"""
Provider-routing layer for AI writing calls.

Model name prefix → provider:
  claude-*          → Anthropic (with prompt caching)
  gpt-* | o1-* | o3-* | o4-*  → OpenAI
  gemini-*          → Google Gemini
"""
from __future__ import annotations
from typing import Any
from core.utils.logger import get_logger

logger = get_logger("writing.ai_client")

# Deprecated or renamed model aliases → current working names
_MODEL_ALIASES: dict[str, str] = {
    # Gemini — 1.x names are deprecated; map to current 2.x equivalents
    "gemini-1.5-flash":           "gemini-2.0-flash",
    "gemini-1.5-flash-latest":    "gemini-2.0-flash",
    "gemini-1.5-flash-001":       "gemini-2.0-flash",
    "gemini-1.5-flash-002":       "gemini-2.0-flash",
    "gemini-1.5-pro":             "gemini-2.0-flash",
    "gemini-1.5-pro-latest":      "gemini-2.0-flash",
    "gemini-1.0-pro":             "gemini-2.0-flash",
    "gemini-pro":                 "gemini-2.0-flash",
    # OpenAI — legacy aliases
    "gpt-4-turbo":                "gpt-4o",
    "gpt-4-turbo-preview":        "gpt-4o",
}


def _resolve_model(model: str) -> str:
    resolved = _MODEL_ALIASES.get(model.lower().strip(), model)
    if resolved != model:
        logger.warning(f"Model '{model}' is deprecated — using '{resolved}' instead.")
    return resolved


def _is_anthropic(model: str) -> bool:
    return model.lower().startswith("claude")


def _is_openai(model: str) -> bool:
    return model.lower().startswith(("gpt-", "o1-", "o3-", "o4-"))


def _is_gemini(model: str) -> bool:
    return model.lower().removeprefix("models/").startswith("gemini-")


def _call_anthropic(*, model: str, api_key: str, system_text: str, user_text: str,
                    max_tokens: int, cache_system: bool = True) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    system_block: dict[str, Any] = {"type": "text", "text": system_text}
    if cache_system:
        system_block["cache_control"] = {"type": "ephemeral"}

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=1.0,
        system=[system_block],
        messages=[{"role": "user", "content": user_text}],
    )
    logger.debug(
        f"Anthropic {model}: input={response.usage.input_tokens} "
        f"cache_read={getattr(response.usage, 'cache_read_input_tokens', 0)}"
    )
    return response.content[0].text.strip()


def _call_openai(*, model: str, api_key: str, system_text: str, user_text: str,
                 max_tokens: int, **_) -> str:
    import openai as oai
    client = oai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=1.2,
        messages=[
            {"role": "system", "content": system_text},
            {"role": "user",   "content": user_text},
        ],
    )
    logger.debug(f"OpenAI {model}: total_tokens={response.usage.total_tokens}")
    return response.choices[0].message.content.strip()


def _call_gemini(*, model: str, api_key: str, system_text: str, user_text: str,
                 max_tokens: int, **_) -> str:
    import requests
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent"

    # Gemini 2.x supports up to 8192 output tokens; ensure we never under-allocate.
    output_tokens = max(max_tokens, 4096)

    resp = requests.post(
        url,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        json={
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {
                "maxOutputTokens": output_tokens,
                "temperature": 0.9,
            },
        },
        timeout=120,
    )
    resp.raise_for_status()
    data      = resp.json()
    candidate = data.get("candidates", [{}])[0]
    finish    = candidate.get("finishReason", "")
    parts     = candidate.get("content", {}).get("parts", [])
    text      = "".join(p.get("text", "") for p in parts).strip()

    if not text:
        safety = candidate.get("safetyRatings", [])
        raise ValueError(
            f"Gemini '{model}' returned no text. "
            f"finishReason={finish}, safetyRatings={safety}"
        )

    if finish == "MAX_TOKENS":
        logger.warning(f"Gemini '{model}' hit MAX_TOKENS — response may be truncated")

    logger.debug(
        f"Gemini {model}: finish={finish}, "
        f"tokens={data.get('usageMetadata', {}).get('totalTokenCount', '?')}"
    )
    return text


def generate(
    *,
    model: str,
    anthropic_api_key: str,
    openai_api_key: str,
    gemini_api_key: str,
    system_text: str,
    user_text: str,
    max_tokens: int,
    cache_system: bool = True,
) -> str:
    """Route to the correct AI provider and return generated text."""
    model = _resolve_model(model)

    if _is_anthropic(model):
        if not anthropic_api_key:
            raise ValueError(f"Model '{model}' requires ANTHROPIC_API_KEY in .env")
        return _call_anthropic(model=model, api_key=anthropic_api_key,
                               system_text=system_text, user_text=user_text,
                               max_tokens=max_tokens, cache_system=cache_system)
    if _is_gemini(model):
        if not gemini_api_key:
            raise ValueError(f"Model '{model}' requires GEMINI_API_KEY in .env")
        return _call_gemini(model=model, api_key=gemini_api_key,
                            system_text=system_text, user_text=user_text, max_tokens=max_tokens)
    if _is_openai(model):
        if not openai_api_key:
            raise ValueError(f"Model '{model}' requires OPENAI_API_KEY in .env")
        return _call_openai(model=model, api_key=openai_api_key,
                            system_text=system_text, user_text=user_text, max_tokens=max_tokens)

    raise ValueError(
        f"Cannot infer AI provider from model '{model}'. "
        "Use claude-*, gemini-*, gpt-*, o1-*, o3-*, or o4-*."
    )
