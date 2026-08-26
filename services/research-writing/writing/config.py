"""Runtime controls that do not change review semantics."""

from pydantic import Field

from writing.schemas import StrictModel


class ReviewConfig(StrictModel):
    """Bounded retries and graph execution controls."""

    max_section_revision_rounds: int = Field(default=2, ge=0)
    max_section_attempts: int = Field(default=2, ge=1)
    max_full_revision_rounds: int = Field(default=2, ge=0)
    max_card_attempts: int = Field(default=2, ge=1)
    recursion_limit: int = Field(default=1000, ge=10)
    max_concurrency: int = Field(default=8, ge=1)
    semantic_audits: bool = False
