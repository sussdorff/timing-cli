#!/usr/bin/env python3
"""
Test suite for bd_lint_contracts.py — fixture-based, no real bd CLI calls.

Run with:
    python3 -m unittest skills/cognovis-beads/scripts/tests/test_bd_lint_contracts.py -v
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Allow importing the module under test
sys.path.insert(0, str(Path(__file__).parent.parent))

import bd_lint_contracts as linter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GOOD_DESCRIPTION = """
## Architecture Contracts Touched
- ADR-001 (Identity): This bead extends the ID helper to support new entity type
- Helper: packages/core/helpers/entity-id.ts
- Enforcer-Reactive: lint/rules/no-raw-id-concat.js

## Coverage Expected
- Packages: core, adapters
- Status nach Bead: ADR-001 green for new entity type

## Gaps to Close
- [ ] None
""".strip()

BAD_3A_EMPTY_SECTION = """
## Architecture Contracts Touched

## Coverage Expected
- Packages: core
- Status nach Bead: unchanged

## Gaps to Close
- [ ] None
""".strip()

BAD_3B_NO_ADR_BULLET = """
## Architecture Contracts Touched
- Helper: packages/core/helpers/entity-id.ts
- Enforcer-Reactive: lint/rules/no-raw-id-concat.js

## Coverage Expected
- Packages: core

## Gaps to Close
- [ ] None
""".strip()

BAD_3C_NO_GAPS_SECTION = """
## Architecture Contracts Touched
- ADR-001 (Identity): extended for new entity type

## Coverage Expected
- Packages: core
""".strip()

BAD_3C_EMPTY_GAPS = """
## Architecture Contracts Touched
- ADR-001 (Identity): extended for new entity type

## Coverage Expected
- Packages: core

## Gaps to Close
""".strip()

BAD_3C_INVALID_GAP_BULLETS = """
## Architecture Contracts Touched
- ADR-001 (Identity): extended for new entity type

## Gaps to Close
- [ ] Some vague gap description without required marker
""".strip()

GOOD_WITH_NEEDED_GAPS = """
## Architecture Contracts Touched
- ADR-002 (Permissions): adds permission check to new route

## Gaps to Close
- [ ] [ADR-NEEDED] No ADR yet for caching strategy
- [ ] [ENFORCER-REACTIVE-NEEDED] ESLint rule for this pattern
""".strip()

GOOD_MINIMAL = """
## Architecture Contracts Touched
- ADR-042 (Caching): uses existing cache invalidation contract

## Gaps to Close
- [ ] None
""".strip()

NO_SECTION_DESCRIPTION = """
## Summary
This bead does not touch any architectural contracts.
""".strip()

EDGE_OPTIONAL_BULLETS_ONLY = """
## Architecture Contracts Touched
- Helper: packages/utils/id.ts
- Enforcer-Proactive: scripts/generate-entity.ts

## Gaps to Close
- [ ] None
""".strip()

BAD_3C_NONE_MIXED_WITH_NEEDED = """
## Architecture Contracts Touched
- ADR-001 (Identity): extended for new entity type

## Gaps to Close
- [ ] None
- [ ] [ADR-NEEDED] Some gap that needs an ADR
""".strip()

DESCRIPTION_WITH_SECTION_NO_LABEL = GOOD_DESCRIPTION

DESCRIPTION_WITH_SECTION_IN_FENCE = """
## Summary
This bead documents the convention.

```markdown
## Architecture Contracts Touched
- ADR-001 (Example): example
```

