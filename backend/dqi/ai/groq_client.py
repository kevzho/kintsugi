"""Thin wrapper over the Groq SDK with on-disk caching and graceful degradation.

Never raises to the caller: on missing key, rate limit (429), timeout, or any
error it returns None and the summarizer falls back to a deterministic summary.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

from .. import config

logger = logging.getLogger("dqi.ai")

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache"


def is_configured() -> bool:
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.json"


def _cache_key(system: str, user: str) -> str:
    return hashlib.sha256(f"{config.GROQ_MODEL}\n{system}\n{user}".encode("utf-8")).hexdigest()


def _read_cache(key: str) -> Optional[str]:
    p = _cache_path(key)
    if p.exists():
        try:
            return json.loads(p.read_text())["response"]
        except Exception:
            return None
    return None


def _write_cache(key: str, response: str) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(key).write_text(json.dumps({"response": response}))
    except Exception:
        pass


def chat(system: str, user: str) -> Optional[str]:
    """Return the model's text response, or None to signal graceful degradation."""
    key = _cache_key(system, user)
    cached = _read_cache(key)
    if cached is not None:
        logger.info("groq cache hit")
        return cached

    if not is_configured():
        logger.info("GROQ_API_KEY not set — degrading to deterministic summary")
        return None

    try:
        from groq import Groq
    except Exception:
        logger.warning("groq SDK not importable — degrading")
        return None

    api_key = os.environ["GROQ_API_KEY"]
    last_err: Optional[Exception] = None
    for attempt in range(2):
        try:
            client = Groq(api_key=api_key, timeout=20.0)
            resp = client.chat.completions.create(
                model=config.GROQ_MODEL,
                temperature=config.GROQ_TEMPERATURE,
                max_tokens=config.GROQ_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            text = resp.choices[0].message.content or ""
            if text.strip():
                _write_cache(key, text)
                return text
        except Exception as exc:  # 429, timeouts, network, etc.
            last_err = exc
            logger.warning("groq attempt %d failed: %s", attempt + 1, type(exc).__name__)
    if last_err:
        logger.warning("groq exhausted retries: %s", type(last_err).__name__)
    return None
