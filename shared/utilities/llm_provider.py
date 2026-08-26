"""Local-first LLM provider layer shared by every pipeline service.

Every service asks for JSON-schema-constrained completions through this module
instead of talking to a model SDK directly, so the underlying model can be
swapped by changing configuration, not service code (see DECISIONS.md D-003).

The default and only configured provider is a local Ollama model
(LOCAL_AI_MODEL, default "qwen3.5:9b") reached over Ollama's native /api/chat
endpoint, which supports streaming and JSON-schema-constrained output directly.

Do not add a paid/cloud provider here without explicit user approval — see
DECISIONS.md "Local AI First Rule".
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.getenv("LOCAL_AI_MODEL", "qwen3.5:9b")


class LLMProviderError(Exception):
    """A user-facing error from the local model layer."""


@dataclass
class Completion:
    text: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    stop: str = "end"  # "end" | "length" | "refusal"


async def stream_json(*, system: str, user: str, schema: dict,
                      model: str | None = None,
                      max_tokens: int = 8000,
                      temperature: float = 0.3) -> AsyncIterator[dict]:
    """Yield {"type": "delta", "text": str} as output streams, then a single
    {"type": "done", "completion": Completion}. Raises LLMProviderError on failure."""
    model = model or DEFAULT_MODEL
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "format": schema,
        "options": {"temperature": temperature, "num_predict": max_tokens},
        "stream": True,
    }
    comp = Completion()
    parts: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=None) as http:
            async with http.stream("POST", f"{OLLAMA_HOST}/api/chat", json=payload) as resp:
                if resp.status_code == 404:
                    raise LLMProviderError(
                        f"Model '{model}' is not installed in Ollama. "
                        f"Run: ollama pull {model}")
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    delta = (chunk.get("message") or {}).get("content", "")
                    if delta:
                        parts.append(delta)
                        yield {"type": "delta", "text": delta}
                    if chunk.get("done"):
                        comp.prompt_tokens = chunk.get("prompt_eval_count", 0)
                        comp.completion_tokens = chunk.get("eval_count", 0)
                        if chunk.get("done_reason") == "length":
                            comp.stop = "length"
    except httpx.ConnectError:
        raise LLMProviderError(
            "Could not reach the local Ollama server at "
            f"{OLLAMA_HOST}. Start it with: ollama serve")
    except httpx.HTTPStatusError as e:
        raise LLMProviderError(f"Ollama returned an error ({e.response.status_code}). "
                               "Check `ollama list` and the model name.")

    comp.text = "".join(parts)
    if not comp.text.strip():
        comp.stop = "refusal"
    yield {"type": "done", "completion": comp}


async def complete_json(*, system: str, user: str, schema: dict,
                        model: str | None = None,
                        max_tokens: int = 8000,
                        temperature: float = 0.3) -> Completion:
    """A structured-JSON completion, non-streaming from the caller's point of view."""
    comp = Completion()
    async for event in stream_json(system=system, user=user, schema=schema,
                                   model=model, max_tokens=max_tokens,
                                   temperature=temperature):
        if event["type"] == "done":
            comp = event["completion"]
    return comp


async def health_check(model: str | None = None) -> bool:
    """True if Ollama is running and the configured model is installed."""
    model = model or DEFAULT_MODEL
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            resp = await http.get(f"{OLLAMA_HOST}/api/tags")
            resp.raise_for_status()
            names = {m["name"] for m in resp.json().get("models", [])}
            return model in names or f"{model}:latest" in names
    except httpx.HTTPError:
        return False
