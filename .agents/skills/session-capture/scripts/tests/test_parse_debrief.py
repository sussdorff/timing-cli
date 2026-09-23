#!/usr/bin/env python3
"""
Test suite for parse_debrief.py — stdin/stdout contract parser.

Run with:
    uv run pytest skills/session-capture/scripts/tests/test_parse_debrief.py -v
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

# Allow importing the module under test
sys.path.insert(0, str(Path(__file__).parent.parent))

import parse_debrief as parser


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FULL_VALID_DEBRIEF = """
### Debrief

#### Key Decisions
- Chose stdlib-only approach for portability
- Used regex for section parsing to avoid external deps

#### Challenges Encountered
- Embedded debrief in larger message requires careful heading detection
- Empty sections must return empty list, not error

#### Surprising Findings
- Agent messages often contain extra whitespace between headings
- Some agents omit the Debrief section entirely

#### Follow-up Items
- Consider adding support for nested bullet points
- May need to handle Unicode in section headings
""".strip()

DEBRIEF_EMBEDDED_IN_LARGER_MESSAGE = """
## Completion Report
- [x] Criterion 1: done
- [x] Criterion 2: done

## Summary
Implemented all acceptance criteria.

### Debrief

#### Key Decisions
- Used pathlib for all file operations
- Kept logic in pure functions for testability

#### Challenges Encountered
- Parsing nested sections was non-trivial

#### Surprising Findings
- None

#### Follow-up Items
- Add integration tests
""".strip()

DEBRIEF_WITH_EMPTY_SECTIONS = """
### Debrief

#### Key Decisions

#### Challenges Encountered
- One challenge found

#### Surprising Findings

#### Follow-up Items
""".strip()

NO_DEBRIEF_HEADING = """
## Summary
This response has no debrief section at all.

Some content here.
""".strip()

DEBRIEF_WITH_EXTRA_CONTENT_AFTER = """
### Debrief

#### Key Decisions
- Decision A

#### Challenges Encountered
- Challenge B

#### Surprising Findings
- Finding C

#### Follow-up Items
- Item D

## Some Other Section After
Content that should not be included.
""".strip()


# ---------------------------------------------------------------------------
# Unit tests for parse_debrief_text()
# ---------------------------------------------------------------------------

class TestParseDebriefText(unittest.TestCase):
    """Tests for the parser.parse_debrief_text() function."""

    def test_full_valid_debrief_all_sections(self):
        """A complete debrief with all four sections returns correct JSON."""
        result = parser.parse_debrief_text(FULL_VALID_DEBRIEF)
        self.assertIn("key_decisions", result)
        self.assertIn("challenges_encountered", result)
        self.assertIn("surprising_findings", result)
        self.assertIn("follow_up_items", result)
        # Verify content
        self.assertTrue(len(result["key_decisions"]) >= 2)
        self.assertIn("Chose stdlib-only approach for portability", result["key_decisions"][0])

    def test_debrief_embedded_in_larger_message(self):
        """Debrief embedded in a larger message is correctly extracted."""
        result = parser.parse_debrief_text(DEBRIEF_EMBEDDED_IN_LARGER_MESSAGE)
        self.assertIn("key_decisions", result)
        self.assertTrue(len(result["key_decisions"]) >= 1)
        self.assertIn("challenges_encountered", result)
        self.assertTrue(len(result["challenges_encountered"]) >= 1)

    def test_empty_sections_return_empty_lists(self):
        """Empty debrief sections return empty list, not an error."""
        result = parser.parse_debrief_text(DEBRIEF_WITH_EMPTY_SECTIONS)
        self.assertIsInstance(result["key_decisions"], list)
        self.assertEqual(result["key_decisions"], [])
        # Non-empty section still parsed correctly
        self.assertTrue(len(result["challenges_encountered"]) >= 1)
        self.assertIsInstance(result["surprising_findings"], list)
        self.assertEqual(result["surprising_findings"], [])
        self.assertIsInstance(result["follow_up_items"], list)
        self.assertEqual(result["follow_up_items"], [])

    def test_extra_content_after_debrief_is_ignored(self):
        """Content after the debrief block (h2/h3) does not pollute results."""
        result = parser.parse_debrief_text(DEBRIEF_WITH_EXTRA_CONTENT_AFTER)
        # Should only have the one item per section, not content from after
        self.assertEqual(len(result["key_decisions"]), 1)
        for item in result["key_decisions"]:
            self.assertNotIn("Some Other Section", item)

    def test_json_output_shape(self):
        """Output dict has exactly the four required keys."""
        result = parser.parse_debrief_text(FULL_VALID_DEBRIEF)
        self.assertEqual(set(result.keys()), {
            "key_decisions",
            "challenges_encountered",
            "surprising_findings",
            "follow_up_items",
        })
        for key in result:
            self.assertIsInstance(result[key], list)

    def test_bullet_items_stripped(self):
        """Bullet markers (- ) are stripped from items."""
        result = parser.parse_debrief_text(FULL_VALID_DEBRIEF)
        for item in result["key_decisions"]:
            self.assertFalse(item.startswith("- "), f"Item should not start with '- ': {item!r}")

    def test_surprising_findings_none_as_text(self):
        """'None' as a bullet item is returned as the string 'None'."""
        result = parser.parse_debrief_text(DEBRIEF_EMBEDDED_IN_LARGER_MESSAGE)
        # The embedded message has "- None" in Surprising Findings
        self.assertIn("None", result["surprising_findings"])


# ---------------------------------------------------------------------------
# Unit tests for parse_debrief_text() — missing heading
# ---------------------------------------------------------------------------

class TestMissingDebriefHeading(unittest.TestCase):

    def test_no_debrief_heading_raises_value_error(self):
        """parse_debrief_text() raises ValueError when no ### Debrief heading found."""
        with self.assertRaises(ValueError) as ctx:
            parser.parse_debrief_text(NO_DEBRIEF_HEADING)
        self.assertIn("Debrief", str(ctx.exception))


# ---------------------------------------------------------------------------
# CLI / subprocess tests
# ---------------------------------------------------------------------------

SCRIPT_PATH = str(Path(__file__).parent.parent / "parse_debrief.py")


class TestCLIContract(unittest.TestCase):
    """Tests the stdin→stdout contract of parse_debrief.py when run as a script."""

    def _run_script(self, stdin_text: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", SCRIPT_PATH],
            input=stdin_text,
            capture_output=True,
            text=True,
        )

    def test_valid_debrief_exits_zero(self):
        """Script exits 0 and outputs valid JSON for a valid debrief."""
        result = self._run_script(FULL_VALID_DEBRIEF)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertIn("key_decisions", data)

    def test_missing_heading_exits_nonzero(self):
        """Script exits non-zero when no ### Debrief heading is found."""
        result = self._run_script(NO_DEBRIEF_HEADING)
        self.assertNotEqual(result.returncode, 0)

    def test_output_is_valid_json(self):
        """stdout is valid JSON for a valid debrief."""
        result = self._run_script(FULL_VALID_DEBRIEF)
        self.assertEqual(result.returncode, 0)
        try:
            json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"Output is not valid JSON: {exc}\nOutput: {result.stdout!r}")

    def test_embedded_debrief_exits_zero(self):
        """Script exits 0 for debrief embedded in a larger message."""
        result = self._run_script(DEBRIEF_EMBEDDED_IN_LARGER_MESSAGE)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertTrue(len(data["key_decisions"]) >= 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