No actual architectural contract touched.
""".strip()


# ---------------------------------------------------------------------------
# Unit tests for extract_section()
# ---------------------------------------------------------------------------

class TestExtractSection(unittest.TestCase):

    def test_extracts_section_content(self):
        content = linter.extract_section(GOOD_DESCRIPTION, "## Architecture Contracts Touched")
        self.assertIsNotNone(content)
        self.assertIn("ADR-001", content)

    def test_returns_none_for_missing_section(self):
        content = linter.extract_section(NO_SECTION_DESCRIPTION, "## Architecture Contracts Touched")
        self.assertIsNone(content)

    def test_stops_at_next_header(self):
        content = linter.extract_section(GOOD_DESCRIPTION, "## Architecture Contracts Touched")
        self.assertNotIn("Packages:", content)  # That's in ## Coverage Expected

    def test_extracts_gaps_section(self):
        content = linter.extract_section(GOOD_DESCRIPTION, "## Gaps to Close")
        self.assertIsNotNone(content)
        self.assertIn("None", content)

    def test_empty_section_returns_empty_string(self):
        content = linter.extract_section(BAD_3A_EMPTY_SECTION, "## Architecture Contracts Touched")
        self.assertIsNotNone(content)
        stripped = content.strip()
        self.assertEqual(stripped, "")


# ---------------------------------------------------------------------------
# Unit tests for validate_contracts_section()
# ---------------------------------------------------------------------------

class TestValidateContractsSection(unittest.TestCase):

    def test_good_description_no_errors(self):
        errors = linter.validate_contracts_section("BID-001", GOOD_DESCRIPTION)
        self.assertEqual(errors, [], f"Expected no errors, got: {errors}")

    def test_good_minimal_no_errors(self):
        errors = linter.validate_contracts_section("BID-002", GOOD_MINIMAL)
        self.assertEqual(errors, [], f"Expected no errors, got: {errors}")

    def test_good_with_needed_gaps_no_errors(self):
        errors = linter.validate_contracts_section("BID-003", GOOD_WITH_NEEDED_GAPS)
        self.assertEqual(errors, [], f"Expected no errors, got: {errors}")

    # Rule 3a: Empty section
    def test_3a_empty_section_fails(self):
        errors = linter.validate_contracts_section("BID-004", BAD_3A_EMPTY_SECTION)
        self.assertTrue(len(errors) > 0, "Expected error for empty section")
        self.assertTrue(any("empty" in e.lower() or "3a" in e for e in errors))

    # Rule 3b: ADR bullet required
    def test_3b_no_adr_bullet_fails(self):
        errors = linter.validate_contracts_section("BID-005", BAD_3B_NO_ADR_BULLET)
        self.assertTrue(len(errors) > 0, "Expected error for missing ADR bullet")
        self.assertTrue(any("ADR" in e for e in errors))

    def test_3b_edge_optional_bullets_only_fails(self):
        """Only Helper/Enforcer bullets, no ADR → should fail rule 3b."""
        errors = linter.validate_contracts_section("BID-006", EDGE_OPTIONAL_BULLETS_ONLY)
        self.assertTrue(len(errors) > 0, "Expected error: no ADR bullet even though optional bullets present")
        self.assertTrue(any("ADR" in e for e in errors))

    # Rule 3c: Gaps section required
    def test_3c_no_gaps_section_fails(self):
        errors = linter.validate_contracts_section("BID-007", BAD_3C_NO_GAPS_SECTION)
        self.assertTrue(len(errors) > 0, "Expected error for missing Gaps section")
        self.assertTrue(any("Gaps" in e or "gap" in e.lower() for e in errors))

    def test_3c_empty_gaps_section_fails(self):
        errors = linter.validate_contracts_section("BID-008", BAD_3C_EMPTY_GAPS)
        self.assertTrue(len(errors) > 0, "Expected error for empty Gaps section")
        self.assertTrue(any("empty" in e.lower() or "Gaps" in e or "bullet" in e.lower() for e in errors))

    def test_3c_invalid_gap_bullets_fails(self):
        errors = linter.validate_contracts_section("BID-009", BAD_3C_INVALID_GAP_BULLETS)
        self.assertTrue(len(errors) > 0, "Expected error for invalid gap bullet format")
        self.assertTrue(any("None" in e or "NEEDED" in e or "format" in e.lower() for e in errors))

    # Missing section entirely
    def test_missing_section_fails(self):
        errors = linter.validate_contracts_section("BID-010", NO_SECTION_DESCRIPTION)
        self.assertTrue(len(errors) > 0, "Expected error for missing section")
        self.assertTrue(any("Missing" in e or "missing" in e for e in errors))

    # Rule 3b: optional bullet prefix validation
    def test_3b_helper_without_colon_fails(self):
        """- Helper path (no colon) is not a valid optional bullet."""
        desc = """## Architecture Contracts Touched
- ADR-001 (Identity): valid adr
- Helper packages/core/id.ts

## Gaps to Close
- [ ] None
"""
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(len(errors) > 0, "Expected error for malformed Helper bullet")
        self.assertTrue(any("Helper" in e or "prefix" in e.lower() or "invalid" in e.lower() for e in errors))

    def test_3b_unrecognised_optional_prefix_fails(self):
        """Unrecognised prefix (e.g. Enforcer: without Proactive/Reactive) must fail."""
        desc = """## Architecture Contracts Touched
- ADR-001 (Identity): valid adr
- Enforcer: some-path

