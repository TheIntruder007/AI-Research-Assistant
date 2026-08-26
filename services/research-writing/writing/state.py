"""Lightweight LangGraph state containing artifact paths and IDs, not paper text."""

import operator
from typing import Annotated, TypedDict


class ReviewState(TypedDict, total=False):
    run_id: str
    review_question: str
    outline_source: str
    literature_directory: str
    output_directory: str
    output_language: str
    citation_style: str
    target_words: int | None

    input_path: str
    tag_tree_path: str
    tag_definitions_path: str
    manifest_path: str

    paper_ids: list[str]
    completed_card_paths: Annotated[list[str], operator.add]
    failed_paper_ids: Annotated[list[str], operator.add]

    tag_index_path: str
    coverage_report_path: str

    writing_order: list[str]
    next_section_index: int
    completed_section_paths: Annotated[list[str], operator.add]
    failed_tag_ids: Annotated[list[str], operator.add]

    introduction_path: str
    conclusion_path: str
    full_review_audit_path: str
    visual_recommendations_path: str
    final_review_path: str
    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]

    worker_document: dict[str, object]
