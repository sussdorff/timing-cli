#!/usr/bin/env python3
"""
Test suite for check-debrief-adherence.py — agent debrief block lint checker.

Run with:
    uv run pytest skills/session-capture/scripts/tests/test_check_debrief_adherence.py -v
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Allow importing the module under test (hyphenated filename requires importlib)
import importlib.util

_SCRIPT_PATH = Path(__file__).parent.parent / "check-debrief-adherence.py"
_spec = importlib.util.spec_from_file_location("check_debrief_adherence", _SCRIPT_PATH)
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)


# ---------------------------------------------------------------------------
# Fixtures: agent .md content
# ---------------------------------------------------------------------------

CONFORMING_AGENT_MD = """---
name: implementer
description: Test agent
tools: Read, Bash
---

# Purpose

Does implementation.

### Debrief

#### Key Decisions
- <decisions made>

#### Challenges Encountered
- <challenges>

#### Surprising Findings
- <surprises>

#### Follow-up Items
- <follow-ups>
"""

MISSING_ONE_SECTION_MD = """---
name: implementer
description: Test agent
tools: Read, Bash
---

# Purpose

Does implementation.

### Debrief

#### Key Decisions
- <decisions made>

#### Challenges Encountered
- <challenges>

#### Surprising Findings
- <surprises>

(Note: Follow-up Items heading is MISSING)
"""

MISSING_DEBRIEF_ENTIRELY = """---
name: implementer
description: Test agent
tools: Read, Bash
---

# Purpose

Does implementation without any debrief section.
"""

EXEMPT_AGENT_MD = """---
name: explorer
description: Exempt agent
tools: Read, Bash
---

# Purpose

Explores without debrief contract.
"""

CONFORMING_REVIEW_AGENT_MD = """---
name: review-agent
description: Code reviewer
tools: Read, Bash
---

# Review Agent

Reviews code.

### Debrief

#### Key Decisions
- <key decisions>

#### Challenges Encountered
- <challenges>

#### Surprising Findings
- <surprising findings>

#### Follow-up Items
- <follow-up items>
"""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _write_agent_file(directory: Path, filename: str, content: str) -> Path:
    """Write a mock agent file into an agents/ subdirectory."""
    agents_dir = directory / "agents"
    agents_dir.mkdir(exist_ok=True)
    path = agents_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Unit tests for has_debrief_template()
# ---------------------------------------------------------------------------

class TestHasDebriefTemplate(unittest.TestCase):

    def test_conforming_agent_passes(self):
        """Agent with all four #### headings inside ### Debrief block passes."""
        result = checker.has_debrief_template(CONFORMING_AGENT_MD)
        self.assertTrue(result, "Conforming agent should pass debrief check")

    def test_missing_one_section_fails(self):
        """Agent missing one of the four required headings fails."""
        result = checker.has_debrief_template(MISSING_ONE_SECTION_MD)
        self.assertFalse(result, "Agent missing Follow-up Items heading should fail")

    def test_no_debrief_section_fails(self):
        """Agent with no ### Debrief block at all fails."""
        result = checker.has_debrief_template(MISSING_DEBRIEF_ENTIRELY)
        self.assertFalse(result, "Agent with no debrief section should fail")

    def test_review_agent_conforming_passes(self):
        """review-agent with all four headings passes."""
        result = checker.has_debrief_template(CONFORMING_REVIEW_AGENT_MD)
        self.assertTrue(result, "review-agent with all headings should pass")


# ---------------------------------------------------------------------------
# Unit tests for missing_sections()
# ---------------------------------------------------------------------------

class TestMissingSections(unittest.TestCase):

    def test_no_missing_sections_for_conforming(self):
        """Conforming agent has no missing sections."""
        missing = checker.missing_sections(CONFORMING_AGENT_MD)
        self.assertEqual(missing, [])

    def test_detects_missing_follow_up_items(self):
        """Returns 'Follow-up Items' for the partial agent."""
        missing = checker.missing_sections(MISSING_ONE_SECTION_MD)
        self.assertIn("Follow-up Items", missing)

    def test_detects_all_missing_when_no_debrief(self):
        """Returns all four headings when debrief block is absent."""
        missing = checker.missing_sections(MISSING_DEBRIEF_ENTIRELY)
        self.assertIn("Key Decisions", missing)
        self.assertIn("Challenges Encountered", missing)
        self.assertIn("Surprising Findings", missing)
        self.assertIn("Follow-up Items", missing)


# ---------------------------------------------------------------------------
# Unit tests for load_exemptions()
# ---------------------------------------------------------------------------

