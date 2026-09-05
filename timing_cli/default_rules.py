"""Packaged default classification rules for Malte's Cognovis setup.

Only ~15% of raw app activity is auto-assigned to a project by Timing's own
predicate rules, and most people won't hand-write a complete ``[[rules]]``
config on day one. ``DEFAULT_COGNOVIS_RULES`` is a ready-to-use ruleset that
maps common cmux/editor window titles and repo paths onto the Timing
projects Malte actually uses, so an empty user config still classifies most
of a normal workday.

Rules are ordered deliberately: specific client/product matches come first,
broad catch-alls (like ``app=cmux``) come last, since :class:`Classifier`
uses first-match-wins semantics. ``timing_cli.config.load_config`` appends
these *after* any explicit user ``[[rules]]`` (user rules always win) unless
``use_default_rules = false`` is set.

``title``/``path`` patterns here intentionally omit inline ``(?i)`` flags:
``Classifier`` already compiles every regex with ``re.IGNORECASE``.
"""

from __future__ import annotations

from timing_cli.config import Rule

# MIRA: Malte's Polaris work. There is no Timing project literally named
# "Polaris" -- it is tracked as "MIRA" locally.
_MIRA_RULES = [
    Rule(
        project="MIRA",
        title=r"(polaris|mira|diagnos|isynet|patient|anonymiz|de[- ]?id|gc50)",
    ),
    Rule(project="MIRA", path=r"(polaris|mira)"),
]

# Client / product projects: matched on window title keywords. Short
# acronyms use word boundaries to avoid matching inside unrelated words.
_CLIENT_RULES = [
    Rule(project="Syntegon", title=r"syntegon"),
    Rule(project="Romelag", title=r"romelag"),
    Rule(project="MCN", title=r"\bmcn\b"),
    Rule(project="ATR", title=r"\batr\b"),
    Rule(project="C4B", title=r"\bc4b\b"),
    Rule(project="NTS", title=r"\bnts\b"),
    Rule(project="BBW", title=r"\bbbw\b"),
    Rule(project="Kolibri", title=r"kolibri"),
    Rule(project="FUD", title=r"\bfud\b"),
    Rule(project="Eubylon", title=r"eubylon"),
    Rule(project="Solutio", title=r"solutio"),
    Rule(project="DST", title=r"\bdst\b"),
    Rule(project="Agiler Norden", title=r"agiler"),
]

_PROJECT_OPEN_RULES = [
    Rule(project="]project-open[", title=r"project-open"),
    Rule(project="]project-open[", path=r"project-open"),
]

_HOME_ELECTRONIC_RULES = [
    Rule(project="Home Electronic", title=r"home-infra|open-brain"),
    Rule(project="Home Electronic", path=r"home-infra|open-brain"),
]

# cognovis Verwaltung: internal tooling, admin, and agent-skill work that
# doesn't belong to a specific client. The `app=cmux` rule is a broad
# catch-all and MUST stay last so specific client rules above get a chance
# to match cmux window titles first.
_COGNOVIS_VERWALTUNG_RULES = [
    Rule(
        project="cognovis Verwaltung",
        title=r"timing-cli|collmex|paperless|invoice|rechnung|library|beads?|claude|codex|agent|skill|acp",
    ),
    Rule(
        project="cognovis Verwaltung",
        path=r"code/(cli-tools|library|timing-cli|collmex-cli|mm-cli)|\.agents|/skills/",
    ),
    Rule(project="cognovis Verwaltung", app="cmux"),
]

DEFAULT_COGNOVIS_RULES: list[Rule] = [
    *_MIRA_RULES,
    *_CLIENT_RULES,
    *_PROJECT_OPEN_RULES,
    *_HOME_ELECTRONIC_RULES,
    *_COGNOVIS_VERWALTUNG_RULES,
]
