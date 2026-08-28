"""Targeted reproduction/verification for the TAG-ROOT overlap fix (D-020).

Re-uses the exact literature files and tag tree from a real prior full-pipeline
run (the one documented in D-019/analytics_and_results.md whose P003 card
failed twice with ancestor/descendant duplication), and regenerates ONLY the
tag semantics + P003's card — a couple of LLM calls instead of a full 15+
minute pipeline run — to directly compare before/after without re-running
Discovery or every other paper's card.

Usage:
    python scripts/repro_tag_overlap.py <run_directory>

<run_directory> is a services/research-writing run directory (the one
containing tag_tree.json, literature/, manifest.json) — e.g. the
02_writing/<id> directory from a real orchestrator run.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "research-writing"))
sys.path.insert(0, str(ROOT))

from writing.adapters.ollama_model import create_ollama_model  # noqa: E402
from writing.modules.card_validation import validate_literature_card  # noqa: E402
from writing.modules.document_registry import discover_documents  # noqa: E402
from writing.modules.literature_card import build_literature_card  # noqa: E402
from writing.modules.tag_semantics import define_tag_semantics  # noqa: E402
from writing.schemas import OutlineNode  # noqa: E402


async def main(run_directory: str) -> None:
    run_dir = Path(run_directory)
    tree_raw = json.loads((run_dir / "tag_tree.json").read_text(encoding="utf-8"))
    tree = [OutlineNode.model_validate(item) for item in tree_raw]
    input_json = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    review_question = input_json["review_question"]
    documents = discover_documents(run_dir / "literature")
    p003 = next(d for d in documents if d.paper_id == "P003")
    print(f"Target paper: {p003.relative_path}\n")

    model = create_ollama_model()
    try:
        print("=== Regenerating tag semantics with the FIXED prompt ===")
        definitions = await define_tag_semantics(review_question, tree, model)
        root = next(d for d in definitions if d.tag_id == "TAG-ROOT")
        print(f"TAG-ROOT include_when (NEW):\n  " + "\n  ".join(root.include_when))
        print(f"TAG-ROOT exclude_when (NEW):\n  " + "\n  ".join(root.exclude_when))

        print("\n=== Building P003's literature card with NEW tag semantics ===")
        card = await build_literature_card(review_question, definitions, p003, model)
        audit = validate_literature_card(card, tree)
        print(f"passed: {audit.passed}")
        for error in audit.errors:
            print(f"  ERROR: {error}")
        if audit.passed:
            print("\nSUCCESS: no ancestor/descendant duplication with the new semantics.")
    finally:
        from writing.adapters.language_model import close_language_model
        await close_language_model(model)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
