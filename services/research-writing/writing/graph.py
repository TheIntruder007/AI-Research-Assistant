"""LangGraph orchestration and the package's public run interface."""

import asyncio
import hashlib
import re
from collections.abc import Sequence
from pathlib import Path
from typing import cast
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Overwrite, Send
from pydantic import BaseModel

from writing.adapters.artifact_store import (
    ArtifactStore,
    JsonValue,
    LocalArtifactStore,
)
from writing.adapters.document_parser import DocumentParser, contains_pdf
from writing.adapters.language_model import (
    LanguageModel,
    close_language_model,
    resolve_language_model,
)
from writing.config import ReviewConfig
from writing.modules.card_validation import (
    audit_literature_card_semantics,
    validate_literature_card,
)
from writing.modules.citation_formatter import build_citation_map
from writing.modules.document_registry import discover_documents
from writing.modules.hierarchical_recall import (
    analyze_tag_coverage,
    direct_items,
)
from writing.modules.literature_card import (
    build_cached_literature_card,
    build_literature_card,
)
from writing.modules.outline_parser import parse_outline
from writing.modules.outline_source import resolve_outline_source
from writing.modules.review_assembler import assemble_review
from writing.modules.review_auditor import (
    audit_full_review,
    audit_full_review_semantics,
    audit_visual_recommendation_evidence,
)
from writing.modules.review_writer import (
    revise_full_review,
    write_conclusion,
    write_introduction,
)
from writing.modules.section_auditor import (
    audit_section,
    audit_section_semantics,
)
from writing.modules.section_context import build_section_context
from writing.modules.section_writer import write_section_with_revisions
from writing.modules.tag_index import build_tag_index
from writing.modules.tag_semantics import define_tag_semantics
from writing.modules.tag_tree import build_tag_tree
from writing.modules.writing_order import plan_writing_order
from writing.schemas import (
    CardAudit,
    CitationInfo,
    FullReviewAudit,
    LiteratureCard,
    OutlineNode,
    PaperDocument,
    ReviewDocument,
    ReviewInput,
    ReviewResult,
    SectionAudit,
    SectionDraft,
    SectionRunResult,
    SectionSummary,
    SectionWritingContext,
    TagDefinition,
    TagIndex,
    TagIndexItem,
)
from writing.state import ReviewState

_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _dump(value: BaseModel) -> JsonValue:
    return cast(JsonValue, value.model_dump(mode="json"))


def _dump_many(values: Sequence[BaseModel]) -> JsonValue:
    return cast(JsonValue, [value.model_dump(mode="json") for value in values])


def _load_many(
    store: ArtifactStore, path: str, model: type[BaseModel]
) -> list[BaseModel]:
    raw = store.read_json(path)
    if not isinstance(raw, list):
        raise ValueError(f"artifact must contain a list: {path}")
    return [model.model_validate(item) for item in raw]


def _load_tree(store: ArtifactStore, path: str) -> list[OutlineNode]:
    return cast(list[OutlineNode], _load_many(store, path, OutlineNode))


def _load_definitions(store: ArtifactStore, path: str) -> list[TagDefinition]:
    return cast(list[TagDefinition], _load_many(store, path, TagDefinition))


def _load_index(store: ArtifactStore, path: str) -> TagIndex:
    raw = store.read_json(path)
    if not isinstance(raw, dict):
        raise ValueError(f"artifact must contain an object: {path}")
    return {
        str(tag_id): [TagIndexItem.model_validate(item) for item in items]
        for tag_id, items in raw.items()
        if isinstance(items, list)
    }


def _unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _reset_reduced_list(values: Sequence[str] = ()) -> list[str]:
    """Clear a reducer-backed channel at the start of a new invocation."""

    return cast(list[str], Overwrite(list(values)))


def _unresolved_section_draft(tag_id: str, output_language: str) -> SectionDraft:
    """Create safe body prose while the audit artifact retains the failed draft."""

    content = (
        "*本节审计未能解决，因此未纳入未经支持的内容。*"
        if output_language.casefold().startswith("zh")
        else "*This section audit could not be resolved; unsupported content was omitted.*"
    )
    return SectionDraft(
        tag_id=tag_id,
        content=content,
        cited_paper_ids=[],
        used_point_ids=[],
    )


