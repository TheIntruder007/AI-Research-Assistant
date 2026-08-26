import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.utilities import llm_provider


def test_default_model_env_override(monkeypatch):
    monkeypatch.setenv("LOCAL_AI_MODEL", "qwen3.5:9b")
    import importlib
    importlib.reload(llm_provider)
    assert llm_provider.DEFAULT_MODEL == "qwen3.5:9b"


def test_completion_defaults_to_end_stop():
    comp = llm_provider.Completion()
    assert comp.stop == "end"
    assert comp.text == ""
