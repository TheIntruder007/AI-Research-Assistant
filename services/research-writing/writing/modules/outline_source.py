"""Resolve an inline outline or a reference to a local outline file."""

import re
from dataclasses import dataclass
from pathlib import Path

_OUTLINE_FILE_SUFFIXES = frozenset({".md", ".markdown", ".txt"})
_EXPLICIT_INLINE_PREFIX = re.compile(
    r"^(?:#{1,6}[ \t]+|\d+(?:\.\d+)*(?:[.)])?[ \t]+|[-+*][ \t]+)"
)


class OutlineSourceError(ValueError):
    """Raised when an outline file reference cannot be read safely."""


@dataclass(frozen=True)
class ResolvedOutline:
    """Resolved outline text and its optional absolute source path."""

    content: str
    source_path: str | None


def _looks_like_path(source: str) -> bool:
    if (
        "\n" in source
        or "\r" in source
        or _EXPLICIT_INLINE_PREFIX.match(source.lstrip()) is not None
    ):
        return False
    candidate = Path(source)
    return (
        candidate.is_absolute()
        or candidate.suffix.casefold() in _OUTLINE_FILE_SUFFIXES
    )


def resolve_outline_source(
    source: str, *, base_directory: str | Path | None = None
) -> ResolvedOutline:
    """Return inline text or read a path relative to the supplied base directory."""

    if not _looks_like_path(source):
        return ResolvedOutline(content=source, source_path=None)

    candidate = Path(source).expanduser()
    if not candidate.is_absolute():
        base = Path.cwd() if base_directory is None else Path(base_directory)
        candidate = base / candidate
    path = candidate.resolve()
    if not path.exists():
        raise OutlineSourceError(f"outline file does not exist: {path}")
    if not path.is_file():
        raise OutlineSourceError(f"outline path is not a file: {path}")
    try:
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise OutlineSourceError(f"outline file could not be read: {path}") from error
    if not content.strip():
        raise OutlineSourceError(f"outline file is empty: {path}")
    return ResolvedOutline(content=content, source_path=str(path))
