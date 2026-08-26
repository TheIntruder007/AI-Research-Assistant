"""Artifact persistence interface and local filesystem adapter."""

import json
from pathlib import Path
from typing import Protocol, TypeAlias
from uuid import uuid4

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class ArtifactStore(Protocol):
    """Persistence interface used by workflow modules."""

    def write_json(self, relative_path: str, value: JsonValue) -> str: ...

    def read_json(self, relative_path: str) -> JsonValue: ...

    def write_text(self, relative_path: str, value: str) -> str: ...

    def read_text(self, relative_path: str) -> str: ...

    def exists(self, relative_path: str) -> bool: ...


class LocalArtifactStore:
    """Persist UTF-8 artifacts below one run directory using atomic replacement."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _target(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise ValueError("artifact paths must be relative")
        target = (self._root / candidate).resolve()
        if not target.is_relative_to(self._root):
            raise ValueError("artifact path escapes the store root")
        return target

    @staticmethod
    def _replace_text(target: Path, value: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(value, encoding="utf-8", newline="\n")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def write_json(self, relative_path: str, value: JsonValue) -> str:
        target = self._target(relative_path)
        rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self._replace_text(target, rendered)
        return Path(relative_path).as_posix()

    def read_json(self, relative_path: str) -> JsonValue:
        value: JsonValue = json.loads(self._target(relative_path).read_text(encoding="utf-8"))
        return value

    def write_text(self, relative_path: str, value: str) -> str:
        self._replace_text(self._target(relative_path), value)
        return Path(relative_path).as_posix()

    def read_text(self, relative_path: str) -> str:
        return self._target(relative_path).read_text(encoding="utf-8")

    def exists(self, relative_path: str) -> bool:
        return self._target(relative_path).exists()
