#!/usr/bin/env python3
"""
Shared helper for computing bead content SHA and reviewer SHA.
Used by bead-orchestrator Phase 0 gate and other bead-reviewer cache consumers.

Content hash is stable across status/priority/metadata.review changes.
Only content fields that affect spec quality are included.

Location convention: this script ships INSIDE the bead-reviewer skill at
`skills/bead-reviewer/scripts/compute_bead_content_sha.py`. This guarantees
that the sibling SKILL.md is always at `Path(__file__).resolve().parents[1]
/ "SKILL.md"` — the script travels with the skill via `/library use
bead-reviewer`, so any consumer (cognovis-core, polaris, mira) reaches the
helper at the same install-relative path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


BEAD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")


def declared_label_prefixes(label_families: list[dict] | None) -> tuple[str, ...]:
    """Return stable non-empty prefixes from the resolved label-family contract."""
    return tuple(
        sorted(
            {
                str(family.get("prefix") or "").strip()
                for family in (label_families or [])
                if isinstance(family, dict)
                and str(family.get("prefix") or "").strip()
            }
        )
    )


def compute_content_sha(
    bead: dict, *, label_families: list[dict] | None = None
) -> str:
    """Compute SHA256 of the canonicalized bead content fields.

    Included fields in canonical JSON:
      title, description, acceptance_criteria,
      issue_type (bead type — affects bead-reviewer Pass 1 criteria set),
      parent ID, sorted labels from contract-declared families, and all sorted
      outgoing relationships.

    Excluded: status, priority, claim, metadata.review, closed_at, updated_at,
    metadata.intent, metadata.contracts, metadata.constraints, metadata.effort,
    and all metadata.routing.* fields. Routing metadata is excluded because work-size
    and execution routes are not inputs to specification review.

    Incoming dependents and children are excluded because they do not change
    this bead's authored specification. Operational state and execution routes
    are not inputs to specification review.
    """
    deps = bead.get("dependencies") or []
    relationships = sorted(
        (
            str(item.get("dependency_type") or ""),
            str(item.get("id") or item.get("depends_on_id") or ""),
        )
        for item in deps
        if isinstance(item, dict)
    )
    prefixes = declared_label_prefixes(label_families)
    labels = sorted(
        str(label)
        for label in (bead.get("labels") or [])
        if any(str(label).startswith(prefix) for prefix in prefixes)
    )
    parent = bead.get("parent")
    parent_id = (
        str(parent.get("id") or "")
        if isinstance(parent, dict)
        else str(parent or bead.get("parent_id") or "")
    )

    # Bead type (issue_type) controls which Pass 1 criteria bead-reviewer
    # requires (feature/epic = all 6, task/bug = 4 required, chore = 1).
    # Accept both `issue_type` (canonical in bd show --json) and the
    # historical `type` key for robustness.
    bead_type = bead.get("issue_type") or bead.get("type") or ""

    canonical = {
        "title": bead.get("title") or "",
        "description": bead.get("description") or "",
        "acceptance_criteria": bead.get("acceptance_criteria") or "",
        "issue_type": bead_type,
        "parent_id": parent_id,
        "labels": labels,
        "relationships": relationships,
    }
    content = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_live_bead(bead_id: str, repo_root: str | Path) -> dict:
    """Load one live bead through bd in an explicitly bound repository."""
    if not BEAD_ID_RE.fullmatch(bead_id):
        raise ValueError(f"invalid bead id: {bead_id}")
    repo = Path(repo_root).expanduser().resolve()
    if not repo.is_dir():
        raise ValueError(f"repository does not exist: {repo}")
    bd_command = ["bd"]
    if os.environ.get("BEAD_REVIEWER_BD_READONLY") == "1":
        bd_command.extend(["--readonly", "--sandbox"])
    bd_command.extend(["show", bead_id, "--json"])
    result = subprocess.run(
        bd_command,
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"bd show {bead_id} failed")
    payload = json.loads(result.stdout, strict=False)
    bead = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(bead, dict):
        raise ValueError(f"bd show returned no bead for {bead_id}")
    return bead


def _repo_root_for_skill(skill_path: Path) -> Path:
    """Return the source/install root for a skill path in skills/bead-reviewer."""
    try:
        if skill_path.parent.name == "bead-reviewer" and skill_path.parent.parent.name == "skills":
            return skill_path.parents[2]
    except IndexError:
        pass
    return skill_path.parent


def _update_hash_from_optional_file(hasher: "hashlib._Hash", path: Path) -> None:
    if path.exists():
        hasher.update(path.read_bytes())
    else:
        hasher.update(b"")


def compute_reviewer_sha(
    reviewer_skill_path: str | None = None,
    reviewer_agent_path: str | None = None,
) -> str:
    """Compute reviewer SHA from the live review skill and its contract files.

    Hash components (SHA256 of concatenated file contents in deterministic order):
    1. SKILL.md (the bead-reviewer skill definition)
    2. references/review-contract.md
    3. scripts/review_contract.py
    4. scripts/contract_loader.py
    5. references/finding-rule-registry.json
    6. scripts/finding_rules.py
    7. the exact bead-spec-reviewer agent source or installed projection used in the
       dispatched prompt
    Contract components are optional for backward compatibility with older standalone
    installs. Missing optional components are hashed as empty strings.

    Strategy:
    1. If `reviewer_skill_path` is given (absolute or expanduser-resolvable), use it.
    2. Otherwise use the script-anchored sibling: `Path(__file__).resolve().parents[1]
       / "SKILL.md"`. Since this script lives at
       `skills/bead-reviewer/scripts/compute_bead_content_sha.py`, its parent's parent
       IS the bead-reviewer skill root, which always contains the live SKILL.md.
       This works identically from the cognovis-core source tree, from a
       `~/.agents/skills/bead-reviewer/` install, and from a `~/.claude/skills/...`
       install.
    3. Return 'unknown' only when explicit `reviewer_skill_path` was given but did not
       resolve.
    """
    if reviewer_skill_path:
        p = Path(reviewer_skill_path).expanduser()
        if not p.exists():
            return "unknown"
    else:
        # Sibling lookup: the script ships inside the skill, so SKILL.md is always
        # at parents[1]/SKILL.md regardless of where the skill is installed.
        p = Path(__file__).resolve().parents[1] / "SKILL.md"
        if not p.exists():
            return "unknown"

    skill_root = p.resolve().parent
    if reviewer_agent_path:
        agent_path = Path(reviewer_agent_path).expanduser()
        if not agent_path.is_file():
            return "unknown"
    else:
        agent_path = skill_root.parents[1] / "agents" / "bead-spec-reviewer.md"
    hasher = hashlib.sha256()
    hasher.update(p.read_bytes())
    _update_hash_from_optional_file(hasher, skill_root / "references" / "review-contract.md")
    _update_hash_from_optional_file(hasher, skill_root / "scripts" / "review_contract.py")
    _update_hash_from_optional_file(hasher, skill_root / "scripts" / "contract_loader.py")
    _update_hash_from_optional_file(
        hasher, skill_root / "references" / "finding-rule-registry.json"
    )
    _update_hash_from_optional_file(hasher, skill_root / "scripts" / "finding_rules.py")
    _update_hash_from_optional_file(hasher, agent_path)
    return hasher.hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compute bead content SHA and reviewer SHA"
    )
    parser.add_argument(
        "--reviewer-skill-path",
        help="Path to bead-reviewer SKILL.md (relative to repo root or absolute)",
    )
    parser.add_argument(
        "--reviewer-agent-path",
        help="Exact bead-spec-reviewer source or installed projection used in the prompt",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--bead-json",
        help="Bead JSON string (if not reading from stdin)",
    )
    source.add_argument("--bead-id", help="Load a live bead by ID through bd")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository used for --bead-id bd lookup",
    )
    args = parser.parse_args()

    # strict=False: bd show --json can emit raw control chars (tabs/newlines)
    # inside string values when a bead description embeds code blocks. Without
    # this flag json rejects such payloads with "Invalid control character at".
    if args.bead_id:
        data = load_live_bead(args.bead_id, args.repo_root)
    elif args.bead_json:
        data = json.loads(args.bead_json, strict=False)
    else:
        data = json.load(sys.stdin, strict=False)

    # bd show returns a list
    bead = data[0] if isinstance(data, list) else data

    from contract_loader import resolve_contract

    contract = resolve_contract(repo_root=args.repo_root)
    content_sha = compute_content_sha(
        bead, label_families=contract["label_families"]
    )
    reviewer_sha = compute_reviewer_sha(
        args.reviewer_skill_path, args.reviewer_agent_path
    )
    contract_sha = contract["contract_sha"]

    print(
        json.dumps(
            {
                "content_sha": content_sha,
                "reviewer_sha": reviewer_sha,
                "contract_sha": contract_sha,
            }
        )
    )
