import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from terminal_app.cli import collect_request_interactively  # noqa: E402


def test_collect_request_interactively_builds_request_from_prompts(monkeypatch):
    answers = iter([
        "What are the effects of X on Y?",  # research question
        "journal",                          # publication type
        "Springer Journal of Examples",     # target venue
        "APA",                              # target format
        "2026-12-01",                       # deadline
        "7",                                # corpus size
        "nutrition science",                # domain
        "en",                               # language
        "fasting, cognition",               # keywords
        "",                                 # excluded topics
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    request = collect_request_interactively()

    assert request.research_question == "What are the effects of X on Y?"
    assert request.publication_type == "journal"
    assert request.target_venue == "Springer Journal of Examples"
    assert request.target_format == "APA"
    assert request.deadline == "2026-12-01"
    assert request.corpus_size == 7
    assert request.domain == "nutrition science"
    assert request.keywords == ["fasting", "cognition"]
    assert request.excluded_topics == []


def test_collect_request_interactively_requires_format_other_name_when_other(monkeypatch):
    answers = iter([
        "Q?", "conference", "", "Other", "CustomStyle", "", "8", "", "en", "", "",
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    request = collect_request_interactively()
    assert request.target_format == "Other"
    assert request.format_other_name == "CustomStyle"
