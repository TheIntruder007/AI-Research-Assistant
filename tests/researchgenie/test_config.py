"""Tests for the local ResearchGenie config store."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from researchgenie import config as rg_config  # noqa: E402


def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(rg_config, "CONFIG_DIR", tmp_path / ".researchgenie")
    monkeypatch.setattr(rg_config, "CONFIG_PATH", tmp_path / ".researchgenie" / "config.json")
    return rg_config


def test_load_returns_defaults_when_no_config_file_exists(tmp_path, monkeypatch):
    mod = _isolated(tmp_path, monkeypatch)
    config = mod.load()
    assert config.setup_complete is False
    assert config.provider == "ollama"


def test_save_then_load_round_trips(tmp_path, monkeypatch):
    mod = _isolated(tmp_path, monkeypatch)
    original = mod.Config(setup_complete=True, provider="gemini", gemini_api_key="secret-key-123")
    mod.save(original)
    loaded = mod.load()
    assert loaded.setup_complete is True
    assert loaded.provider == "gemini"
    assert loaded.gemini_api_key == "secret-key-123"


def test_load_ignores_unknown_fields_and_corrupt_json(tmp_path, monkeypatch):
    mod = _isolated(tmp_path, monkeypatch)
    mod.CONFIG_DIR.mkdir(parents=True)
    mod.CONFIG_PATH.write_text("not valid json{{{", encoding="utf-8")
    config = mod.load()
    assert config == mod.Config()  # falls back to defaults, does not crash


def test_masked_summary_never_exposes_the_full_api_key(tmp_path, monkeypatch):
    mod = _isolated(tmp_path, monkeypatch)
    config = mod.Config(gemini_api_key="AIzaSyD-verysecretvalue1234567890")
    summary = config.masked_summary()
    assert "verysecretvalue1234567890" not in summary["gemini_api_key"]
    assert summary["gemini_api_key"].startswith("AIza")


def test_apply_to_environment_sets_expected_variables(tmp_path, monkeypatch):
    mod = _isolated(tmp_path, monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config = mod.Config(provider="gemini", gemini_api_key="k123", gemini_model="gemini-2.5-flash")
    mod.apply_to_environment(config)
    import os
    assert os.environ["AI_PROVIDER"] == "gemini"
    assert os.environ["GEMINI_API_KEY"] == "k123"
    assert os.environ["GEMINI_MODEL"] == "gemini-2.5-flash"


def test_is_setup_complete_reflects_saved_state(tmp_path, monkeypatch):
    mod = _isolated(tmp_path, monkeypatch)
    assert mod.is_setup_complete() is False
    mod.save(mod.Config(setup_complete=True))
    assert mod.is_setup_complete() is True