class TestLoadExemptions(unittest.TestCase):

    def test_returns_default_when_no_standard_doc(self):
        """Falls back to hardcoded exemption list when standard doc not found."""
        exemptions = checker.load_exemptions(Path("/nonexistent/debrief-contract.md"))
        self.assertIsInstance(exemptions, set)
        self.assertIn("explorer", exemptions)
        self.assertIn("researcher", exemptions)
        self.assertIn("bead-orchestrator", exemptions)

    def test_loads_from_standard_doc(self):
        """Reads exemptions from the allowlist section in the standard doc."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("""
# Standard doc

## Agent Allowlist (Exempt from Debrief Contract)

- explorer
- custom-exempt-agent
- another-exempt
""")
            tmp_path = Path(f.name)

        try:
            exemptions = checker.load_exemptions(tmp_path)
            self.assertIn("explorer", exemptions)
            self.assertIn("custom-exempt-agent", exemptions)
            self.assertIn("another-exempt", exemptions)
        finally:
            tmp_path.unlink()


# ---------------------------------------------------------------------------
# Unit tests for check_agents_dir()
# ---------------------------------------------------------------------------

class TestCheckAgentsDir(unittest.TestCase):

    def test_conforming_agent_passes(self):
        """Conforming agent produces no violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_agent_file(Path(tmpdir), "implementer.md", CONFORMING_AGENT_MD)
            violations = checker.check_agents_dir(
                Path(tmpdir),
                exemptions=set(),
            )
        self.assertEqual(violations, [])

    def test_missing_section_produces_violation(self):
        """Agent missing Follow-up Items produces a violation entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_agent_file(Path(tmpdir), "implementer.md", MISSING_ONE_SECTION_MD)
            violations = checker.check_agents_dir(
                Path(tmpdir),
                exemptions=set(),
            )
        self.assertTrue(len(violations) >= 1)
        agent_names = [v["agent"] for v in violations]
        self.assertIn("implementer", agent_names)
        # Check that missing sections are reported
        missing = violations[0]["missing"]
        self.assertIn("Follow-up Items", missing)

    def test_exempt_agent_skipped(self):
        """Allowlisted agent is not checked even if it lacks debrief template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_agent_file(Path(tmpdir), "explorer.md", EXEMPT_AGENT_MD)
            violations = checker.check_agents_dir(
                Path(tmpdir),
                exemptions={"explorer"},
            )
        self.assertEqual(violations, [], "Exempt agent should produce no violation")

    def test_mixed_directory(self):
        """Conforming + missing + exempt: only the non-conforming non-exempt fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_agent_file(Path(tmpdir), "implementer.md", MISSING_ONE_SECTION_MD)
            _write_agent_file(Path(tmpdir), "review-agent.md", CONFORMING_REVIEW_AGENT_MD)
            _write_agent_file(Path(tmpdir), "explorer.md", EXEMPT_AGENT_MD)
            violations = checker.check_agents_dir(
                Path(tmpdir),
                exemptions={"explorer"},
            )
        # Only implementer should fail
        agent_names = [v["agent"] for v in violations]
        self.assertIn("implementer", agent_names)
        self.assertNotIn("review-agent", agent_names)
        self.assertNotIn("explorer", agent_names)


# ---------------------------------------------------------------------------
# CLI / subprocess integration tests
# ---------------------------------------------------------------------------

SCRIPT_PATH = str(Path(__file__).parent.parent / "check-debrief-adherence.py")


class TestCLIContract(unittest.TestCase):
    """Tests the CLI behavior of check-debrief-adherence.py."""

    def _run_script(self, search_path: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", SCRIPT_PATH, "--search-path", search_path],
            capture_output=True,
            text=True,
        )

    def test_all_conforming_exits_zero(self):
        """Script exits 0 when all non-exempt agents are conforming."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_agent_file(Path(tmpdir), "implementer.md", CONFORMING_AGENT_MD)
            result = self._run_script(tmpdir)
        self.assertEqual(result.returncode, 0, f"stdout: {result.stdout}\nstderr: {result.stderr}")

    def test_violation_exits_nonzero(self):
        """Script exits non-zero when a required agent lacks debrief sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_agent_file(Path(tmpdir), "implementer.md", MISSING_ONE_SECTION_MD)
            result = self._run_script(tmpdir)
        self.assertNotEqual(result.returncode, 0)

    def test_only_exempt_exits_zero(self):
        """Script exits 0 when all found agents are exempt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_agent_file(Path(tmpdir), "explorer.md", EXEMPT_AGENT_MD)
            result = self._run_script(tmpdir)
        self.assertEqual(result.returncode, 0, f"Exempt-only dir should exit 0. stderr: {result.stderr}")

    def test_report_names_missing_agent(self):
        """Output report names the agent that is missing sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_agent_file(Path(tmpdir), "implementer.md", MISSING_ONE_SECTION_MD)
            result = self._run_script(tmpdir)
        self.assertIn("implementer", result.stdout)
        self.assertIn("Follow-up Items", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
