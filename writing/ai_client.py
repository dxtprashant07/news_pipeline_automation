"""
Provider-routing layer for AI writing calls.

Model name prefix → provider:
  claude-*                     → Anthropic (with prompt caching)
  gpt-* | o1-* | o3-* | o4-*  → OpenAI
  gemini-*                     → Google Gemini
  llama-* | mixtral-* | gemma* → Groq

Fallback: if the primary provider raises an exception, generate() automatically
tries other providers whose API keys are set, in order: Groq → Gemini → Anthropic → OpenAI.
"""
from __future__ import annotations
from typing import Any
from core.utils.logger import get_logger

logger = get_logger("writing.ai_client")

# Deprecated or renamed model aliases → current working names
_MODEL_ALIASES: dict[str, str] = {
    "gemini-1.5-flash":           "gemini-2.0-flash",
    "gemini-1.5-flash-latest":    "gemini-2.0-flash",
    "gemini-1.5-flash-001":       "gemini-2.0-flash",
    "gemini-1.5-flash-002":       "gemini-2.0-flash",
    "gemini-1.5-pro":             "gemini-2.0-flash",
    "gemini-1.5-pro-latest":      "gemini-2.0-flash",
    "gemini-1.0-pro":             "gemini-2.0-flash",
    "gemini-pro":                 "gemini-2.0-flash",
    "gpt-4-turbo":                "gpt-4o",
    "gpt-4-turbo-preview":        "gpt-4o",
}

# Fallback model to use when a provider key is available but the primary model failed
_FALLBACK_MODEL = {
    "groq":      "llama-3.3-70b-versatile",
    "gemini":    "gemini-2.0-flash",
    "anthropic": "claude-haiku-4-5-20251001",
    "openai":    "gpt-4o-mini",
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


def _is_groq(model: str) -> bool:
    return model.lower().startswith(("llama-", "mixtral-", "gemma", "qwen-", "deepseek-"))


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
        temperature=1.0,
        messages=[
            {"role": "system", "content": system_text},
            {"role": "user",   "content": user_text},
        ],
    )
    logger.debug(f"OpenAI {model}: total_tokens={response.usage.total_tokens}")
    return response.choices[0].message.content.strip()


def _call_groq(*, model: str, api_key: str, system_text: str, user_text: str,
               max_tokens: int, **_) -> str:
    import time
    import openai as oai
    # Groq free tier TPM = 6000 (input tokens + requested output tokens combined).
    # Our system prompts + story content = ~2500-3000 input tokens.
    # So cap output at 2000 to keep total safely under 6000.
    # If that still triggers 413, halve to 1000 and retry once.
    client = oai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    caps = [min(max_tokens, 2000), min(max_tokens, 1000)]

    for cap_idx, groq_max in enumerate(caps):
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model,
                    max_tokens=groq_max,
                    temperature=0.9,
                    messages=[
                        {"role": "system", "content": system_text},
                        {"role": "user",   "content": user_text},
                    ],
                )
                logger.debug(f"Groq {model}: total_tokens={response.usage.total_tokens}, cap={groq_max}")
                return response.choices[0].message.content.strip()
            except oai.RateLimitError as exc:
                err_body = str(exc)
                # "tokens" type = request too large for TPM — reduce cap and retry
                if '"type": "tokens"' in err_body or "'type': 'tokens'" in err_body:
                    logger.warning(
                        f"Groq 413 tokens (cap={groq_max}, attempt cap {cap_idx+1}/2) — "
                        f"reducing output cap"
                    )
                    break  # break inner loop → try next cap
                # Regular rate limit (RPM) — wait and retry
                if attempt == 2:
                    raise
                wait = 15 * (attempt + 1)
                logger.warning(f"Groq rate limit (attempt {attempt+1}/3) — waiting {wait}s")
                time.sleep(wait)
        else:
            continue   # inner loop exhausted without cap-break — go to next cap
        if cap_idx == len(caps) - 1:
            raise RuntimeError(
                f"Groq '{model}' request too large even at cap={groq_max} tokens. "
                "Reduce article word count or switch to a model with higher TPM limits."
            )
    raise RuntimeError("Groq: all caps exhausted")


def _call_gemini(*, model: str, api_key: str, system_text: str, user_text: str,
                 max_tokens: int, **_) -> str:
    import time
    import requests
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent"
    output_tokens = max(max_tokens, 4096)

    resp = None
    for attempt in range(3):
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
        if resp.status_code == 429:
            if attempt == 2:
                resp.raise_for_status()  # give up after 3 attempts
            wait = 30 * (attempt + 1)   # 30s, then 60s
            logger.warning(f"Gemini 429 rate limit (attempt {attempt+1}/3) — waiting {wait}s")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        break   # success — exit retry loop

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


