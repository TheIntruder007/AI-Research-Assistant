"""Parse a user-authored outline without interpreting its semantics."""

import re

from writing.schemas import ParsedHeading

_MARKDOWN_HEADING = re.compile(r"^(?P<marks>#{1,6})[ \t]+(?P<title>.+?)[ \t]*#*[ \t]*$")
_NUMBERED_HEADING = re.compile(
    r"^(?P<number>\d+(?:\.\d+)*)(?:[.)])?[ \t]+(?P<title>\S.*)$"
)
_LIST_MARKER = re.compile(r"^[-+*][ \t]+")


class OutlineStructureError(ValueError):
    """Raised when an outline cannot be mapped to a reliable hierarchy."""


def _validate_levels(headings: list[ParsedHeading]) -> list[ParsedHeading]:
    previous_level = 0
    for heading in headings:
        if heading.level > previous_level + 1:
            raise OutlineStructureError(
                f"illegal level jump from {previous_level} to {heading.level}: {heading.title}"
            )
        previous_level = heading.level
    return headings


def parse_outline(source: str) -> list[ParsedHeading]:
    """Return Markdown headings in their original order.

    This initial parsing path deliberately performs no semantic rewriting.
    """

    raw_lines = [line.rstrip() for line in source.splitlines() if line.strip()]
    lines = [line.strip() for line in raw_lines]
    markdown_matches = [_MARKDOWN_HEADING.fullmatch(line) for line in lines]
    if any(match is not None for match in markdown_matches):
        has_markdown_root = any(
            match is not None and len(match.group("marks")) == 1
            for match in markdown_matches
        )
        headings: list[ParsedHeading] = []
        for line, markdown_match in zip(lines, markdown_matches, strict=True):
            if markdown_match is not None:
                headings.append(
                    ParsedHeading(
                        level=len(markdown_match.group("marks")),
                        title=markdown_match.group("title").strip(),
                    )
                )
                continue
            numbered_match = _NUMBERED_HEADING.fullmatch(line)
            if numbered_match is not None:
                number = numbered_match.group("number")
                headings.append(
                    ParsedHeading(
                        level=number.count(".") + 1 + int(has_markdown_root),
                        number=number,
                        title=numbered_match.group("title").strip(),
                    )
                )
                continue
            raise OutlineStructureError(f"unrecognized outline line: {line}")
        return _validate_levels(headings)

    numbered_matches = [_NUMBERED_HEADING.fullmatch(line) for line in lines]
    if numbered_matches and all(match is not None for match in numbered_matches):
        headings = []
        for match in numbered_matches:
            assert match is not None
            number = match.group("number")
            headings.append(
                ParsedHeading(
                    level=number.count(".") + 1,
                    number=number,
                    title=match.group("title").strip(),
                )
            )
        return _validate_levels(headings)

    if (
        len(numbered_matches) > 1
        and numbered_matches[0] is None
        and all(match is not None for match in numbered_matches[1:])
    ):
        headings = [ParsedHeading(level=1, title=lines[0])]
        for match in numbered_matches[1:]:
            assert match is not None
            number = match.group("number")
            headings.append(
                ParsedHeading(
                    level=number.count(".") + 2,
                    number=number,
                    title=match.group("title").strip(),
                )
            )
        return _validate_levels(headings)

    if not raw_lines:
        raise OutlineStructureError("outline is empty")

    indent_stack: list[int] = []
    headings = []
    for raw_line in raw_lines:
        expanded = raw_line.expandtabs(4)
        indent = len(expanded) - len(expanded.lstrip(" "))
        if not indent_stack:
            if indent != 0:
                raise OutlineStructureError("the first outline level must not be indented")
            indent_stack.append(indent)
        elif indent > indent_stack[-1]:
            indent_stack.append(indent)
        elif indent < indent_stack[-1]:
            if indent not in indent_stack:
                raise OutlineStructureError(f"inconsistent indentation at: {raw_line.strip()}")
            indent_stack = indent_stack[: indent_stack.index(indent) + 1]

        title = _LIST_MARKER.sub("", expanded.strip()).strip()
        if not title:
            raise OutlineStructureError("outline contains an empty title")
        headings.append(ParsedHeading(level=len(indent_stack), title=title))

    return _validate_levels(headings)
