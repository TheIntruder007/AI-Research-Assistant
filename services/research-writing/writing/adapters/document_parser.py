"""Document-parsing seam used before the review graph starts."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class PreparedLiterature:
    """Markdown directory plus non-fatal source parsing warnings."""

    directory: Path
    warnings: tuple[str, ...] = ()
    failed_sources: tuple[str, ...] = ()


class DocumentParser(Protocol):
    """Prepare a Markdown-only literature directory for the workflow."""

    async def prepare_directory(
        self, source_directory: str | Path, target_directory: str | Path
    ) -> PreparedLiterature: ...


def contains_pdf(directory: str | Path) -> bool:
    """Return whether a literature directory contains at least one PDF."""

    root = Path(directory)
    return root.is_dir() and any(
        path.is_file() and path.suffix.lower() == ".pdf" for path in root.rglob("*")
    )
