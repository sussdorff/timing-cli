#!/usr/bin/env python3
"""
parse_debrief — Parse subagent debrief sections from message text.

Reads full subagent message from stdin, extracts the ### Debrief block,
and outputs structured JSON to stdout.

JSON shape:
    {
        "key_decisions": [...],
        "challenges_encountered": [...],
        "surprising_findings": [...],
        "follow_up_items": [...]
    }

Exit codes:
    0  Success (even if some sections are empty)
    1  Format violation (no ### Debrief heading found)

Usage:
    echo "<agent output>" | python3 parse_debrief.py
    cat agent_response.txt | python3 parse_debrief.py

Stdin/Stdout Contract:
    stdin:  Full subagent message text (may contain content before/after debrief)
    stdout: JSON object with the four debrief keys (lists of strings)
    stderr: Error message on format violation
"""

import json
import re
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------

# The four canonical heading names (matching session-close Step 11 taxonomy)
_SECTION_HEADINGS: dict[str, str] = {
    "key_decisions": "Key Decisions",
    "challenges_encountered": "Challenges Encountered",
    "surprising_findings": "Surprising Findings",
    "follow_up_items": "Follow-up Items",
}


def _extract_debrief_block(text: str) -> Optional[str]:
    """Extract the content of the ### Debrief block from text.

    Searches for '### Debrief' heading and returns everything until the
    next heading of the same or higher level (## or ###), or end of text.

    Args:
        text: Full message text that may contain a debrief section.

    Returns:
        The content of the debrief block (including its heading), or None if
        no '### Debrief' heading is found.
    """
    lines = text.splitlines()
    debrief_start: Optional[int] = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "### Debrief":
            debrief_start = i
            break

    if debrief_start is None:
        return None

    # Collect lines from debrief_start onward, stopping at next h2/h3 that
    # is NOT a #### subheading (i.e. ## or ### lines that start a new block)
    block_lines: list[str] = [lines[debrief_start]]
    for line in lines[debrief_start + 1 :]:
        stripped = line.strip()
        # Stop at next ## or ### heading (but not #### which are subsections)
        if re.match(r"^#{2,3}\s+\S", stripped) and not stripped.startswith("####"):
            break
        block_lines.append(line)

    return "\n".join(block_lines)


def _extract_h4_section(block: str, heading_name: str) -> list[str]:
    """Extract bullet items from an #### heading within a debrief block.

    Args:
        block: The debrief block text (from _extract_debrief_block).
        heading_name: The heading text to find (e.g. "Key Decisions").

    Returns:
        List of stripped bullet item strings (without leading "- " marker).
        Returns an empty list if the section is absent or has no bullets.
    """
    lines = block.splitlines()
    target_heading = f"#### {heading_name}"
    in_section = False
    items: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == target_heading:
            in_section = True
            continue
        if in_section:
            # Stop at any other #### heading (next subsection)
            if stripped.startswith("####"):
                break
            # Stop at ## or ### headings (parent level)
            if re.match(r"^#{2,3}\s+\S", stripped):
                break
            # Collect bullet items
            if stripped.startswith("- "):
                items.append(stripped[2:].strip())

    return items


def parse_debrief_text(text: str) -> dict[str, list[str]]:
    """Parse a debrief section from message text and return structured data.

    Args:
        text: Full message text containing a ### Debrief block.

    Returns:
        Dict with keys: key_decisions, challenges_encountered,
        surprising_findings, follow_up_items — each a list of strings.

    Raises:
        ValueError: If no '### Debrief' heading is found in text.
    """
    block = _extract_debrief_block(text)
    if block is None:
        raise ValueError(
            "No '### Debrief' heading found in message. "
            "Agent output must contain a '### Debrief' section."
        )

    return {
        key: _extract_h4_section(block, heading)
        for key, heading in _SECTION_HEADINGS.items()
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Read stdin, parse debrief, write JSON to stdout."""
    text = sys.stdin.read()
    try:
        result = parse_debrief_text(text)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
