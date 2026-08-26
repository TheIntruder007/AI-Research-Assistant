"""Command-line entry point with a dynamically loaded language-model adapter."""

import argparse
import asyncio
import json
import os
from collections.abc import Sequence
from pathlib import Path

from writing.adapters.language_model import (
    LanguageModelConfigurationError,
    close_language_model,
    load_language_model,
    resolve_language_model,
)
from writing.config import ReviewConfig
from writing.graph import run_review_async
from writing.modules.citation_formatter import SUPPORTED_CITATION_STYLES
from writing.schemas import ReviewInput, ReviewResult


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="literature-review",
        description="Run an outline-driven literature-review LangGraph.",
    )
    parser.add_argument("--request", required=True, help="Path to ReviewInput JSON.")
    parser.add_argument(
        "--model-factory",
        default=os.getenv("LITERATURE_REVIEW_MODEL_FACTORY"),
        help=(
            "Language-model adapter or zero-argument factory as module:attribute. "
            "Defaults to LITERATURE_REVIEW_MODEL_FACTORY, then DeepSeek environment settings."
        ),
    )
    parser.add_argument("--run-id", help="Stable run ID used for recovery.")
    parser.add_argument(
        "--citation-style",
        choices=SUPPORTED_CITATION_STYLES,
        help="Override citation_style from the request JSON before writing.",
    )
    parser.add_argument("--max-section-revisions", type=int, default=2)
    parser.add_argument("--max-section-attempts", type=int, default=2)
    parser.add_argument("--max-full-revisions", type=int, default=2)
    parser.add_argument("--max-card-attempts", type=int, default=2)
    parser.add_argument("--max-concurrency", type=int, default=8)
    parser.add_argument(
        "--semantic-audits",
        action="store_true",
        help="Enable separate LLM semantic audits for generated sections.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the configured review and print a machine-readable result."""

    parser = _parser()
    arguments = parser.parse_args(argv)
    request_path = Path(arguments.request).resolve()
    raw_request = json.loads(request_path.read_text(encoding="utf-8-sig"))
    request = ReviewInput.model_validate(raw_request)
    if arguments.citation_style is not None:
        request = request.model_copy(
            update={"citation_style": arguments.citation_style}
        )
    try:
        model = (
            load_language_model(arguments.model_factory)
            if arguments.model_factory
            else resolve_language_model(None)
        )
    except LanguageModelConfigurationError as error:
        parser.error(str(error))
    config = ReviewConfig(
        max_section_revision_rounds=arguments.max_section_revisions,
        max_section_attempts=arguments.max_section_attempts,
        max_full_revision_rounds=arguments.max_full_revisions,
        max_card_attempts=arguments.max_card_attempts,
        max_concurrency=arguments.max_concurrency,
        semantic_audits=arguments.semantic_audits,
    )

    async def execute() -> ReviewResult:
        try:
            return await run_review_async(
                request,
                model,
                config=config,
                run_id=arguments.run_id,
                outline_base_directory=request_path.parent,
            )
        finally:
            await close_language_model(model)

    result = asyncio.run(execute())
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if result.succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
