"""ResearchGenie — console entry point.

    researchgenie          Run setup (first time only), then the research app.
    researchgenie config   Force the setup wizard to run again.

Everything downstream of "ready" reuses the existing, already-tested
pipeline (orchestrator.pipeline.run_pipeline) unchanged — this module is
purely the product/UX layer: config, provider readiness, and presentation.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Windows' legacy console API can't render some Unicode Rich uses (box-
# drawing characters, ✦, em dashes) — reconfigure stdout and steer Rich away
# from its legacy-console code path so a modern terminal renders correctly.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rich.console import Console  # noqa: E402
from rich.live import Live  # noqa: E402
from rich.prompt import Confirm, IntPrompt, Prompt  # noqa: E402

from orchestrator.pipeline import PipelineError, run_pipeline  # noqa: E402
from researchgenie import config as rg_config  # noqa: E402
from researchgenie import ollama_manager as om  # noqa: E402
from researchgenie.setup_wizard import run_setup_wizard  # noqa: E402
from researchgenie.theme import ERROR, MUTED, OK, WARN  # noqa: E402
from researchgenie.tui import PipelineView, render_banner, render_completion, render_failure, render_summary  # noqa: E402
from shared.contracts.pipeline_contract import ResearchRequest  # noqa: E402

_TARGET_FORMATS = ["IEEE", "Springer"]


def _ensure_ready(console: Console, config: rg_config.Config) -> bool:
    """Re-verifies the saved provider is actually ready right now (the
    Ollama server may not be running yet even though setup previously
    succeeded — e.g. after a reboot) and starts it automatically if not."""
    rg_config.apply_to_environment(config)
    if config.provider == "gemini":
        if not config.gemini_api_key:
            console.print(f"[{WARN}]No Gemini API key configured.[/{WARN}]")
            return False
        return True

    async def check_and_start() -> bool:
        if await om.is_ollama_server_running():
            return await om.is_model_installed(config.ollama_model)
        console.print(f"[{MUTED}]Starting Ollama...[/{MUTED}]")
        om.start_ollama_server()
        for _ in range(15):
            await asyncio.sleep(1)
            if await om.is_ollama_server_running():
                return await om.is_model_installed(config.ollama_model)
        return False

    ready = asyncio.run(check_and_start())
    if not ready:
        console.print(
            f"[{WARN}]Ollama isn't ready. Run `researchgenie config` to fix your setup.[/{WARN}]"
        )
    return ready


def _collect_request(console: Console) -> ResearchRequest:
    console.print()
    question = Prompt.ask("[bold]What are you researching?[/bold]")
    while not question.strip():
        question = Prompt.ask("[bold]What are you researching?[/bold]")

    corpus_size = IntPrompt.ask(
        "How many papers should the research corpus include? (6-9)", default=8,
    )
    corpus_size = max(6, min(9, corpus_size))

    console.print("Paper format: [1] IEEE  [2] Springer")
    format_choice = Prompt.ask("Select", choices=["1", "2"], default="1")
    target_format = "IEEE" if format_choice == "1" else "Springer"

    return ResearchRequest(
        research_question=question, corpus_size=corpus_size, target_format=target_format,
    )


def _provider_label(config: rg_config.Config) -> str:
    if config.provider == "gemini":
        return f"Gemini · {config.gemini_model}"
    return f"Ollama · {config.ollama_model}"


async def _run_research(console: Console, request: ResearchRequest) -> None:
    view = PipelineView()
    result = None
    error: PipelineError | None = None

    with Live(view.render(), console=console, refresh_per_second=6) as live:
        try:
            async for event in run_pipeline(request):
                if event["type"] == "result":
                    result = event["result"]
                else:
                    view.ingest(event)
                    live.update(view.render())
        except PipelineError as exc:
            error = exc

    if error is not None:
        # The orchestrator writes each completed stage's artifacts to disk
        # as it goes (see orchestrator/pipeline.py), so a partial run's work
        # is preserved under outputs/ even on failure — but the exact
        # directory isn't attached to PipelineError itself, so we can only
        # point the user to their run history rather than one exact path.
        render_failure(
            console, stage="unknown", reason=str(error),
            run_directory=str(ROOT / "outputs") + " (see the most recent run folder)",
        )
        return

    if result is None:
        render_failure(
            console, stage="unknown",
            reason="The pipeline finished without producing a result.",
            run_directory=None,
        )
        return

    artifacts = ["Research draft (Markdown)", "Quality report", "Citation validation report",
                "Reference list", "Run metadata"]
    if Path(result.run_directory, "final", "paper.tex").exists():
        artifacts.insert(0, "LaTeX source (paper.tex)")
    if Path(result.run_directory, "final", "paper.pdf").exists():
        artifacts.insert(0, "Compiled research paper (paper.pdf)")

    render_completion(
        console, run_directory=result.run_directory,
        overall_score=result.quality_assurance.scores.overall, artifacts=artifacts,
    )


def _run_app(console: Console, config: rg_config.Config) -> None:
    render_banner(console)
    console.print(f"[{OK}]Ready to research.[/{OK}]\n")
    request = _collect_request(console)
    render_summary(
        console, question=request.research_question, corpus_size=request.corpus_size,
        target_format=request.target_format, provider_label=_provider_label(config),
    )
    if not Confirm.ask("\n[bold]Start research?[/bold]", default=True):
        console.print(f"[{MUTED}]Cancelled.[/{MUTED}]")
        return
    asyncio.run(_run_research(console, request))


def main() -> None:
    console = Console(legacy_windows=False)
    args = sys.argv[1:]

    force_setup = bool(args) and args[0] == "config"
    if force_setup or not rg_config.is_setup_complete():
        config = run_setup_wizard(console)
        if not config.setup_complete:
            console.print(f"[{ERROR}]Setup did not complete. Run `researchgenie` to try again.[/{ERROR}]")
            sys.exit(1)
        if force_setup:
            return
    else:
        config = rg_config.load()

    if not _ensure_ready(console, config):
        sys.exit(1)

    _run_app(console, config)


if __name__ == "__main__":
    main()