## Gaps to Close
- [ ] None
"""
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(len(errors) > 0, "Expected error for unrecognised prefix")
        self.assertTrue(any("Enforcer" in e or "prefix" in e.lower() or "invalid" in e.lower() for e in errors))

    def test_3b_typo_in_optional_prefix_fails(self):
        """Typo in optional prefix (Enforcer-Proacive vs Enforcer-Proactive) must fail."""
        desc = """## Architecture Contracts Touched
- ADR-001 (Identity): valid adr
- Enforcer-Proacive: some-path

## Gaps to Close
- [ ] None
"""
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(len(errors) > 0, "Expected error for typo in prefix")

    def test_3b_valid_optional_bullets_with_adr_pass(self):
        """Valid Helper + Enforcer-Proactive + Enforcer-Reactive with ADR should pass."""
        desc = """## Architecture Contracts Touched
- ADR-001 (Identity): valid adr
- Helper: packages/core/helpers/entity-id.ts
- Enforcer-Proactive: scripts/codegen/generate-entity.ts
- Enforcer-Reactive: lint/rules/no-raw-id-concat.js

## Gaps to Close
- [ ] None
"""
        errors = linter.validate_contracts_section("X", desc)
        self.assertEqual(errors, [], f"Expected no errors for valid optional bullets: {errors}")


# ---------------------------------------------------------------------------
# Unit tests for label false-negative check (rule Y)
# ---------------------------------------------------------------------------

class TestFalseNegativeCheck(unittest.TestCase):

    def test_detects_section_without_label(self):
        """Bead has section in description but no touches-contract label → error."""
        beads = [
            {"id": "BID-FN1", "description": DESCRIPTION_WITH_SECTION_NO_LABEL,
             "title": "Test", "status": "open"}
        ]

        labeled_ids: set[str] = set()  # Empty: BID-FN1 has no label
        errors = linter.check_false_negatives(labeled_ids, beads)

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].bead_id, "BID-FN1")
        self.assertIn("label", errors[0].error.lower())

    def test_no_false_negative_when_correctly_labeled(self):
        """Bead has section AND has label → already in labeled_ids → no error."""
        beads = [
            {"id": "BID-FN2", "description": GOOD_DESCRIPTION,
             "title": "Test", "status": "open"}
        ]

        labeled_ids = {"BID-FN2"}  # Already labeled
        errors = linter.check_false_negatives(labeled_ids, beads)

        self.assertEqual(errors, [])

    def test_no_false_negative_when_no_section(self):
        """Bead has no section and no label → no error (opt-in)."""
        beads = [
            {"id": "BID-FN3", "description": NO_SECTION_DESCRIPTION,
             "title": "Test", "status": "open"}
        ]

        labeled_ids: set[str] = set()
        errors = linter.check_false_negatives(labeled_ids, beads)

        self.assertEqual(errors, [])

    def test_no_false_negative_when_section_in_fence(self):
        """Header inside fenced code block should not trigger rule Y."""
        beads = [
            {"id": "BID-FN4", "description": DESCRIPTION_WITH_SECTION_IN_FENCE,
             "title": "Test", "status": "open"}
        ]

        labeled_ids: set[str] = set()
        errors = linter.check_false_negatives(labeled_ids, beads)

        self.assertEqual(errors, [], f"Expected no errors for fenced header, got: {errors}")

    def test_label_exact_match_no_substring(self):
        """_bead_has_label should not match 'touches-contract-v2' for 'touches-contract'."""
        with patch("bd_lint_contracts._run") as mock_run:
            mock_run.return_value = (0, "touches-contract-v2\n", "")
            result = linter._bead_has_label("BID-X", "touches-contract")
            self.assertFalse(result)


# ---------------------------------------------------------------------------
# Integration-style tests for lint_bead()
# ---------------------------------------------------------------------------

class TestLintBead(unittest.TestCase):

    @patch("bd_lint_contracts._run")
    def test_lint_valid_bead_passes(self, mock_run):
        import json
        bead_detail = [{"id": "BID-I1", "description": GOOD_DESCRIPTION}]

        def side_effect(args, **kwargs):
            if args == ["show", "BID-I1", "--json"]:
                return (0, json.dumps(bead_detail), "")
            if args == ["label", "list", "BID-I1"]:
                return (0, "touches-contract\n", "")
            return (0, "", "")

        mock_run.side_effect = side_effect
        errors = linter.lint_bead("BID-I1")
        self.assertEqual(errors, [], f"Expected no errors: {errors}")

    @patch("bd_lint_contracts._run")
    def test_lint_bead_without_label_but_with_section(self, mock_run):
        import json
        bead_detail = [{"id": "BID-I2", "description": GOOD_DESCRIPTION}]

        def side_effect(args, **kwargs):
            if args == ["show", "BID-I2", "--json"]:
                return (0, json.dumps(bead_detail), "")
            if args == ["label", "list", "BID-I2"]:
                return (0, "other-label\n", "")  # No touches-contract
            return (0, "", "")

        mock_run.side_effect = side_effect
        errors = linter.lint_bead("BID-I2")
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("label" in e.error.lower() for e in errors))

    @patch("bd_lint_contracts._run")
    def test_lint_bead_with_label_and_bad_description(self, mock_run):
        import json
        bead_detail = [{"id": "BID-I3", "description": BAD_3B_NO_ADR_BULLET}]

        def side_effect(args, **kwargs):
            if args == ["show", "BID-I3", "--json"]:
                return (0, json.dumps(bead_detail), "")
            if args == ["label", "list", "BID-I3"]:
                return (0, "touches-contract\n", "")
            return (0, "", "")

        mock_run.side_effect = side_effect
        errors = linter.lint_bead("BID-I3")
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("ADR" in e.error for e in errors))

    @patch("bd_lint_contracts._run")
    def test_lint_bead_not_found(self, mock_run):
        mock_run.return_value = (1, "", "bead not found")
        errors = linter.lint_bead("NONEXISTENT")
        self.assertTrue(len(errors) > 0)


# ---------------------------------------------------------------------------
# ADR bullet format validation
# ---------------------------------------------------------------------------

class TestADRBulletFormats(unittest.TestCase):

    def _desc_with_bullets(self, bullets: str) -> str:
        return f"""## Architecture Contracts Touched
{bullets}