def build_review_graph(
    model: LanguageModel,
    store: ArtifactStore,
    runtime: ReviewConfig,
    checkpointer: BaseCheckpointSaver[str],
) -> CompiledStateGraph[ReviewState, None, ReviewState, ReviewState]:
    """Compile the review graph around supplied model and persistence adapters."""

    async def initialize(state: ReviewState) -> dict[str, object]:
        tree = build_tag_tree(parse_outline(state["outline_source"]))
        tree_path = store.write_json("tag_tree.json", _dump_many(tree))
        return {"input_path": "input.json", "tag_tree_path": tree_path}

    async def define_tags(state: ReviewState) -> dict[str, object]:
        tree = _load_tree(store, state["tag_tree_path"])
        definitions = await define_tag_semantics(
            state["review_question"], tree, model
        )
        path = store.write_json("tag_definitions.json", _dump_many(definitions))
        return {"tag_definitions_path": path}

    async def register_documents(state: ReviewState) -> dict[str, object]:
        documents = discover_documents(state["literature_directory"])
        manifest = {
            "documents": [document.model_dump(mode="json") for document in documents]
        }
        path = store.write_json("manifest.json", cast(JsonValue, manifest))
        warnings = ["No Markdown literature documents were found."] if not documents else []
        return {
            "manifest_path": path,
            "paper_ids": [document.paper_id for document in documents],
            "warnings": warnings,
        }

    def dispatch_cards(state: ReviewState) -> str | list[Send]:
        raw = store.read_json(state["manifest_path"])
        if not isinstance(raw, dict):
            raise ValueError("manifest does not contain a document list")
        documents_value = raw.get("documents")
        if not isinstance(documents_value, list):
            raise ValueError("manifest does not contain a document list")
        documents: list[dict[str, JsonValue]] = []
        for document in documents_value:
            if not isinstance(document, dict):
                raise ValueError("manifest document entries must be objects")
            documents.append(document)
        if not documents:
            return "build_tag_index"
        return [
            Send(
                "build_literature_card",
                {
                    "worker_document": document,
                    "review_question": state["review_question"],
                    "tag_tree_path": state["tag_tree_path"],
                    "tag_definitions_path": state["tag_definitions_path"],
                },
            )
            for document in documents
        ]

    async def build_card_worker(state: ReviewState) -> dict[str, object]:
        document = PaperDocument.model_validate(state["worker_document"])
        audit_path = f"card_audits/{document.paper_id}.json"
        definitions = _load_definitions(store, state["tag_definitions_path"])
        tree = _load_tree(store, state["tag_tree_path"])
        attempt_errors: list[str] = []
        for attempt in range(1, runtime.max_card_attempts + 1):
            try:
                if attempt == 1:
                    card = await build_cached_literature_card(
                        state["review_question"], definitions, document, model, store
                    )
                else:
                    # Targeted retry (DECISIONS.md D-019): pass the previous
                    # attempt's validation errors back in so the model fixes
                    # the specific mistake (most commonly a point duplicated
                    # across an ancestor and descendant tag) instead of this
                    # being an identical, blind repeat of the same request.
                    card = await build_literature_card(
                        state["review_question"], definitions, document, model,
                        previous_errors=attempt_errors or None,
                    )
                    store.write_json(
                        f"literature_cards/{document.paper_id}.json", _dump(card)
                    )
                audit = validate_literature_card(card, tree)
                if runtime.semantic_audits and audit.passed:
                    audit = await audit_literature_card_semantics(
                        card, definitions, model
                    )
                audit = audit.model_copy(update={"attempts": attempt})
                store.write_json(audit_path, _dump(audit))
                if audit.passed:
                    return {
                        "completed_card_paths": [
                            f"literature_cards/{document.paper_id}.json"
                        ]
                    }
                attempt_errors.append(
                    f"attempt {attempt} validation: " + "; ".join(audit.errors)
                )
            except Exception as error:  # worker isolation is an explicit requirement
                attempt_errors.append(
                    f"attempt {attempt} {type(error).__name__}: {error}"
                )
        failed_audit = CardAudit(
            paper_id=document.paper_id,
            passed=False,
            errors=attempt_errors,
            attempts=runtime.max_card_attempts,
        )
        store.write_json(audit_path, _dump(failed_audit))
        return {
            "failed_paper_ids": [document.paper_id],
            "errors": [
                f"Paper {document.paper_id} failed after "
                f"{runtime.max_card_attempts} attempts: "
                + "; ".join(attempt_errors)
            ],
        }

    async def create_tag_index(state: ReviewState) -> dict[str, object]:
        tree = _load_tree(store, state["tag_tree_path"])
        paths = _unique(state.get("completed_card_paths", []))
        cards = [LiteratureCard.model_validate(store.read_json(path)) for path in paths]
        index = build_tag_index(cards, tree)
        rendered = {
            tag_id: [item.model_dump(mode="json") for item in items]
            for tag_id, items in index.items()
        }
        path = store.write_json("tag_index.json", cast(JsonValue, rendered))
        return {"tag_index_path": path}

    async def analyze_coverage(state: ReviewState) -> dict[str, object]:
        tree = _load_tree(store, state["tag_tree_path"])
        index = _load_index(store, state["tag_index_path"])
        report = analyze_tag_coverage(index, tree)
        path = store.write_json("tag_coverage.json", _dump(report))
        warnings = [
            f"Insufficient evidence for tag {tag_id}."
            for tag_id in report.insufficient_tag_ids
            if tag_id != "TAG-ROOT"
        ]
        return {"coverage_report_path": path, "warnings": warnings}

    async def plan_sections(state: ReviewState) -> dict[str, object]:
        tree = _load_tree(store, state["tag_tree_path"])
        return {"writing_order": plan_writing_order(tree), "next_section_index": 0}

    def route_to_section(state: ReviewState) -> str:
        return "write_section" if state["writing_order"] else "write_review"

    async def write_next_section(state: ReviewState) -> dict[str, object]:
        position = state["next_section_index"]
        tag_id = state["writing_order"][position]
        draft_path = f"section_drafts/{tag_id}.json"
        summary_path = f"section_summaries/{tag_id}.json"
        audit_path = f"section_audits/{tag_id}.json"
        try:
            tree = _load_tree(store, state["tag_tree_path"])
            definitions = _load_definitions(store, state["tag_definitions_path"])
            definition = next(item for item in definitions if item.tag_id == tag_id)
            index = _load_index(store, state["tag_index_path"])
            node = next(item for item in tree if item.tag_id == tag_id)
            child_summaries = {
                child_id: SectionSummary.model_validate(
                    store.read_json(f"section_summaries/{child_id}.json")
                )
                for child_id in node.child_ids
                if store.exists(f"section_summaries/{child_id}.json")
            }
            target_words = None
            total_words = state.get("target_words")
            if total_words is not None:
                target_words = max(
                    1, total_words // max(1, len(state["writing_order"]))
                )
            context = build_section_context(
                tag_id,
                tree,
                definitions,
                index,
                child_summaries,
                target_words,
                output_language=state["output_language"],
            )
            store.write_json(f"section_contexts/{tag_id}.json", _dump(context))

            if definition.node_type == "container":
                summary_values = list(child_summaries.values())
                # A container tag has no prose of its own (assemble_review()
                # renders only its heading; its children carry the actual
                # content) — but SectionDraft.content requires min_length=1
                # (see writing/schemas.py). A literal "" here is an invalid
                # state that crashes deterministically on EVERY run with a
                # container tag, regardless of model behavior (see
                # DECISIONS.md D-020) — not a model-reliability issue at all,
                # which is why retrying it could never help. A single space
                # satisfies the schema while still rendering as empty:
                # assemble_review() checks `draft.content.strip()` before
                # emitting any body text for a section.
                draft = SectionDraft(
                    tag_id=tag_id, content=" ", cited_paper_ids=[], used_point_ids=[]
                )
                audit = SectionAudit(
                    tag_id=tag_id,
                    passed=True,
                    unsupported_claims=[],
                    out_of_scope_content=[],
                    invalid_paper_ids=[],
                    missing_key_points=[],
                    duplicated_child_content=[],
                    revision_instructions=[],
                )
                run_result = SectionRunResult(
                    draft=draft,
                    audits=[audit],
                    resolved=True,
                    unresolved_issues=[],
                )
                summary = SectionSummary(
                    tag_id=tag_id,
                    summary=" ".join(item.summary for item in summary_values),
                    cited_paper_ids=_unique(
                        [paper for item in summary_values for paper in item.cited_paper_ids]
                    ),
                    used_point_ids=_unique(
                        [point for item in summary_values for point in item.used_point_ids]
                    ),
                )
            else:
                section_errors: list[str] = []
                for section_attempt in range(1, runtime.max_section_attempts + 1):
                    try:
                        run_result = await write_section_with_revisions(
                            context,
                            model,
                            max_revision_rounds=runtime.max_section_revision_rounds,
                            semantic_audit=runtime.semantic_audits,
                        )
                        break
                    except Exception as error:
                        section_errors.append(
                            f"attempt {section_attempt} {type(error).__name__}: {error}"
                        )
                        if section_attempt == runtime.max_section_attempts:
                            raise RuntimeError("; ".join(section_errors)) from error
                draft = run_result.draft
                summary = SectionSummary(
                    tag_id=tag_id,
                    summary=draft.summary or draft.content[:1200],
                    cited_paper_ids=draft.cited_paper_ids,
                    used_point_ids=draft.used_point_ids,
                )

            if not run_result.resolved:
                summary = SectionSummary(
                    tag_id=tag_id,
                    summary="Insufficient evidence: section audit was unresolved.",
                    cited_paper_ids=[],
                    used_point_ids=[],
                )

            persisted_draft = (
                draft
                if run_result.resolved
                else _unresolved_section_draft(tag_id, state["output_language"])
            )
            store.write_json(draft_path, _dump(persisted_draft))
            store.write_json(audit_path, _dump(run_result))
            store.write_json(summary_path, _dump(summary))
            result: dict[str, object] = {
                "completed_section_paths": [draft_path],
                "next_section_index": position + 1,
            }
            if not run_result.resolved:
                result["failed_tag_ids"] = [tag_id]
                result["warnings"] = [
                    f"Section {tag_id} has unresolved issues: "
                    + "; ".join(run_result.unresolved_issues)
                ]
            return result
        except Exception as error:
            draft = SectionDraft(
                tag_id=tag_id,
                content="*Section generation failed; no unsupported content was inserted.*",
                cited_paper_ids=[],
                used_point_ids=[],
            )
            summary = SectionSummary(
                tag_id=tag_id,
                summary=draft.content,
                cited_paper_ids=[],
                used_point_ids=[],
            )
            store.write_json(draft_path, _dump(draft))
            store.write_json(summary_path, _dump(summary))
            store.write_json(
                audit_path,
                {
                    "draft": draft.model_dump(mode="json"),
                    "audits": [],
                    "resolved": False,
                    "unresolved_issues": [f"{type(error).__name__}: {error}"],
                },
            )
            return {
                "completed_section_paths": [draft_path],
                "failed_tag_ids": [tag_id],
                "next_section_index": position + 1,
                "errors": [f"Section {tag_id} failed: {type(error).__name__}: {error}"],
            }

    def continue_sections(state: ReviewState) -> str:
        return (
            "write_section"
            if state["next_section_index"] < len(state["writing_order"])
            else "write_review"
        )

    async def write_review(state: ReviewState) -> dict[str, object]:
        tree = _load_tree(store, state["tag_tree_path"])
        definitions = _load_definitions(store, state["tag_definitions_path"])
        index = _load_index(store, state["tag_index_path"])
        cards = [
            LiteratureCard.model_validate(store.read_json(path))
            for path in _unique(state.get("completed_card_paths", []))
        ]
        metadata_by_paper_id = {card.paper_id: card.metadata for card in cards}
        drafts = {
            draft.tag_id: draft
            for path in _unique(state.get("completed_section_paths", []))
            for draft in [SectionDraft.model_validate(store.read_json(path))]
        }
        summaries: list[SectionSummary] = []
        resolved_tag_ids: set[str] = set()
        for tag_id in state["writing_order"]:
            summary_path = f"section_summaries/{tag_id}.json"
            audit_path = f"section_audits/{tag_id}.json"
            if not store.exists(summary_path) or not store.exists(audit_path):
                continue
            run_result = SectionRunResult.model_validate(store.read_json(audit_path))
            if run_result.resolved:
                resolved_tag_ids.add(tag_id)
                summaries.append(
                    SectionSummary.model_validate(store.read_json(summary_path))
                )
        summary_by_id = {summary.tag_id: summary for summary in summaries}
        top_level_ids = tree[0].child_ids
        top_level_summaries = [
            summary_by_id[tag_id] for tag_id in top_level_ids if tag_id in summary_by_id
        ]
        overview_points = direct_items("TAG-ROOT", index)
        for tag_id in top_level_ids:
            overview_points.extend(direct_items(tag_id, index))
        seen_points: set[str] = set()
        unique_overview_points: list[TagIndexItem] = []
        for item in overview_points:
            if item.point_id not in seen_points:
                seen_points.add(item.point_id)
                unique_overview_points.append(item)
        overview_points = unique_overview_points

        has_intro_evidence = bool(overview_points) or any(
            summary.used_point_ids for summary in summaries
        )
        has_conclusion_evidence = any(summary.used_point_ids for summary in summaries)
        if has_intro_evidence:
            introduction = await write_introduction(
                state["review_question"],
                tree,
                top_level_summaries,
                overview_points,
                model,
                output_language=state["output_language"],
            )
        else:
            chinese_output = state["output_language"].casefold().startswith("zh")
            introduction = SectionDraft(
                tag_id="INTRODUCTION",
                content=(
                    "*本综述可用证据不足。*"
                    if chinese_output
                    else "*Insufficient evidence is available for this review.*"
                ),
                cited_paper_ids=[],
                used_point_ids=[],
            )

        if has_conclusion_evidence:
            conclusion = await write_conclusion(
                state["review_question"],
                summaries,
                model,
                output_language=state["output_language"],
            )
        else:
            chinese_output = state["output_language"].casefold().startswith("zh")
            conclusion = SectionDraft(
                tag_id="CONCLUSION",
                content=(
                    "*无法形成有证据支持的结论。*"
                    if chinese_output
                    else "*No evidence-backed conclusion can be drawn.*"
                ),
                cited_paper_ids=[],
                used_point_ids=[],
            )

        citation_lookup: dict[str, CitationInfo] = {}
        point_content_lookup: dict[str, str] = {}
        for items in index.values():
            for item in items:
                citation_lookup[item.paper_id] = item.citation
                point_content_lookup[item.point_id] = item.content

        intro_allowed_papers = _unique(
            [item.paper_id for item in overview_points]
            + [
                paper_id
                for summary in top_level_summaries
                for paper_id in summary.cited_paper_ids
            ]
        )
        intro_allowed_points = _unique(
            [item.point_id for item in overview_points]
            + [
                point_id
                for summary in top_level_summaries
                for point_id in summary.used_point_ids
            ]
        )
        body_allowed_papers = _unique(
            [paper_id for summary in summaries for paper_id in summary.cited_paper_ids]
        )
        body_allowed_points = _unique(
            [point_id for summary in summaries for point_id in summary.used_point_ids]
        )
        introduction_context = SectionWritingContext(
            tag_id="INTRODUCTION",
            title="Introduction",
            outline_path=[tree[0].title],
            depth=0,
            writing_mode="subtree",
            direct_points=overview_points,
            ancestor_context=[],
            child_summaries=[summary.summary for summary in top_level_summaries],
            allowed_paper_ids=intro_allowed_papers,
            allowed_point_ids=intro_allowed_points,
            citations={
                paper_id: citation_lookup[paper_id]
                for paper_id in intro_allowed_papers
                if paper_id in citation_lookup
            },
            sibling_titles=[],
            prohibited_topics=[],
        )
        conclusion_context = SectionWritingContext(
            tag_id="CONCLUSION",
            title="Conclusion",
            outline_path=[tree[0].title],
            depth=0,
            writing_mode="subtree",
            direct_points=[],
            ancestor_context=[],
            child_summaries=[summary.summary for summary in summaries],
            allowed_paper_ids=body_allowed_papers,
            allowed_point_ids=body_allowed_points,
            citations={
                paper_id: citation_lookup[paper_id]
                for paper_id in body_allowed_papers
                if paper_id in citation_lookup
            },
            sibling_titles=[],
            prohibited_topics=[],
        )
        bookend_warnings: list[str] = []
        if not audit_section(introduction, introduction_context).passed:
            bookend_warnings.append(
                "Introduction output violated its evidence context and was replaced."
            )
            introduction = SectionDraft(
                tag_id="INTRODUCTION",
                content="*Introduction generation did not satisfy evidence constraints.*",
                cited_paper_ids=[],
                used_point_ids=[],
            )
        if not audit_section(conclusion, conclusion_context).passed:
            bookend_warnings.append(
                "Conclusion output violated its evidence context and was replaced."
            )
            conclusion = SectionDraft(
                tag_id="CONCLUSION",
                content="*No evidence-backed conclusion can be drawn.*",
                cited_paper_ids=[],
                used_point_ids=[],
            )

        async def assemble_and_audit() -> tuple[ReviewDocument, FullReviewAudit]:
            current_review = assemble_review(
                tree,
                definitions,
                drafts,
                introduction,
                conclusion,
                citation_lookup,
                citation_style=state["citation_style"],
                metadata_by_paper_id=metadata_by_paper_id,
                output_language=state["output_language"],
            )
            rendered_citations = build_citation_map(
                current_review.cited_paper_ids,
                metadata_by_paper_id,
                state["citation_style"],
            )
            current_audit = audit_full_review(
                current_review,
                tree,
                definitions,
                drafts,
                introduction,
                conclusion,
                rendered_citations,
                citation_style=state["citation_style"],
            )
            if runtime.semantic_audits and current_audit.passed:
                semantic = await audit_full_review_semantics(
                    state["review_question"],
                    current_review,
                    summaries,
                    model,
                    section_contents={
                        tag_id: draft.content for tag_id, draft in drafts.items()
                    },
                )
                if semantic.visual_recommendations:
                    try:
                        approved_visuals = await audit_visual_recommendation_evidence(
                            semantic.visual_recommendations,
                            point_content_lookup,
                            model,
                        )
                    except Exception:
                        approved_visuals = []
                        bookend_warnings.append(
                            "Visual recommendation evidence audit failed; suggestions omitted."
                        )
                    semantic = semantic.model_copy(
                        update={"visual_recommendations": approved_visuals}
                    )
                if semantic.visual_recommendations:
                    current_review = assemble_review(
                        tree,
                        definitions,
                        drafts,
                        introduction,
                        conclusion,
                        citation_lookup,
                        citation_style=state["citation_style"],
                        metadata_by_paper_id=metadata_by_paper_id,
                        output_language=state["output_language"],
                        visual_recommendations=semantic.visual_recommendations,
                    )
                    current_audit = audit_full_review(
                        current_review,
                        tree,
                        definitions,
                        drafts,
                        introduction,
                        conclusion,
                        build_citation_map(
                            current_review.cited_paper_ids,
                            metadata_by_paper_id,
                            state["citation_style"],
                        ),
                        citation_style=state["citation_style"],
                    )
                current_audit = current_audit.model_copy(
                    update={
                        "passed": current_audit.passed and semantic.passed,
                        "semantic_checked": True,
                        "semantic_issues": semantic.issues,
                        "revision_instructions": [
                            *current_audit.revision_instructions,
                            *semantic.revision_instructions,
                        ],
                        "visual_recommendations": semantic.visual_recommendations,
                    }
                )
            return current_review, current_audit

        review, audit = await assemble_and_audit()
        definition_by_id = {item.tag_id: item for item in definitions}
        editable_drafts = {
            tag_id: draft
            for tag_id, draft in drafts.items()
            if tag_id in resolved_tag_ids
            and definition_by_id[tag_id].node_type != "container"
        }
        contexts = {
            tag_id: SectionWritingContext.model_validate(
                store.read_json(f"section_contexts/{tag_id}.json")
            )
            for tag_id in editable_drafts
        }
        full_revision_round = 0
        while not audit.passed and full_revision_round < runtime.max_full_revision_rounds:
            try:
                revised_introduction, revised_sections, revised_conclusion = (
                    await revise_full_review(
                        introduction,
                        editable_drafts,
                        conclusion,
                        contexts,
                        audit,
                        model,
                    )
                )
            except Exception as error:
                audit = audit.model_copy(
                    update={
                        "passed": False,
                        "errors": [
                            *audit.errors,
                            f"Full revision failed: {type(error).__name__}: {error}",
                        ],
                        "revision_instructions": [
                            *audit.revision_instructions,
                            "Retry the bounded full-review revision.",
                        ],
                    }
                )
                full_revision_round += 1
                continue
            section_audits: dict[str, SectionAudit] = {}
            for tag_id, revised_draft in revised_sections.items():
                section_audit = audit_section(revised_draft, contexts[tag_id])
                if runtime.semantic_audits and section_audit.passed:
                    section_audit = await audit_section_semantics(
                        revised_draft, contexts[tag_id], model
                    )
                section_audits[tag_id] = section_audit
            invalid_sections = [
                tag_id
                for tag_id, section_audit in section_audits.items()
                if not section_audit.passed
            ]
            if not audit_section(revised_introduction, introduction_context).passed:
                invalid_sections.append("INTRODUCTION")
            if not audit_section(revised_conclusion, conclusion_context).passed:
                invalid_sections.append("CONCLUSION")
            if invalid_sections:
                audit = audit.model_copy(
                    update={
                        "passed": False,
                        "errors": [
                            *audit.errors,
                            "Full revision violated original section contexts: "
                            + ", ".join(invalid_sections),
                        ],
                        "revision_instructions": [
                            *audit.revision_instructions,
                            "Keep every revised section inside its original evidence context.",
                        ],
                    }
                )
                full_revision_round += 1
                continue

            introduction = revised_introduction
            conclusion = revised_conclusion
            editable_drafts = revised_sections
            drafts.update(revised_sections)
            revised_summary_by_id = {
                summary.tag_id: summary for summary in summaries
            }
            for tag_id, revised_draft in revised_sections.items():
                revised_summary_by_id[tag_id] = SectionSummary(
                    tag_id=tag_id,
                    summary=revised_draft.summary or revised_draft.content[:1200],
                    cited_paper_ids=revised_draft.cited_paper_ids,
                    used_point_ids=revised_draft.used_point_ids,
                )
                store.write_json(f"section_drafts/{tag_id}.json", _dump(revised_draft))
                store.write_json(
                    f"section_audits/{tag_id}.json",
                    {
                        "draft": revised_draft.model_dump(mode="json"),
                        "audits": [section_audits[tag_id].model_dump(mode="json")],
                        "resolved": True,
                        "unresolved_issues": [],
                    },
                )
                store.write_json(
                    f"section_summaries/{tag_id}.json",
                    _dump(revised_summary_by_id[tag_id]),
                )
            summaries = [
                revised_summary_by_id.get(summary.tag_id, summary) for summary in summaries
            ]
            review, audit = await assemble_and_audit()
            full_revision_round += 1

        introduction_path = store.write_json(
            "section_drafts/INTRODUCTION.json", _dump(introduction)
        )
        conclusion_path = store.write_json(
            "section_drafts/CONCLUSION.json", _dump(conclusion)
        )
        final_path = store.write_text("final_review.md", review.markdown)
        store.write_json(
            "references.json",
            cast(JsonValue, {
                "citation_style": state["citation_style"],
                "cited_paper_ids": review.cited_paper_ids,
                "references": review.references,
            }),
        )
        audit_path = store.write_json("full_review_audit.json", _dump(audit))
        visual_recommendations_path = store.write_json(
            "visual_recommendations.json",
            _dump_many(audit.visual_recommendations),
        )
        errors = [] if audit.passed else [
            "Full review audit failed: " + "; ".join(audit.revision_instructions)
        ]
        return {
            "introduction_path": introduction_path,
            "conclusion_path": conclusion_path,
            "final_review_path": final_path,
            "full_review_audit_path": audit_path,
            "visual_recommendations_path": visual_recommendations_path,
            "warnings": bookend_warnings,
            "errors": errors,
        }

    builder = StateGraph(ReviewState)
    builder.add_node("initialize", initialize)
    builder.add_node("define_tag_semantics", define_tags)
    builder.add_node("discover_documents", register_documents)
    builder.add_node("build_literature_card", build_card_worker)
    builder.add_node("build_tag_index", create_tag_index)
    builder.add_node("analyze_tag_coverage", analyze_coverage)
    builder.add_node("plan_writing_order", plan_sections)
    builder.add_node("write_section", write_next_section)
    builder.add_node("write_review", write_review)

    builder.add_edge(START, "initialize")
    builder.add_edge("initialize", "define_tag_semantics")
    builder.add_edge("define_tag_semantics", "discover_documents")
    builder.add_conditional_edges("discover_documents", dispatch_cards)
    builder.add_edge("build_literature_card", "build_tag_index")
    builder.add_edge("build_tag_index", "analyze_tag_coverage")
    builder.add_edge("analyze_tag_coverage", "plan_writing_order")
    builder.add_conditional_edges("plan_writing_order", route_to_section)
    builder.add_conditional_edges("write_section", continue_sections)
    builder.add_edge("write_review", END)
    return builder.compile(checkpointer=checkpointer)


