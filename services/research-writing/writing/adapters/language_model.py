"""Language-model interface used by semantic workflow modules."""

import importlib
import os
from typing import Protocol, TypeVar, cast, runtime_checkable

from pydantic import BaseModel

StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


class LanguageModel(Protocol):
    """Generate schema-validated output from separated system and user prompts."""

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredOutput],
    ) -> StructuredOutput: ...


@runtime_checkable
class AsyncClosableLanguageModel(Protocol):
    """Optional lifecycle interface for adapters that own async resources."""

    async def aclose(self) -> None: ...


async def close_language_model(model: object) -> None:
    """Close an adapter when it exposes the optional lifecycle interface."""

    if isinstance(model, AsyncClosableLanguageModel):
        await model.aclose()


async def generate_validated(
    model: LanguageModel,
    *,
    system_prompt: str,
    user_prompt: str,
    response_model: type[StructuredOutput],
) -> StructuredOutput:
    """Validate every adapter result even when the adapter claims structured output."""

    output = await model.generate_structured(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=response_model,
    )
    return response_model.model_validate(output)


class LanguageModelConfigurationError(RuntimeError):
    """Raised when no usable language-model adapter is configured."""


def load_language_model(specification: str) -> LanguageModel:
    """Load `module:attribute`, calling the attribute when it is a factory."""

    module_name, separator, attribute_name = specification.partition(":")
    if not separator or not module_name or not attribute_name:
        raise LanguageModelConfigurationError(
            "model factory must use module:attribute syntax"
        )
    module = importlib.import_module(module_name)
    candidate = getattr(module, attribute_name)
    model = candidate if hasattr(candidate, "generate_structured") else candidate()
    if not hasattr(model, "generate_structured"):
        raise LanguageModelConfigurationError(
            "loaded model must implement generate_structured"
        )
    return cast(LanguageModel, model)


def resolve_language_model(model: LanguageModel | None) -> LanguageModel:
    """Use an injected adapter or resolve one from the provider-neutral environment setting."""

    if model is not None:
        return model
    specification = os.getenv("LITERATURE_REVIEW_MODEL_FACTORY")
    if specification:
        return load_language_model(specification)
    if os.getenv("DEEPSEEK_API_KEY"):
        from writing.adapters.deepseek import create_deepseek_model

        return create_deepseek_model()
    if os.getenv("OPENAI_COMPATIBLE_API_KEY"):
        from writing.adapters.openai_compatible import (
            create_openai_compatible_model,
        )

        return create_openai_compatible_model()
    raise LanguageModelConfigurationError(
        "pass a LanguageModel adapter, set LITERATURE_REVIEW_MODEL_FACTORY, "
        "set DEEPSEEK_API_KEY, or configure OPENAI_COMPATIBLE_*"
    )
