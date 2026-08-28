"""Tests for the deterministic Markdown -> LaTeX export."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.utilities.latex_export import compile_pdf, markdown_to_latex  # noqa: E402

_SAMPLE = """# What are the effects of X on Y?

> **AI-generated research draft for human review.** Not a verified publication.

## Introduction

Some introductory prose about X and Y (Smith, 2020).

## Literature Review

Findings from **multiple studies** show *mixed* results.

## References

- Smith, J. (2020). A study of X. Journal of Y.
- Jones, A. (2021). Another study. Journal of Z.
"""


def test_document_has_valid_structure():
    tex = markdown_to_latex(_SAMPLE, title="What are the effects of X on Y?")
    assert tex.startswith("\\documentclass")
    assert "\\begin{document}" in tex
    assert "\\end{document}" in tex
    assert tex.index("\\begin{document}") < tex.index("\\end{document}")


def test_h1_title_is_not_duplicated_as_a_section():
    tex = markdown_to_latex(_SAMPLE, title="What are the effects of X on Y?")
    assert "\\section{What are the effects" not in tex


def test_h2_headings_become_sections():
    tex = markdown_to_latex(_SAMPLE, title="Q")
    assert "\\section{Introduction}" in tex
    assert "\\section{Literature Review}" in tex


def test_blockquote_disclaimer_is_rendered_as_italic():
    tex = markdown_to_latex(_SAMPLE, title="Q")
    assert "\\textit{" in tex
    assert "AI-generated research draft" in tex


def test_bold_and_italic_markdown_are_converted():
    tex = markdown_to_latex(_SAMPLE, title="Q")
    assert "\\textbf{multiple studies}" in tex
    assert "\\textit{mixed}" in tex


def test_special_latex_characters_are_escaped():
    tex = markdown_to_latex("## Section\n\n100% of studies & 50\\% of others used $x_1$.\n", title="Q")
    assert "100\\% of studies \\& 50" in tex
    assert "\\$x" in tex


def test_reference_list_becomes_a_bibliography_block():
    tex = markdown_to_latex(_SAMPLE, title="Q")
    assert "\\begin{thebibliography}" in tex
    assert "\\bibitem{ref1}" in tex
    assert "\\bibitem{ref2}" in tex
    assert "Smith, J. (2020)" in tex


def test_document_with_no_references_omits_bibliography_block():
    tex = markdown_to_latex("# Q\n\n## Introduction\n\nSome text.\n", title="Q")
    assert "\\begin{thebibliography}" not in tex


def test_compile_pdf_returns_none_when_no_toolchain_available(tmp_path, monkeypatch):
    from shared.utilities import latex_export
    monkeypatch.setattr(latex_export.shutil, "which", lambda name: None)
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("\\documentclass{article}\\begin{document}x\\end{document}", encoding="utf-8")
    assert compile_pdf(tex_path, tmp_path) is None


def test_compile_pdf_returns_none_if_output_file_was_not_actually_produced(tmp_path, monkeypatch):
    """Never claim a PDF exists unless the compiler actually wrote one —
    even if the subprocess "succeeds" without producing output."""
    from shared.utilities import latex_export
    monkeypatch.setattr(latex_export.shutil, "which", lambda name: "tectonic" if name == "tectonic" else None)
    monkeypatch.setattr(latex_export.subprocess, "run", lambda *a, **k: None)
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("x", encoding="utf-8")
    assert compile_pdf(tex_path, tmp_path) is None