async def run_review_async(
    request: ReviewInput,
    model: LanguageModel | None = None,
    *,
    config: ReviewConfig | None = None,
    run_id: str | None = None,
    document_parser: DocumentParser | None = None,
    outline_base_directory: str | Path | None = None,
) -> ReviewResult:
    """Run or resume an outline-driven review with a persistent SQLite checkpoint."""

    runtime = config or ReviewConfig()
    actual_run_id = run_id or uuid4().hex
    if not _RUN_ID.fullmatch(actual_run_id) or ".." in actual_run_id:
        raise ValueError("run_id contains unsafe characters")
    run_directory = (Path(request.output_directory) / actual_run_id).resolve()
    run_directory.mkdir(parents=True, exist_ok=True)
    store = LocalArtifactStore(run_directory)
    resolved_outline = resolve_outline_source(
        request.outline, base_directory=outline_base_directory
    )
    outline_snapshot: JsonValue = {
        "content": resolved_outline.content,
        "content_sha256": hashlib.sha256(
            resolved_outline.content.encode()
        ).hexdigest(),
        "source_path": resolved_outline.source_path,
    }
    request_payload = cast(JsonValue, request.model_dump(mode="json"))
    if store.exists("input.json") and store.read_json("input.json") != request_payload:
        raise ValueError(
            "run_id already exists with different inputs; use a new run_id"
        )
    store.write_json("input.json", request_payload)
    if (
        store.exists("outline_source.json")
        and store.read_json("outline_source.json") != outline_snapshot
    ):
        raise ValueError(
            "run_id already exists with a different resolved outline; use a new run_id"
        )
    store.write_json("outline_source.json", outline_snapshot)
    prepared_literature_directory = Path(request.literature_directory).resolve()
    preparation_warnings: tuple[str, ...] = ()
    if contains_pdf(prepared_literature_directory):
        if document_parser is None:
            from writing.adapters.mineru import MinerUDocumentParser

            auto_parser = MinerUDocumentParser.from_environment()
            try:
                preparation = await auto_parser.prepare_directory(
                    prepared_literature_directory,
                    run_directory / "parsed_literature",
                )
            finally:
                await auto_parser.aclose()
        else:
            preparation = await document_parser.prepare_directory(
                prepared_literature_directory,
                run_directory / "parsed_literature",
            )
        prepared_literature_directory = preparation.directory
        preparation_warnings = preparation.warnings
    checkpoint_path = run_directory / "checkpoints.sqlite"
    initial: ReviewState = {
        "run_id": actual_run_id,
        "review_question": request.review_question,
        "outline_source": resolved_outline.content,
        "literature_directory": str(prepared_literature_directory),
        "output_directory": request.output_directory,
        "output_language": request.output_language,
        "citation_style": request.citation_style,
        "target_words": request.target_words,
        "completed_card_paths": _reset_reduced_list(),
        "failed_paper_ids": _reset_reduced_list(),
        "completed_section_paths": _reset_reduced_list(),
        "failed_tag_ids": _reset_reduced_list(),
        "warnings": _reset_reduced_list(preparation_warnings),
        "errors": _reset_reduced_list(),
    }
    owns_model = model is None
    resolved_model = resolve_language_model(model)
    try:
        async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
            graph = build_review_graph(resolved_model, store, runtime, checkpointer)
            final = cast(
                ReviewState,
                await graph.ainvoke(
                    initial,
                    {
                        "configurable": {"thread_id": actual_run_id},
                        "recursion_limit": runtime.recursion_limit,
                        "max_concurrency": runtime.max_concurrency,
                    },
                ),
            )
    finally:
        if owns_model:
            await close_language_model(resolved_model)

    audit_passed = False
    if final.get("full_review_audit_path"):
        audit_passed = FullReviewAudit.model_validate(
            store.read_json(final["full_review_audit_path"])
        ).passed
    relative_final = final.get("final_review_path")
    return ReviewResult(
        run_id=actual_run_id,
        succeeded=bool(relative_final and audit_passed and not final.get("failed_tag_ids")),
        run_directory=str(run_directory),
        final_review_path=(
            str(run_directory / relative_final) if relative_final is not None else None
        ),
        warnings=_unique(final.get("warnings", [])),
        errors=_unique(final.get("errors", [])),
        failed_paper_ids=_unique(final.get("failed_paper_ids", [])),
        failed_tag_ids=_unique(final.get("failed_tag_ids", [])),
    )


def run_review(
    request: ReviewInput,
    model: LanguageModel | None = None,
    *,
    config: ReviewConfig | None = None,
    run_id: str | None = None,
    document_parser: DocumentParser | None = None,
    outline_base_directory: str | Path | None = None,
) -> ReviewResult:
    """Synchronous wrapper for environments without an active event loop."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            run_review_async(
                request,
                model,
                config=config,
                run_id=run_id,
                document_parser=document_parser,
                outline_base_directory=outline_base_directory,
            )
        )
    raise RuntimeError("run_review cannot run inside an event loop; await run_review_async")
