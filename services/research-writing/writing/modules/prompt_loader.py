"""Load role prompts with a shared editorial standard where appropriate."""

import re
from importlib.resources import files

_PROMPT_NAME = re.compile(r"^[a-z][a-z0-9_]*\.md$")
_EDITORIAL_PROMPTS = frozenset(
    {
        "write_leaf_section.md",
        "write_parent_intro.md",
        "write_introduction.md",
        "write_conclusion.md",
        "revise_section.md",
        "revise_full_review.md",
        "audit_section.md",
        "audit_full_review.md",
    }
)


def load_prompt(name: str) -> str:
    """Return one packaged prompt, prepending shared standards when required."""

    if _PROMPT_NAME.fullmatch(name) is None:
        raise ValueError(f"invalid prompt resource name: {name}")
    prompt_root = files("writing.prompts")
    role_prompt = prompt_root.joinpath(name).read_text(encoding="utf-8").strip()
    if name not in _EDITORIAL_PROMPTS:
        return role_prompt + "\n"
    editorial = prompt_root.joinpath("editorial_standard.md").read_text(
        encoding="utf-8"
    ).strip()
    return f"{editorial}\n\n## Node-specific task\n\n{role_prompt}\n"
