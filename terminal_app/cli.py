"""Terminal application — the current user-facing interface to the pipeline.

Usage:
    python terminal_app/cli.py                        # interactive prompts
    python terminal_app/cli.py "Your research question here"   # non-interactive, defaults for the rest
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.pipeline import run_pipeline  # noqa: E402
from shared.contracts.pipeline_contract import ResearchRequest  # noqa: E402

_TARGET_FORMATS = ("IEEE", "Springer", "ACM", "APA", "Other")
_PUBLICATION_TYPES = ("conference", "journal", "other")


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def _prompt_choice(label: str, choices: tuple[str, ...], default: str) -> str:
    value = _prompt(f"{label} ({'/'.join(choices)})", default)
    return value if value in choices else default


def _prompt_int(label: str, default: int, *, minimum: int, maximum: int) -> int:
    while True:
        raw = _prompt(label, str(default))
        try:
            value = int(raw)
        except ValueError:
            print(f"  Please enter a whole number between {minimum} and {maximum}.")
            continue
        if minimum <= value <= maximum:
            return value
        print(f"  Please enter a number between {minimum} and {maximum}.")


def _prompt_list(label: str) -> list[str]:
    raw = _prompt(f"{label} (comma-separated, optional)")
    return [item.strip() for item in raw.split(",") if item.strip()] if raw else []


def collect_request_interactively() -> ResearchRequest:
    print("=== AI Research Assistant — New Research Run ===\n")
    research_question = ""
    while not research_question:
        research_question = _prompt("What research problem do you want to investigate?")

    publication_type = _prompt_choice("Target publication type", _PUBLICATION_TYPES, "conference")
    target_venue = _prompt("Target venue (e.g. 'IEEE International Conference on ...')") or None
    target_format = _prompt_choice("Target format", _TARGET_FORMATS, "IEEE")
    format_other_name = None
    if target_format == "Other":
        while not format_other_name:
            format_other_name = _prompt("Name of the target format")
    deadline = _prompt("Submission deadline (optional, any format)") or None
    corpus_size = _prompt_int("Number of papers for the research corpus", 8, minimum=6, maximum=9)

    domain = _prompt("Research domain (optional)") or None
    language = _prompt("Output language", "en")
    keywords = _prompt_list("Keywords")
    excluded_topics = _prompt_list("Excluded topics")

    return ResearchRequest(
        research_question=research_question,
        publication_type=publication_type,  # type: ignore[arg-type]
        target_venue=target_venue,
        target_format=target_format,  # type: ignore[arg-type]
        format_other_name=format_other_name,
        deadline=deadline,
        corpus_size=corpus_size,
        domain=domain,
        language=language,
        keywords=keywords,
        excluded_topics=excluded_topics,
    )


def _print_event(event: dict) -> None:
    print(f"{event['emoji']} [{event['stage']}] {event['message']}")


async def run(request: ResearchRequest) -> None:
    async for event in run_pipeline(request):
        if event["type"] == "result":
            result = event["result"]
            print("\n=== RESEARCH RUN COMPLETE ===")
            print(f"Run ID: {result.run_id}")
            print(f"Saved to: {result.run_directory}")
            print(
                f"Timings — discovery: {result.timings.discovery_seconds}s, "
                f"writing: {result.timings.writing_seconds}s, "
                f"verification: {result.timings.verification_seconds}s, "
                f"quality assurance: {result.timings.quality_assurance_seconds}s"
            )
            print(f"Overall quality score: {result.quality_assurance.scores.overall:.1f}/5.0")
            print(f"\nFinal draft: {result.run_directory}\\final\\draft.md")
            print(f"Quality report: {result.run_directory}\\final\\quality_report.md")
        else:
            _print_event(event)


def main() -> None:
    args = sys.argv[1:]
    if args:
        request = ResearchRequest(research_question=" ".join(args))
    else:
        request = collect_request_interactively()
    asyncio.run(run(request))


if __name__ == "__main__":
    main()
