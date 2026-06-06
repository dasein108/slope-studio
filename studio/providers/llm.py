"""LLM text completion for the script stage. Returns raw text (expected JSON)."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import httpx

from studio.config import env

TIMEOUT = httpx.Timeout(120.0)


def vision_json(image_path: str | Path, system: str, user: str, provider: str = "gemini") -> str:
    """Ask a vision-capable model a question about an image; return raw JSON text.

    Used for tasks like locating a face's mouth for lip-sync placement. Gemini and
    OpenAI both accept an inline base64 image; default to Gemini (gemini-2.5-flash)."""
    p = Path(image_path)
    data = base64.b64encode(p.read_bytes()).decode()
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    if provider == "gemini":
        key = env("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("missing GEMINI_API_KEY")
        r = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash:generateContent",
            headers={"x-goog-api-key": key},
            json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [
                    {"inline_data": {"mime_type": mime, "data": data}},
                    {"text": user},
                ]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    if provider == "openai":
        key = env("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("missing OPENAI_API_KEY")
        r = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": [
                        {"type": "text", "text": user},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{mime};base64,{data}"}},
                    ]},
                ],
                "response_format": {"type": "json_object"},
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    raise ValueError(f"unknown vision provider {provider}")


def complete(provider: str, system: str, user: str) -> str:
    if provider == "stub":
        raise RuntimeError("stub provider has no LLM; handled in stage, not here")
    if provider == "ollama":
        return _ollama(system, user)
    if provider == "groq":
        return _openai_compatible(
            "https://api.groq.com/openai/v1", env("GROQ_API_KEY"),
            "llama-3.1-8b-instant", system, user)
    if provider == "openrouter":
        # default to a top model (GPT-5); override with OPENROUTER_MODEL for any
        # openrouter slug (e.g. "anthropic/claude-opus-4", "google/gemini-2.5-pro").
        return _openai_compatible(
            "https://openrouter.ai/api/v1", env("OPENROUTER_API_KEY"),
            env("OPENROUTER_MODEL") or "openai/gpt-5", system, user)
    if provider == "openai":
        return _openai_compatible(
            "https://api.openai.com/v1", env("OPENAI_API_KEY"),
            "gpt-4o-mini", system, user)
    if provider == "gemini":
        return _gemini(system, user)
    raise ValueError(f"unknown llm provider {provider}")


def _openai_compatible(base: str, key: str | None, model: str, system: str, user: str) -> str:
    if not key:
        raise RuntimeError(f"missing API key for {base}")
    r = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.8,
            "response_format": {"type": "json_object"},
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _ollama(system: str, user: str) -> str:
    host = env("OLLAMA_HOST") or "http://localhost:11434"
    r = httpx.post(
        f"{host}/api/chat",
        json={
            "model": "llama3.1:8b",
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "format": "json",
            "stream": False,
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def _gemini(system: str, user: str) -> str:
    key = env("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("missing GEMINI_API_KEY")
    r = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent",
        headers={"x-goog-api-key": key},
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
