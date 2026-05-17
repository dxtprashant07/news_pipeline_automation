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

    resp = requests.post(
        url,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        json={
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        },
        timeout=60,
    )
    resp.raise_for_status()
    data  = resp.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text  = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise ValueError(f"Gemini model '{model}' returned no text")
    logger.debug(f"Gemini {model}: tokens={data.get('usageMetadata', {}).get('totalTokenCount', '?')}")
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