def _dispatch(*, model: str, api_key: str, system_text: str, user_text: str,
              max_tokens: int, cache_system: bool = True) -> str:
    """Route a single call to the right provider using the given key."""
    if _is_anthropic(model):
        return _call_anthropic(model=model, api_key=api_key, system_text=system_text,
                               user_text=user_text, max_tokens=max_tokens, cache_system=cache_system)
    if _is_groq(model):
        return _call_groq(model=model, api_key=api_key, system_text=system_text,
                          user_text=user_text, max_tokens=max_tokens)
    if _is_gemini(model):
        return _call_gemini(model=model, api_key=api_key, system_text=system_text,
                            user_text=user_text, max_tokens=max_tokens)
    if _is_openai(model):
        return _call_openai(model=model, api_key=api_key, system_text=system_text,
                            user_text=user_text, max_tokens=max_tokens)
    raise ValueError(
        f"Cannot infer AI provider from model '{model}'. "
        "Use claude-*, gemini-*, gpt-*, o1-*, o3-*, o4-*, llama-*, mixtral-*, or gemma*."
    )


def _get_key_for_model(model: str, *,
                       anthropic_api_key: str, openai_api_key: str,
                       gemini_api_key: str, groq_api_key: str) -> str:
    import os
    if _is_anthropic(model): return anthropic_api_key
    if _is_groq(model):      return groq_api_key or os.environ.get("GROQ_API_KEY", "")
    if _is_gemini(model):    return gemini_api_key
    if _is_openai(model):    return openai_api_key
    return ""


def generate(
    *,
    model: str,
    anthropic_api_key: str = "",
    openai_api_key: str = "",
    gemini_api_key: str = "",
    groq_api_key: str = "",
    system_text: str,
    user_text: str,
    max_tokens: int,
    cache_system: bool = True,
) -> str:
    """
    Route to the correct AI provider and return generated text.
    If the primary model fails for any reason (token limit, rate limit, API error),
    automatically falls back to other providers whose keys are configured.
    """
    import os
    groq_api_key = groq_api_key or os.environ.get("GROQ_API_KEY", "")
    model = _resolve_model(model)

    key = _get_key_for_model(model, anthropic_api_key=anthropic_api_key,
                              openai_api_key=openai_api_key, gemini_api_key=gemini_api_key,
                              groq_api_key=groq_api_key)
    if not key:
        raise ValueError(
            f"Model '{model}' requires an API key that is not set in .env. "
            "Add the relevant key (GROQ_API_KEY / GEMINI_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY)."
        )

    # ── Primary attempt ───────────────────────────────────────────────────────
    primary_error: Exception | None = None
    try:
        return _dispatch(model=model, api_key=key, system_text=system_text,
                         user_text=user_text, max_tokens=max_tokens, cache_system=cache_system)
    except Exception as exc:
        primary_error = exc
        logger.warning(f"Primary model '{model}' failed: {exc!r} — trying fallbacks")

    # ── Fallback chain (skip the provider that just failed) ───────────────────
    all_keys = {
        "groq":      groq_api_key,
        "gemini":    gemini_api_key,
        "anthropic": anthropic_api_key,
        "openai":    openai_api_key,
    }
    # Determine which provider family the primary model belongs to
    def _family(m: str) -> str:
        if _is_anthropic(m): return "anthropic"
        if _is_groq(m):      return "groq"
        if _is_gemini(m):    return "gemini"
        if _is_openai(m):    return "openai"
        return ""

    failed_family = _family(model)
    # Try in order: groq (cheapest/fastest) → gemini → anthropic → openai
    for provider in ("groq", "gemini", "anthropic", "openai"):
        if provider == failed_family:
            continue
        fb_key = all_keys.get(provider, "")
        if not fb_key:
            continue
        fb_model = _FALLBACK_MODEL[provider]
        try:
            logger.info(f"  Fallback: using '{fb_model}' ({provider})")
            result = _dispatch(model=fb_model, api_key=fb_key, system_text=system_text,
                               user_text=user_text, max_tokens=max_tokens, cache_system=False)
            logger.info(f"  Fallback '{fb_model}' succeeded")
            return result
        except Exception as fb_exc:
            logger.warning(f"  Fallback '{fb_model}' also failed: {fb_exc!r}")

    raise RuntimeError(
        f"All AI providers failed. Primary ('{model}'): {primary_error!r}"
    )
