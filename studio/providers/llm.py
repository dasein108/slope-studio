"""LLM text completion for the script stage. Returns raw text (expected JSON)."""

from __future__ import annotations

import httpx

from studio.config import env

TIMEOUT = httpx.Timeout(120.0)


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
        return _openai_compatible(
            "https://openrouter.ai/api/v1", env("OPENROUTER_API_KEY"),
            "meta-llama/llama-3.1-8b-instruct:free", system, user)
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
