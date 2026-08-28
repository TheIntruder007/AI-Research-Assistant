"""One restrained color palette for the ResearchGenie terminal UI.

Explicit product requirement: modern and clean, not a "gaming terminal" —
one primary accent, one secondary/supporting color, neutral tones for
everything else. Used via Rich's markup (e.g. f"[{ACCENT}]text[/{ACCENT}]").
"""

ACCENT = "cyan"        # primary accent — headings, active state, key values
SECONDARY = "magenta"  # supporting accent — used sparingly (e.g. highlights)
OK = "green"           # success / completed state only
WARN = "yellow"        # warnings — never used for hard failures
ERROR = "red"          # failures only
MUTED = "grey62"       # secondary/explanatory text
