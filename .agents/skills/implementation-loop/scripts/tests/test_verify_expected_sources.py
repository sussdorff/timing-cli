"""AC3: tautological expected values are rejected; independent sources pass."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "verify_expected_sources.py"


def _load():
    spec = importlib.util.spec_from_file_location("verify_expected_sources", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_independent_source_is_accepted(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "unit" / "lab.test.ts"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        '''
        // independent source: IG canonical http://example.org/ig|1.0.0 element LabObservation.code
        test("lab code is NA", () => {
          expect(mapLab().code).toBe("NA");
        });
        ''',
        encoding="utf-8",
    )
    verify = _load()
    result = verify.verify_expected_values(
        [
            {
                "name": "lab_code",
                "value": "NA",
                "source_kind": "ig_profile",
                "source": "IG canonical http://example.org/ig|1.0.0 element LabObservation.code",
                "test_path": str(test_file),
                "ig_canonical": "http://example.org/ig|1.0.0",
                "element": "LabObservation.code",
            }
        ],
        repo_root=tmp_path,
        test_tree="tests",
    )
    assert result["status"] == "ok"
    assert "http://example.org/ig|1.0.0" in result["sources"][0]


def test_allowlisted_kind_without_structured_provenance_is_rejected(
    tmp_path: Path,
) -> None:
    test_file = tmp_path / "tests" / "lab.test.ts"
    test_file.parent.mkdir(parents=True)
    test_file.write_text('expect(code).toBe("NA");\n', encoding="utf-8")
    verify = _load()
    result = verify.verify_expected_values(
        [
            {
                "name": "lab_code",
                "value": "NA",
                "source_kind": "ig_profile",
                "source": "Implementation Guide profile LabObservation.code",
                "test_path": str(test_file),
            }
        ],
        repo_root=tmp_path,
        test_tree="tests",
    )
    assert result["status"] == "rejected"
    assert "provenance" in result["reason"]


def test_test_file_must_name_source_and_expected_value(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "lab.test.ts"
    test_file.parent.mkdir(parents=True)
    test_file.write_text('expect(code).toBe("XX");\n', encoding="utf-8")
    verify = _load()
    result = verify.verify_expected_values(
        [
            {
                "name": "lab_code",
                "value": "NA",
                "source_kind": "ig_profile",
                "source": "IG canonical http://example.org/ig|1.0.0 element LabObservation.code",
                "test_path": str(test_file),
                "ig_canonical": "http://example.org/ig|1.0.0",
                "element": "LabObservation.code",
            }
        ],
        repo_root=tmp_path,
        test_tree="tests",
    )
    assert result["status"] == "rejected"
    assert "test" in result["reason"]


def test_tautological_expected_value_is_rejected() -> None:
    verify = _load()
    result = verify.verify_expected_values(
        [
            {
                "name": "total",
                "value": "items.reduce",
                "source_kind": "implementation",
                "source": "computed the way the mapper computes it",
                "derivation": "items.reduce((sum, i) => sum + i.price, 0)",
            }
        ]
    )
    assert result["status"] == "rejected"
    assert "tautological" in result["reason"]


def test_missing_independent_source_is_rejected() -> None:
    verify = _load()
    result = verify.verify_expected_values(
        [{"name": "status", "value": "confirmed"}]
    )
    assert result["status"] == "rejected"
    assert "independent source" in result["reason"]


def test_test_path_outside_test_tree_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "agents").mkdir()
    agent = tmp_path / "agents" / "tdd-test-author.md"
    agent.write_text('expect("NA"); IG canonical http://example.org/ig|1.0.0 LabObservation.code\n', encoding="utf-8")
    verify = _load()
    result = verify.verify_expected_values(
        [
            {
                "name": "lab_code",
                "value": "NA",
                "source_kind": "ig_profile",
                "source": "IG canonical http://example.org/ig|1.0.0 element LabObservation.code",
                "test_path": str(agent),
                "ig_canonical": "http://example.org/ig|1.0.0",
                "element": "LabObservation.code",
            }
        ],
        repo_root=tmp_path,
        test_tree="tests",
    )
    assert result["status"] == "rejected"
    assert "test tree" in result["reason"]


def test_symlink_escape_from_test_tree_is_rejected(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    outside = tmp_path / "secret.test.ts"
    outside.write_text(
        '// IG canonical http://example.org/ig|1.0.0 element LabObservation.code\nexpect("NA");\n',
        encoding="utf-8",
    )
    link = tests / "escaped.test.ts"
    link.symlink_to(outside)
    verify = _load()
    result = verify.verify_expected_values(
        [
            {
                "name": "lab_code",
                "value": "NA",
                "source_kind": "ig_profile",
                "source": "IG canonical http://example.org/ig|1.0.0 element LabObservation.code",
                "test_path": str(link),
                "ig_canonical": "http://example.org/ig|1.0.0",
                "element": "LabObservation.code",
            }
        ],
        repo_root=tmp_path,
        test_tree="tests",
    )
    assert result["status"] == "rejected"


def test_ig_source_containing_code_is_not_tautological(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "lab.test.ts"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        '''
        // IG canonical http://example.org/ig|1.0.0 element LabObservation.code
        expect(mapLab().code).toBe("NA");
        ''',
        encoding="utf-8",
    )
    verify = _load()
    result = verify.verify_expected_values(
        [
            {
                "name": "lab_code",
                "value": "NA",
                "source_kind": "ig_profile",
                "source": "IG canonical http://example.org/ig|1.0.0 element LabObservation.code",
                "test_path": str(test_file),
                "ig_canonical": "http://example.org/ig|1.0.0",
                "element": "LabObservation.code",
            }
        ],
        repo_root=tmp_path,
        test_tree="tests",
    )
    assert result["status"] == "ok"


def test_oracle_source_mentioning_code_is_accepted(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "oracle.test.ts"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        '// oracle ledger led-42 Observation.code\nexpect(obs.code).toBe("NA");\n',
        encoding="utf-8",
    )
    verify = _load()
    result = verify.verify_expected_values(
        [
            {
                "name": "code",
                "value": "NA",
                "source_kind": "oracle",
                "source": "oracle ledger led-42 Observation.code",
                "test_path": str(test_file),
                "oracle_ledger_id": "led-42",
            }
        ],
        repo_root=tmp_path,
        test_tree="tests",
    )
    assert result["status"] == "ok"


def test_cli_rejects_tautological_payload(tmp_path: Path) -> None:
    payload = tmp_path / "expected.json"
    payload.write_text(
        json.dumps(
            {
                "expected_values": [
                    {
                        "name": "total",
                        "value": "15",
                        "source_kind": "implementation",
                        "source": "same formula as calculateTotal",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(MODULE),
            "verify",
            "--from-json",
            str(payload),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "tautological" in result.stdout
