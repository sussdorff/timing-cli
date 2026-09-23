#!/usr/bin/env python3
"""
Test suite for probe-urls.py — review-agent's B4 External Resource Verification helper.

Run with:
    uv run pytest skills/bead-reviewer/tests/test_probe_urls.py -v

These tests are unit-level: they exercise the URL extraction, skip-list classification,
and HTTP-code classification without making real network calls. The end-to-end probe
flow is covered by manual smoke tests (see bead CCP-cduz).
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "probe-urls.py"
_spec = importlib.util.spec_from_file_location("probe_urls", _SCRIPT_PATH)
probe_urls = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe_urls)


class TestSkipClassification(unittest.TestCase):
    """The skip-list catches license/comment/localhost/example URLs."""

    def test_apache_license_skipped(self):
        self.assertIn("apache.org", probe_urls._should_skip("https://www.apache.org/licenses/LICENSE-2.0") or "")

    def test_gnu_license_skipped(self):
        self.assertIsNotNone(probe_urls._should_skip("https://www.gnu.org/licenses/gpl-3.0.txt"))

    def test_example_com_skipped(self):
        self.assertIsNotNone(probe_urls._should_skip("https://example.com/foo"))

    def test_example_org_skipped(self):
        self.assertIsNotNone(probe_urls._should_skip("https://example.org/bar"))

    def test_localhost_skipped(self):
        self.assertIsNotNone(probe_urls._should_skip("http://localhost:8080/health"))

    def test_127_loopback_skipped(self):
        self.assertIsNotNone(probe_urls._should_skip("http://127.0.0.1/foo"))

    def test_real_url_not_skipped(self):
        self.assertIsNone(probe_urls._should_skip("https://www.google.com/"))

    def test_s3_path_not_skipped(self):
        self.assertIsNone(probe_urls._should_skip("https://my-bucket.s3.amazonaws.com/key"))


class TestHttpClassification(unittest.TestCase):
    """HTTP codes map to the correct severity buckets."""

    def test_200_is_ok(self):
        self.assertEqual(probe_urls._classify("200"), "ok")

    def test_301_is_ok(self):
        self.assertEqual(probe_urls._classify("301"), "ok")

    def test_399_is_ok(self):
        self.assertEqual(probe_urls._classify("399"), "ok")

    def test_404_is_fail(self):
        self.assertEqual(probe_urls._classify("404"), "fail")

    def test_500_is_fail(self):
        self.assertEqual(probe_urls._classify("500"), "fail")

    def test_429_is_transient(self):
        self.assertEqual(probe_urls._classify("429"), "transient")

    def test_503_is_transient(self):
        self.assertEqual(probe_urls._classify("503"), "transient")

    def test_000_is_unreachable(self):
        self.assertEqual(probe_urls._classify("000"), "unreachable")

    def test_garbage_is_unreachable(self):
        self.assertEqual(probe_urls._classify("not-a-code"), "unreachable")


class TestTrailingJunkStrip(unittest.TestCase):
    """URL extraction strips trailing markdown/punctuation that isn't part of the URL."""

    def test_trailing_period_stripped(self):
        self.assertEqual(probe_urls._strip_trailing_junk("https://x.com/foo."), "https://x.com/foo")

    def test_trailing_paren_stripped(self):
        self.assertEqual(probe_urls._strip_trailing_junk("https://x.com/foo)"), "https://x.com/foo")

    def test_trailing_comma_stripped(self):
        self.assertEqual(probe_urls._strip_trailing_junk("https://x.com/foo,"), "https://x.com/foo")

    def test_clean_url_unchanged(self):
        self.assertEqual(probe_urls._strip_trailing_junk("https://x.com/foo"), "https://x.com/foo")


class TestExtractAddedUrls(unittest.TestCase):
    """End-to-end extraction from a real (tiny) git repo's diff."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="probe_urls_test_")
        self.repo = Path(self.tmpdir)
        self._git("init", "-q")
        self._git("config", "user.email", "test@test")
        self._git("config", "user.name", "test")
        (self.repo / "README.md").write_text("initial\n")
        self._git("add", ".")
        self._git("commit", "-q", "-m", "init")
        self.pre_sha = self._git("rev-parse", "HEAD").strip()

    def _git(self, *args):
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def test_extracts_added_urls_only(self):
        # Add file with URLs
        (self.repo / "data.md").write_text(
            "Real: https://www.example.com/real\n"
            "Another: https://my-bucket.s3.amazonaws.com/key\n"
        )
        self._git("add", "data.md")
        self._git("commit", "-q", "-m", "add data")

        # Switch cwd into the repo so git diff inside _extract_added_urls works
        prev_cwd = os.getcwd()
        try:
            os.chdir(self.repo)
            urls = probe_urls._extract_added_urls(f"{self.pre_sha}...HEAD")
        finally:
            os.chdir(prev_cwd)

        url_set = {u for u, _ in urls}
        self.assertIn("https://www.example.com/real", url_set)
        self.assertIn("https://my-bucket.s3.amazonaws.com/key", url_set)

    def test_skips_removed_lines(self):
        # Initial commit already had README.md — modify it by adding a URL,
        # then in next commit remove the URL line.
        (self.repo / "README.md").write_text("initial\nhttps://added-then-removed.com/foo\n")
        self._git("add", ".")
        self._git("commit", "-q", "-m", "add url")

        mid_sha = self._git("rev-parse", "HEAD").strip()

        (self.repo / "README.md").write_text("initial\n")
        self._git("add", ".")
        self._git("commit", "-q", "-m", "remove url")

        # Diff from mid_sha (URL present) to HEAD (URL removed) — should NOT pick up the URL
        prev_cwd = os.getcwd()
        try:
            os.chdir(self.repo)
            urls = probe_urls._extract_added_urls(f"{mid_sha}...HEAD")
        finally:
            os.chdir(prev_cwd)

        url_set = {u for u, _ in urls}
        self.assertNotIn("https://added-then-removed.com/foo", url_set)


class TestEnvelopeShape(unittest.TestCase):
    """The script emits the canonical execution-result envelope shape."""

    def test_envelope_required_fields(self):
        env = probe_urls._envelope("ok", "test", {"x": 1})
        for field in ("status", "summary", "data", "errors", "next_steps", "open_items", "meta"):
            self.assertIn(field, env)
        self.assertEqual(env["meta"]["producer"], "probe-urls.py")
        self.assertEqual(env["meta"]["schema"], "core/contracts/execution-result.schema.json")


class TestCliBadRange(unittest.TestCase):
    """The script rejects malformed --diff-range and exits 2."""

    def test_bad_range_exits_2(self):
        result = subprocess.run(
            [sys.executable, str(_SCRIPT_PATH), "--diff-range", "not-a-range"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["errors"][0]["code"], "BAD_RANGE")


if __name__ == "__main__":
    unittest.main()