## Gaps to Close
- [ ] None
"""

    def test_valid_adr_format_accepted(self):
        desc = self._desc_with_bullets("- ADR-001 (Identity): does something")
        errors = linter.validate_contracts_section("X", desc)
        self.assertEqual(errors, [])

    def test_valid_adr_three_digits(self):
        desc = self._desc_with_bullets("- ADR-123 (Caching Strategy): uses cache")
        errors = linter.validate_contracts_section("X", desc)
        self.assertEqual(errors, [])

    def test_invalid_adr_no_number_fails(self):
        desc = self._desc_with_bullets("- ADR (Identity): missing number")
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(any("ADR" in e for e in errors))

    def test_invalid_adr_no_parens_fails(self):
        desc = self._desc_with_bullets("- ADR-001: missing name in parens")
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(any("ADR" in e for e in errors))


# ---------------------------------------------------------------------------
# Gap section valid marker tests
# ---------------------------------------------------------------------------

class TestGapMarkers(unittest.TestCase):

    def _desc_with_gap(self, gap_line: str) -> str:
        return f"""## Architecture Contracts Touched
- ADR-001 (Test): test contract

## Gaps to Close
{gap_line}
"""

    def test_none_marker_valid(self):
        desc = self._desc_with_gap("- [ ] None")
        errors = linter.validate_contracts_section("X", desc)
        self.assertEqual(errors, [])

    def test_adr_needed_marker_valid(self):
        desc = self._desc_with_gap("- [ ] [ADR-NEEDED] Need ADR for this pattern")
        errors = linter.validate_contracts_section("X", desc)
        self.assertEqual(errors, [])

    def test_helper_needed_marker_valid(self):
        desc = self._desc_with_gap("- [ ] [HELPER-NEEDED] Need helper for XYZ")
        errors = linter.validate_contracts_section("X", desc)
        self.assertEqual(errors, [])

    def test_enforcer_proactive_needed_marker_valid(self):
        desc = self._desc_with_gap("- [ ] [ENFORCER-PROACTIVE-NEEDED] Codegen missing")
        errors = linter.validate_contracts_section("X", desc)
        self.assertEqual(errors, [])

    def test_enforcer_reactive_needed_marker_valid(self):
        desc = self._desc_with_gap("- [ ] [ENFORCER-REACTIVE-NEEDED] Lint rule missing")
        errors = linter.validate_contracts_section("X", desc)
        self.assertEqual(errors, [])

    def test_free_text_gap_fails(self):
        desc = self._desc_with_gap("- [ ] Some gap without proper marker")
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(len(errors) > 0)

    def test_bare_adr_needed_fails(self):
        """- [ ] [ADR-NEEDED] with no description after marker must fail."""
        desc = self._desc_with_gap("- [ ] [ADR-NEEDED]")
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(len(errors) > 0, "Bare [ADR-NEEDED] with no description should fail")

    def test_bare_helper_needed_fails(self):
        """- [ ] [HELPER-NEEDED] with no description must fail."""
        desc = self._desc_with_gap("- [ ] [HELPER-NEEDED]")
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(len(errors) > 0, "Bare [HELPER-NEEDED] with no description should fail")

    def test_bare_enforcer_proactive_needed_fails(self):
        """- [ ] [ENFORCER-PROACTIVE-NEEDED] with no description must fail."""
        desc = self._desc_with_gap("- [ ] [ENFORCER-PROACTIVE-NEEDED]")
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(len(errors) > 0, "Bare [ENFORCER-PROACTIVE-NEEDED] with no description should fail")

    def test_bare_enforcer_reactive_needed_fails(self):
        """- [ ] [ENFORCER-REACTIVE-NEEDED] with no description must fail."""
        desc = self._desc_with_gap("- [ ] [ENFORCER-REACTIVE-NEEDED]")
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(len(errors) > 0, "Bare [ENFORCER-REACTIVE-NEEDED] with no description should fail")

    def test_adr_needed_whitespace_only_fails(self):
        """- [ ] [ADR-NEEDED]   (marker + only whitespace) must fail."""
        desc = self._desc_with_gap("- [ ] [ADR-NEEDED]   ")
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(len(errors) > 0, "[ADR-NEEDED] followed by only whitespace should fail")

    def test_3c_none_and_needed_coexist_fails(self):
        """- [ ] None and - [ ] [ADR-NEEDED] in same section must fail (mutual exclusion)."""
        desc = self._desc_with_gap("- [ ] None\n- [ ] [ADR-NEEDED] Some gap")
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(len(errors) > 0, "Expected error for None mixed with NEEDED markers")
        self.assertTrue(
            any("None" in e or "mutual" in e.lower() or "exclusive" in e.lower() for e in errors),
            f"Error message should mention None, mutual, or exclusive. Got: {errors}"
        )

    def test_3c_none_only_passes(self):
        """- [ ] None alone (no NEEDED markers) must pass."""
        desc = self._desc_with_gap("- [ ] None")
        errors = linter.validate_contracts_section("X", desc)
        self.assertEqual(errors, [], f"Only '- [ ] None' should pass, got: {errors}")


# ---------------------------------------------------------------------------
# Fenced code block handling in validate_contracts_section
# ---------------------------------------------------------------------------

class TestFencedBlocksInValidation(unittest.TestCase):

    def test_section_in_fence_not_parsed_as_real_section(self):
        """If ## Architecture Contracts Touched only appears in a fenced block, no error."""
        desc = """## Summary
This bead documents the convention.

```markdown
## Architecture Contracts Touched
- ADR-001 (Example): example

## Gaps to Close
- [ ] None
```

No actual contract touched.
"""
        # validate_contracts_section should see no real section → "Missing section" error
        errors = linter.validate_contracts_section("X", desc)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("Missing" in e for e in errors),
                        "Should report missing section, not parse fenced content as real")

    def test_fenced_example_above_real_section_no_interference(self):
        """Fenced example above a real section should not interfere with parsing."""
        desc = """## Overview
Example template:

```markdown
## Architecture Contracts Touched
- ADR-999 (Example): this is just an example
```

## Architecture Contracts Touched
- ADR-001 (Identity): actual contract usage

## Gaps to Close
- [ ] None
"""
        errors = linter.validate_contracts_section("X", desc)
        self.assertEqual(errors, [], f"Real section after fence should pass: {errors}")


# ---------------------------------------------------------------------------
# _BdUnavailableError propagation
# ---------------------------------------------------------------------------

class TestBdUnavailableError(unittest.TestCase):

    @patch("bd_lint_contracts._run")
    def test_get_beads_json_raises_on_bd_failure(self, mock_run):
        mock_run.return_value = (1, "", "bd: command not found")
        with self.assertRaises(linter._BdUnavailableError):
            linter._get_beads_json(["--status", "open"])

    @patch("bd_lint_contracts._run")
    def test_get_beads_json_raises_on_invalid_json(self, mock_run):
        mock_run.return_value = (0, "not valid json", "")
        with self.assertRaises(linter._BdUnavailableError):
            linter._get_beads_json(["--status", "open"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
