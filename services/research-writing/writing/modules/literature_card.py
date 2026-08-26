"""Build one structured literature card from one Markdown paper."""

import json
from hashlib import sha256
from pathlib import Path

from pydantic import ValidationError

from writing.adapters.artifact_store import ArtifactStore
from writing.adapters.language_model import (
    LanguageModel,
    generate_validated,
)
from writing.modules.prompt_loader import load_prompt
from writing.schemas import (
    LiteratureCard,
    LiteratureCardContent,
    PaperDocument,
    PaperMetadata,
    TagDefinition,
)


async def build_literature_card(
    review_question: str,
    tag_definitions: list[TagDefinition],
    document: PaperDocument,
    model: LanguageModel,
) -> LiteratureCard:
    """Read exactly one registered paper and extract review-scoped evidence."""

    system_prompt = load_prompt("build_literature_card.md")
    paper_text = Path(document.source_path).read_text(encoding="utf-8-sig")
    user_prompt = json.dumps(
        {
            "review_question": review_question,
            "paper_id": document.paper_id,
            "evidence_depth": document.evidence_depth,
            "known_metadata": document.metadata.model_dump(mode="json"),
            "tag_definitions": [
                definition.model_dump(mode="json") for definition in tag_definitions
            ],
            "paper_markdown": paper_text,
        },
        ensure_ascii=False,
        indent=2,
    )
    content = await generate_validated(
        model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=LiteratureCardContent,
    )
    metadata = content.metadata.model_dump(mode="python")
    known_metadata = document.metadata.model_dump(mode="python", exclude_none=True)
    metadata.update(
        {
            field: value
            for field, value in known_metadata.items()
            if value != "" and value != []
        }
    )
    card_fields = content.model_dump(mode="python", exclude={"metadata"})
    return LiteratureCard(
        paper_id=document.paper_id,
        metadata=PaperMetadata.model_validate(metadata),
        **card_fields,
    )


def _cache_key(document: PaperDocument, definitions: list[TagDefinition]) -> str:
    encoded_definitions = json.dumps(
        [definition.model_dump(mode="json") for definition in definitions],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(
        f"{document.content_hash}\n{encoded_definitions}".encode()
    ).hexdigest()


async def build_cached_literature_card(
    review_question: str,
    tag_definitions: list[TagDefinition],
    document: PaperDocument,
    model: LanguageModel,
    store: ArtifactStore,
) -> LiteratureCard:
    """Reuse a valid card when paper content and tag semantics are unchanged."""

    card_path = f"literature_cards/{document.paper_id}.json"
    cache_path = f"card_cache/{document.paper_id}.json"
    cache_key = _cache_key(document, tag_definitions)

    if store.exists(cache_path) and store.exists(card_path):
        cache_record = store.read_json(cache_path)
        if isinstance(cache_record, dict) and cache_record.get("cache_key") == cache_key:
            try:
                return LiteratureCard.model_validate(store.read_json(card_path))
            except ValidationError:
                pass

    card = await build_literature_card(
        review_question, tag_definitions, document, model
    )
    store.write_json(card_path, card.model_dump(mode="json"))
    store.write_json(
        cache_path,
        {"cache_key": cache_key, "card_path": card_path},
    )
    return card
