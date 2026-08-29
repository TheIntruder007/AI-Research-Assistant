"""Deterministic Markdown → LaTeX export for the final research draft.

No LLM involved — this is a pure, testable text transformation of the
already-finished, human-reviewed Markdown draft into a compilable LaTeX
source file, plus a best-effort PDF compile if a LaTeX toolchain
(`pdflatex` or `tectonic`) is available on the host machine.

Scope, stated honestly: this handles the specific, limited Markdown shape
the writing pipeline actually produces (headings, plain paragraphs,
blockquote disclaimer, bullet reference list) — it is not a general-purpose
Markdown-to-LaTeX converter and does not attempt to handle arbitrary
Markdown (tables, images, nested lists, code blocks).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

_ESCAPE_MAP = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_ESCAPE_RE = re.compile("|".join(re.escape(char) for char in _ESCAPE_MAP))
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+?)\*(?!\*)")


def _escape(text: str) -> str:
    return _ESCAPE_RE.sub(lambda m: _ESCAPE_MAP[m.group(0)], text)


def _inline_formatting(text: str) -> str:
    escaped = _escape(text)
    escaped = _BOLD_RE.sub(r"\\textbf{\1}", escaped)
    escaped = _ITALIC_RE.sub(r"\\textit{\1}", escaped)
    return escaped


# Format-specific LaTeX preamble/front-matter. Only the two formats the
# product actually asks a user to choose between (IEEE vs Springer — see
# ResearchRequest.target_format and DECISIONS.md D-026) get a dedicated
# publisher document class; anything else (ACM/APA/Other) keeps the
# original, always-compilable plain `article` class rather than guessing at
# an unverified template. Springer's actual "svjour3" class is not available
# in tectonic's bundled TeX distribution (confirmed by direct test); `llncs`
# (Springer's real, standard Lecture Notes in Computer Science class) is
# used instead as a genuine, compiling Springer template — documented
# honestly here rather than silently substituted.
_DOCUMENT_CLASSES: dict[str, str] = {
    "IEEE": "\\documentclass[conference]{IEEEtran}\n",
    "Springer": "\\documentclass{llncs}\n",
}
_DEFAULT_DOCUMENT_CLASS = "\\documentclass[11pt]{article}\n"


def _front_matter(target_format: str, title: str) -> str:
    escaped_title = _inline_formatting(title)
    if target_format == "IEEE":
        return (
            f"\\title{{{escaped_title}}}\n"
            "\\author{\\IEEEauthorblockN{ResearchGenie}"
            "\\IEEEauthorblockA{AI-generated research draft}}\n"
        )
    if target_format == "Springer":
        return (
            f"\\title{{{escaped_title}}}\n"
            "\\author{ResearchGenie}\n"
            "\\institute{AI-generated research draft}\n"
        )
    return f"\\title{{{escaped_title}}}\n\\date{{}}\n"


def markdown_to_latex(markdown: str, *, title: str, target_format: str = "Other") -> str:
    """Converts the pipeline's known draft shape into a compilable LaTeX
    document. `target_format` selects the publisher document class ("IEEE"
    -> IEEEtran, "Springer" -> llncs); anything else keeps the original
    plain `article` class. References are rendered as a `thebibliography`
    block from the trailing "## References" section's bullet list, if
    present — `thebibliography` is supported by all three classes, so no
    format-specific bibliography handling is needed."""
    lines = markdown.splitlines()
    body: list[str] = []
    references: list[str] = []
    in_references = False
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            body.append(" ".join(paragraph))
            body.append("")
            paragraph.clear()

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            flush_paragraph()
            continue
        if line.startswith("# "):
            continue  # the document title is set separately, not repeated as a section
        if line.startswith("## References"):
            flush_paragraph()
            in_references = True
            continue
        if in_references:
            if line.startswith("- "):
                references.append(_inline_formatting(line[2:].strip()))
            continue
        if line.startswith("## "):
            flush_paragraph()
            body.append(f"\\section{{{_inline_formatting(line[3:].strip())}}}")
            continue
        if line.startswith("### "):
            flush_paragraph()
            body.append(f"\\subsection{{{_inline_formatting(line[4:].strip())}}}")
            continue
        if line.startswith("> "):
            flush_paragraph()
            body.append(f"\\textit{{{_inline_formatting(line[2:].strip())}}}\\par")
            body.append("")
            continue
        if line.startswith("- "):
            flush_paragraph()
            body.append(f"\\begin{{itemize}}\\item {_inline_formatting(line[2:].strip())}\\end{{itemize}}")
            continue
        paragraph.append(_inline_formatting(line.strip()))
    flush_paragraph()

    bibliography = ""
    if references:
        items = "\n".join(f"\\bibitem{{ref{i}}} {entry}" for i, entry in enumerate(references, start=1))
        bibliography = (
            "\n\\begin{thebibliography}{99}\n" + items + "\n\\end{thebibliography}\n"
        )

    document_class = _DOCUMENT_CLASSES.get(target_format, _DEFAULT_DOCUMENT_CLASS)
    # `geometry` is redundant with (and can warn under) IEEEtran/llncs, which
    # already set their own publisher-defined page layout — only the plain
    # `article` fallback needs it.
    geometry = "" if target_format in _DOCUMENT_CLASSES else "\\usepackage[margin=1in]{geometry}\n"
    return (
        document_class
        + "\\usepackage[utf8]{inputenc}\n"
        + geometry
        + "\\usepackage{hyperref}\n"
        + _front_matter(target_format, title)
        + "\\begin{document}\n"
        "\\maketitle\n"
        + "\n".join(body)
        + bibliography
        + "\n\\end{document}\n"
    )


def compile_pdf(tex_path: Path, output_dir: Path) -> Path | None:
    """Best-effort PDF compilation. Returns the compiled PDF's path on
    success, or None if no supported LaTeX toolchain is available or
    compilation fails — never raises, and never claims a PDF exists unless
    it was actually written by the compiler."""
    if shutil.which("tectonic"):
        command = ["tectonic", "--outdir", str(output_dir), str(tex_path)]
    elif shutil.which("pdflatex"):
        command = [
            "pdflatex", "-interaction=nonstopmode", "-halt-on-error",
            f"-output-directory={output_dir}", str(tex_path),
        ]
    else:
        return None

    try:
        # pdflatex needs two passes to resolve the bibliography numbering;
        # tectonic handles this internally in one invocation but a second,
        # harmless run is not attempted for it.
        passes = 1 if command[0] == "tectonic" else 2
        # tectonic's very first run on a machine downloads its TeX resource
        # bundle (cached afterward) — a real, observed run took several
        # minutes for that reason alone before any actual typesetting
        # started. 300s gives room for that one-time cost; cached runs
        # finish in a few seconds.
        for _ in range(passes):
            subprocess.run(command, capture_output=True, timeout=300, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None

    pdf_path = output_dir / (tex_path.stem + ".pdf")
    return pdf_path if pdf_path.exists() else None
