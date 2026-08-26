"""LanguageModel adapter backed by the project's local Ollama provider.

Implements the `writing.adapters.language_model.LanguageModel` protocol using
`shared/utilities/llm_provider.py` — the same local-first provider Service 1
uses (see DECISIONS.md D-003) — instead of the repo's original
prompt-engineered OpenAI-compatible JSON-mode adapter. Ollama's native
schema-constrained decoding is more reliable than prompt-engineered JSON mode
for a small local model (see DECISIONS.md D-009).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.utilities import llm_provider  # noqa: E402

StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


class OllamaModelError(RuntimeError):
    """Raised when the local model fails to produce a schema-valid response."""


class OllamaLanguageModel:
    """Generate schema-validated output through the local Ollama provider."""

    def __init__(self, *, model: str | None = None, max_tokens: int = 8000,
                temperature: float = 0.3, think: bool = False) -> None:
        self._model = model or llm_provider.DEFAULT_MODEL
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._think = think

    async def generate_structured(
        self, *, system_prompt: str, user_prompt: str,
        response_model: type[StructuredOutput],
    ) -> StructuredOutput:
        schema = response_model.model_json_schema()
        comp = await llm_provider.complete_json(
            system=system_prompt, user=user_prompt, schema=schema,
            model=self._model, max_tokens=self._max_tokens,
            temperature=self._temperature, think=self._think,
        )
        if comp.stop == "refusal":
            raise OllamaModelError(
                "The local model produced no output for this request "
                f"(schema: {response_model.__name__}).")
        if comp.stop == "length":
            raise OllamaModelError(
                f"The local model's response was cut off before completing the "
                f"{response_model.__name__} schema. Try a smaller input or a "
                "higher max_tokens.")
        try:
            return response_model.model_validate_json(comp.text)
        except ValidationError as error:
            raise OllamaModelError(
                f"The local model's output did not match {response_model.__name__}: "
                f"{error}") from error


def create_ollama_model(*, max_tokens: int = 8000) -> OllamaLanguageModel:
    """Factory usable as WRITING_MODEL_FACTORY=writing.adapters.ollama_model:create_ollama_model."""
    return OllamaLanguageModel(max_tokens=max_tokens)
