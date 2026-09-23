"""Deterministic admission and progression for Executive Sub-Pack waves."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import posixpath
import re
import subprocess
import tomllib
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

CONTRACT = "executive_subpack_v2"
EVIDENCE = "executive_subpack_evidence_v1"
BINDING = "executive_subpack_session_binding_v1"
RECEIPT = "executive_subpack_session_receipt_v1"
ACPX_EVIDENCE = "cognovis.acpx-transport-evidence.v1"
AGENT_EVIDENCE = "cognovis.agent-evidence.v1"
CCORE_TRANSPORTS = frozenset({"ccore_agent", "ccore_acpx"})
NATIVE_EVIDENCE = "executive_subpack_native_subagent_evidence_v1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
POINTER_RE = re.compile(r"`([^`]+)`")


class SubpackContractError(ValueError):
    """Raised when a Sub-Pack plan or transition violates the contract."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SubpackContractError(f"{field} must be non-empty text")
    return value.strip()


def _sha(value: object, field: str) -> str:
    result = _text(value, field)
    if not SHA_RE.fullmatch(result):
        raise SubpackContractError(f"{field} must be a full lowercase Git SHA")
    return result


def _list(value: object, field: str, *, empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not empty):
        raise SubpackContractError(f"{field} must be a list")
    result = [_text(item, field) for item in value]
    if len(result) != len(set(result)):
        raise SubpackContractError(f"{field} must contain unique values")
    return result


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SubpackContractError(f"cannot read JSON from {path}: {exc}") from exc


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_digest(path: Path) -> str:
    try:
        return _digest_bytes(path.read_bytes())
    except OSError as exc:
        raise SubpackContractError(f"cannot read evidence artifact {path}: {exc}") from exc


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise SubpackContractError(
            f"git {' '.join(args)} failed: {(result.stderr or result.stdout).strip()}"
        )
    return result.stdout.strip()


def _commit(repository: Path, value: object, field: str) -> str:
    result = _sha(value, field)
    _git(repository, "cat-file", "-e", f"{result}^{{commit}}")
    return result


def _ancestor(repository: Path, ancestor: str, descendant: str, field: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repository), "merge-base", "--is-ancestor", ancestor, descendant],
        capture_output=True,
        check=False,
    )
    if result.returncode == 1:
        raise SubpackContractError(f"{field}: {ancestor} is not an ancestor of {descendant}")
    if result.returncode:
        raise SubpackContractError(f"cannot validate {field}: {result.stderr.decode().strip()}")


def _worktrees(repository: Path) -> set[str]:
    return {
        str(Path(line[9:]).resolve())
        for line in _git(repository, "worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    }


def _binding(value: object, field: str) -> dict[str, str]:
    if not isinstance(value, dict) or value.get("contract") != BINDING:
        raise SubpackContractError(f"{field} must use {BINDING}")
    transport = _text(value.get("transport"), f"{field}.transport")
    if transport not in {*CCORE_TRANSPORTS, "native_subagent"}:
        raise SubpackContractError(
            f"{field}.transport must be ccore_agent, ccore_acpx, or native_subagent"
        )
    return {
        "contract": BINDING,
        "transport": transport,
        "session_name": _text(value.get("session_name"), f"{field}.session_name"),
        "adapter": _text(value.get("adapter"), f"{field}.adapter"),
        "cwd": str(Path(_text(value.get("cwd"), f"{field}.cwd")).resolve()),
    }


def _receipt(value: object, binding: Mapping[str, str], field: str, candidate: str) -> dict[str, str]:
    if not isinstance(value, dict) or value.get("contract") != RECEIPT:
        raise SubpackContractError(f"{field} must use {RECEIPT}")
    if value.get("session_name") != binding["session_name"]:
        raise SubpackContractError(f"{field} names the wrong session")
    if value.get("candidate_sha") != candidate:
        raise SubpackContractError(f"{field} is bound to a different candidate")
    if str(Path(_text(value.get("cwd"), f"{field}.cwd")).resolve()) != binding["cwd"]:
        raise SubpackContractError(f"{field} names the wrong worktree")
    path = Path(_text(value.get("transport_evidence_path"), f"{field}.path"))
    digest = _text(value.get("transport_evidence_sha256"), f"{field}.sha256")
    if _file_digest(path) != digest:
        raise SubpackContractError(f"{field} transport evidence digest does not match")
    evidence = _load(path)
    if not isinstance(evidence, dict):
        raise SubpackContractError(f"{field} evidence must be an object")
    if binding["transport"] in CCORE_TRANSPORTS:
        contract = evidence.get("contract")
        if contract == AGENT_EVIDENCE:
            _text(evidence.get("session_id"), f"{field}.session_id")
            _text(evidence.get("stop_reason"), f"{field}.stop_reason")
        elif contract == ACPX_EVIDENCE:
            if evidence.get("stop_reason") != "end_turn":
                raise SubpackContractError(
                    f"{field} must reference successful ccore dispatch evidence"
                )
        else:
            raise SubpackContractError(
                f"{field} must reference successful ccore agent or ACPX evidence"
            )
        session_id = _text(evidence.get("session_id"), f"{field}.session_id")
    else:
        if evidence.get("contract") != NATIVE_EVIDENCE or evidence.get("status") != "completed":
            raise SubpackContractError(f"{field} must reference completed native-subagent evidence")
        if str(Path(_text(evidence.get("cwd"), f"{field}.evidence.cwd")).resolve()) != binding["cwd"]:
            raise SubpackContractError(f"{field} native evidence names the wrong worktree")
        session_id = _text(evidence.get("session_id"), f"{field}.session_id")
    return {
        "contract": RECEIPT,
        "session_name": binding["session_name"],
        "cwd": binding["cwd"],
        "transport_evidence_path": str(path.resolve()),
        "transport_evidence_sha256": digest,
        "transport": binding["transport"],
        "actual_session_id": session_id,
        "answer_sha256": _text(evidence.get("answer_sha256"), f"{field}.answer_sha256"),
        "candidate_sha": candidate,
    }


def _receipt_digests(value: object) -> set[str]:
    if isinstance(value, dict):
        own = {value["transport_evidence_sha256"]} if value.get("contract") == RECEIPT else set()
        return own | set().union(*(_receipt_digests(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_receipt_digests(item) for item in value), set())
    return set()


def _require_fresh_receipts(state: object, *receipts: Mapping[str, str]) -> None:
    digests = [receipt["transport_evidence_sha256"] for receipt in receipts]
    if len(digests) != len(set(digests)) or set(digests) & _receipt_digests(state):
        raise SubpackContractError("transport evidence may authorize exactly one transition")


def _interval(value: object, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise SubpackContractError(f"{field} must be an object")
    start = _text(value.get("started_at"), f"{field}.started_at")
    end = _text(value.get("ended_at"), f"{field}.ended_at")
    try:
        start_dt, end_dt = datetime.fromisoformat(start), datetime.fromisoformat(end)
    except (TypeError, ValueError) as exc:
        raise SubpackContractError(f"{field} must use ISO-8601 timestamps") from exc
    if start_dt.tzinfo is None or end_dt.tzinfo is None:
        raise SubpackContractError(f"{field} timestamps must include UTC offsets")
    if end_dt < start_dt:
        raise SubpackContractError(f"{field}.ended_at precedes started_at")
    return {"started_at": start, "ended_at": end}


def _evidence(value: object, kind: str, candidate: str, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("contract") != EVIDENCE:
        raise SubpackContractError(f"{field} must use {EVIDENCE}")
    if value.get("kind") != kind or value.get("candidate_sha") != candidate:
        raise SubpackContractError(f"{field} is not bound to {kind} on {candidate}")
    path = Path(_text(value.get("artifact_path"), f"{field}.artifact_path"))
    digest = _text(value.get("artifact_sha256"), f"{field}.artifact_sha256")
    if _file_digest(path) != digest:
        raise SubpackContractError(f"{field} artifact digest does not match")
    return {
        "contract": EVIDENCE,
        "kind": kind,
        "candidate_sha": candidate,
        "artifact_path": str(path.resolve()),
        "artifact_sha256": digest,
        "interval": _interval(value.get("interval"), f"{field}.interval"),
        "scope": _list(value.get("scope"), f"{field}.scope"),
    }


def _dependencies(record: Mapping[str, Any]) -> list[str]:
    raw = record.get("dependencies", [])
    if not isinstance(raw, list):
        raise SubpackContractError("Bead dependencies must be a list")
    return [
        _text(item.get("id"), "dependency id")
        for item in raw
        if isinstance(item, dict) and item.get("dependency_type", "blocks") == "blocks"
    ]


def _prefix(pattern: str) -> str:
    parts = []
    for part in pattern.split("/"):
        if any(character in part for character in "*?["):
            break
        parts.append(part)
    return "/".join(parts).rstrip("/")


def _pattern(value: object, field: str) -> str:
    raw = _text(value, field).replace("\\", "/")
    normalized = posixpath.normpath(raw).removeprefix("./")
    if normalized in {"", ".", ".."} or normalized.startswith(("../", "/")):
        raise SubpackContractError(f"{field} must stay repository-relative")
    return normalized.casefold()


def _overlap(left: str, right: str) -> bool:
    if left == right or fnmatch(left, right) or fnmatch(right, left):
        return True
    one, two = _prefix(left), _prefix(right)
    if not one or not two:
        return True
    return bool(one and two and (one == two or one.startswith(f"{two}/") or two.startswith(f"{one}/")))


def _covers(path: str, pattern: str) -> bool:
    prefix = _prefix(pattern)
    if any(character in pattern for character in "*?["):
        return fnmatch(path, pattern)
    return path == prefix or path.startswith(f"{prefix}/")


def _subpack(state: dict[str, Any], subpack_id: str) -> dict[str, Any]:
    for item in state["subpacks"]:
        if item["id"] == subpack_id:
            return item
    raise SubpackContractError(f"unknown Sub-Pack: {subpack_id}")


def _member_loops(
    value: object,
    item: Mapping[str, Any],
    bead_commits: Mapping[str, str],
    owner_session_id: str,
    forbidden_actual_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(item["ordered_bead_ids"]):
        raise SubpackContractError("member_loops must map every Sub-Pack Bead exactly once")
    normalized = {}
    owner_name = item["session_binding"]["session_name"]
    if owner_session_id in forbidden_actual_ids:
        raise SubpackContractError("Sub-Pack owner reuses an actual wave session")
    used_actual_ids = {owner_session_id} | forbidden_actual_ids
    for bead_id in item["ordered_bead_ids"]:
        loop = value[bead_id]
        bindings = item["member_actor_bindings"][bead_id]
        if not isinstance(loop, dict) or not isinstance(loop.get("rounds"), list) or not loop["rounds"]:
            raise SubpackContractError(f"member loop {bead_id} must contain rounds")
        rounds = []
        implementer_id = reviewer_id = None
        for index, raw_round in enumerate(loop["rounds"]):
            if not isinstance(raw_round, dict):
                raise SubpackContractError(f"member loop {bead_id} round must be an object")
            round_candidate = _sha(raw_round.get("candidate_sha"), f"{bead_id}.rounds[{index}].candidate_sha")
            implementation = _receipt(raw_round.get("implementation_receipt"), bindings["implementer"], f"{bead_id}.rounds[{index}].implementation", round_candidate)
            review = _receipt(raw_round.get("review_receipt"), bindings["reviewer"], f"{bead_id}.rounds[{index}].review", round_candidate)
            verdict = _text(raw_round.get("verdict"), f"{bead_id}.rounds[{index}].verdict")
            if verdict not in {"repair_required", "accepted"}:
                raise SubpackContractError("member verdict must be repair_required or accepted")
            implementation_interval = _interval(raw_round.get("implementation_interval"), f"{bead_id}.rounds[{index}].implementation_interval")
            review_interval = _interval(raw_round.get("review_interval"), f"{bead_id}.rounds[{index}].review_interval")
            implementer_id = implementer_id or implementation["actual_session_id"]
            reviewer_id = reviewer_id or review["actual_session_id"]
            if implementation["actual_session_id"] != implementer_id:
                raise SubpackContractError(f"{bead_id} repairs must return to the same implementer session")
            if review["actual_session_id"] != reviewer_id:
                raise SubpackContractError(f"{bead_id} reviews must remain in the same reviewer session")
            rounds.append({
                "implementation_receipt": implementation,
                "review_receipt": review,
                "implementation_interval": implementation_interval,
                "review_interval": review_interval,
                "verdict": verdict,
            })
        if rounds[-1]["verdict"] != "accepted" or any(round_["verdict"] == "accepted" for round_ in rounds[:-1]):
            raise SubpackContractError(f"{bead_id} must end with exactly one accepted review")
        if rounds[-1]["implementation_receipt"]["candidate_sha"] != bead_commits[bead_id]:
            raise SubpackContractError(f"{bead_id} accepted round must bind its final commit")
        actor_names = {bindings["implementer"]["session_name"], bindings["reviewer"]["session_name"]}
        if len(actor_names) != 2 or owner_name in actor_names or implementer_id == reviewer_id:
            raise SubpackContractError(f"{bead_id} owner, implementer, and reviewer must be distinct")
        if implementer_id in used_actual_ids or reviewer_id in used_actual_ids:
            raise SubpackContractError(f"{bead_id} actor reuses an actual owner or member session")
        used_actual_ids.update({implementer_id, reviewer_id})
        normalized[bead_id] = {"rounds": rounds, "final_commit_sha": bead_commits[bead_id]}
    return normalized


def _require_next(state: dict[str, Any], subpack_id: str) -> None:
    index = len(state["integrated_subpacks"])
    expected = state["integration_order"][index] if index < len(state["integration_order"]) else None
    if expected != subpack_id:
        raise SubpackContractError(f"integration order requires {expected}, not {subpack_id}")


def admit(plan: dict[str, Any], records: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Admit a wave from caller topology and repository-local live Bead records."""
    if "bead_dependencies" in plan:
        raise SubpackContractError("bead_dependencies is derived from live bd state")
    repository = Path(_text(plan.get("repository"), "repository")).resolve()
    linked = _worktrees(repository)
    parent = str(Path(_text(plan.get("parent_worktree"), "parent_worktree")).resolve())
    if parent not in linked:
        raise SubpackContractError("parent_worktree is not linked to repository")
    base = _commit(repository, plan.get("base_sha"), "base_sha")
    beads = _list(plan.get("ordered_bead_ids"), "ordered_bead_ids")
    parent_binding = _binding(plan.get("parent_session_binding"), "parent_session_binding")
    parent_repair_binding = _binding(
        plan.get("parent_repair_session_binding"), "parent_repair_session_binding"
    )
    if parent_binding["cwd"] != parent:
        raise SubpackContractError("parent session binding must use parent_worktree")
    if parent_repair_binding["cwd"] != parent:
        raise SubpackContractError("parent repair binding must use parent_worktree")
    raw_subpacks = plan.get("subpacks")
    if not isinstance(raw_subpacks, list) or len(raw_subpacks) < 2:
        raise SubpackContractError("subpacks must contain at least two shards")
    subpacks = []
    for raw in raw_subpacks:
        if not isinstance(raw, dict):
            raise SubpackContractError("each Sub-Pack must be an object")
        member_ids = _list(raw.get("ordered_bead_ids"), "Sub-Pack ordered_bead_ids")
        worktree = str(Path(_text(raw.get("worktree"), "Sub-Pack worktree")).resolve())
        binding = _binding(raw.get("session_binding"), "Sub-Pack session_binding")
        declared = raw.get("declared_write_sets")
        actor_bindings = raw.get("member_actor_bindings")
        if worktree not in linked or binding["cwd"] != worktree:
            raise SubpackContractError("Sub-Pack must bind a linked worktree")
        if not isinstance(declared, dict) or set(declared) != set(member_ids):
            raise SubpackContractError("declared_write_sets must map every member")
        if not isinstance(actor_bindings, dict) or set(actor_bindings) != set(member_ids):
            raise SubpackContractError("member_actor_bindings must map every member")
        normalized_actors = {}
        for bead_id in member_ids:
            actors = actor_bindings[bead_id]
            if not isinstance(actors, dict) or set(actors) != {"implementer", "reviewer"}:
                raise SubpackContractError(f"{bead_id} must bind implementer and reviewer")
            normalized_actors[bead_id] = {
                role: _binding(actors[role], f"{bead_id}.{role}")
                for role in ("implementer", "reviewer")
            }
            if any(actor["cwd"] != worktree for actor in normalized_actors[bead_id].values()):
                raise SubpackContractError(f"{bead_id} actors must run in the Sub-Pack worktree")
        subpacks.append(
            {
                "id": _text(raw.get("id"), "Sub-Pack id"),
                "ordered_bead_ids": member_ids,
                "worktree": worktree,
                "session_binding": binding,
                "member_actor_bindings": normalized_actors,
                "declared_write_sets": {
                    key: [_pattern(pattern, f"write set {key}") for pattern in _list(declared[key], f"write set {key}")]
                    for key in member_ids
                },
                "status": "active",
            }
        )
    for values, label in (
        ([item["id"] for item in subpacks], "id"),
        ([item["worktree"] for item in subpacks], "worktree"),
        ([item["session_binding"]["session_name"] for item in subpacks], "session name"),
    ):
        if len(values) != len(set(values)):
            raise SubpackContractError(f"each Sub-Pack {label} must be unique")
    if parent in {item["worktree"] for item in subpacks}:
        raise SubpackContractError("parent and shard worktrees must differ")
    if parent_binding["session_name"] in {item["session_binding"]["session_name"] for item in subpacks}:
        raise SubpackContractError("parent and shard sessions must differ")
    all_session_names = [parent_binding["session_name"], parent_repair_binding["session_name"]]
    for item in subpacks:
        all_session_names.append(item["session_binding"]["session_name"])
        all_session_names.extend(
            binding["session_name"]
            for actors in item["member_actor_bindings"].values()
            for binding in actors.values()
        )
    if len(all_session_names) != len(set(all_session_names)):
        raise SubpackContractError("Pack owner, Sub-Pack owners, implementers, and reviewers must use distinct sessions")
    partition = [bead for item in subpacks for bead in item["ordered_bead_ids"]]
    if len(partition) != len(set(partition)) or set(partition) != set(beads):
        raise SubpackContractError("Sub-Pack partition must contain every Bead once")
    order = _list(plan.get("integration_order"), "integration_order")
    if set(order) != {item["id"] for item in subpacks}:
        raise SubpackContractError("integration_order must contain every Sub-Pack")
    if set(beads) - set(records):
        raise SubpackContractError("live Bead snapshot is incomplete")
    owner = {bead: item["id"] for item in subpacks for bead in item["ordered_bead_ids"]}
    position = {bead: index for item in subpacks for index, bead in enumerate(item["ordered_bead_ids"])}
    dependencies = []
    for bead in beads:
        for dependency in _dependencies(records[bead]):
            if dependency not in owner:
                if dependency not in records or records[dependency].get("status") != "closed":
                    raise SubpackContractError(f"{bead} has unresolved external dependency {dependency}")
                continue
            if owner[bead] != owner[dependency]:
                raise SubpackContractError(f"cross-Sub-Pack dependency: {bead} depends on {dependency}")
            if position[dependency] >= position[bead]:
                raise SubpackContractError(f"Sub-Pack order violates dependency for {bead}")
            dependencies.append([bead, dependency])
    patterns = [
        (item["id"], bead, pattern)
        for item in subpacks
        for bead, declared in item["declared_write_sets"].items()
        for pattern in declared
    ]
    for index, (left_shard, left_bead, left) in enumerate(patterns):
        for right_shard, right_bead, right in patterns[index + 1 :]:
            if left_shard != right_shard and _overlap(left, right):
                raise SubpackContractError(f"declared write overlap: {left_bead}:{left} and {right_bead}:{right}")
    advisories = []
    pointer_analysis = {}
    pointers = {}
    for bead in beads:
        body = "\n".join(
            str(records[bead].get(field, ""))
            for field in ("description", "acceptance_criteria", "notes")
        )
        match = re.search(
            r"(?ims)^## Context Pointers\s*$\n(.*?)(?=^##\s|\Z)", body
        )
        pointers[bead] = set(POINTER_RE.findall(match.group(1))) if match else set()
        pointer_analysis[bead] = {
            "pointers_analyzable": match is not None,
            "context_pointers": sorted(pointers[bead]),
        }
    for index, left in enumerate(beads):
        for right in beads[index + 1 :]:
            overlap = sorted(pointers[left] & pointers[right])
            if owner[left] != owner[right] and overlap:
                advisories.append({"bead_ids": [left, right], "context_pointer_overlap": overlap, "status": "heuristic_admission_signal_only"})
    snapshot = {key: deepcopy(records[key]) for key in sorted(records)}
    return {
        "contract": CONTRACT,
        "pack_id": _text(plan.get("pack_id"), "pack_id"),
        "repository": str(repository),
        "parent_worktree": parent,
        "parent_session_binding": parent_binding,
        "parent_repair_session_binding": parent_repair_binding,
        "base_sha": base,
        "current_parent_sha": base,
        "ordered_bead_ids": beads,
        "bead_dependencies": dependencies,
        "bead_snapshot": snapshot,
        "bead_snapshot_sha256": _digest_bytes(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()),
        "admission_advisories": advisories,
        "context_pointer_analysis": pointer_analysis,
        "subpacks": subpacks,
        "integration_order": order,
        "integrated_subpacks": [],
        "remaining_bead_ids": beads.copy(),
        "wave_status": "active",
        "final_gate_evidence": None,
        "ready_for_final_review": False,
    }


def complete_subpack(state: dict[str, Any], *, subpack_id: str, owner_session_receipt: dict[str, Any], candidate_sha: str, bead_commits: dict[str, str], member_loops: dict[str, Any], implementation_interval: dict[str, str]) -> dict[str, Any]:
    updated = deepcopy(state)
    item = _subpack(updated, subpack_id)
    if updated["wave_status"] != "active" or item["status"] != "active":
        raise SubpackContractError(f"Sub-Pack {subpack_id} is not active")
    repository = Path(updated["repository"])
    candidate = _commit(repository, candidate_sha, "candidate_sha")
    _ancestor(repository, updated["base_sha"], candidate, "candidate ancestry")
    if _git(Path(item["worktree"]), "rev-parse", "HEAD") != candidate:
        raise SubpackContractError("candidate_sha must equal the Sub-Pack worktree HEAD")
    actual_paths = _git(repository, "-c", "core.quotePath=false", "diff", "--name-only", updated["base_sha"], candidate).splitlines()
    declared_patterns = [
        pattern for patterns in item["declared_write_sets"].values() for pattern in patterns
    ]
    outside = [
        path for path in actual_paths if not any(_covers(path.casefold(), pattern) for pattern in declared_patterns)
    ]
    if outside:
        raise SubpackContractError(f"candidate changed paths outside declared write sets: {', '.join(outside)}")
    if not isinstance(bead_commits, dict) or set(bead_commits) != set(item["ordered_bead_ids"]):
        raise SubpackContractError("bead_commits must map every member")
    commits = {key: _commit(repository, value, f"commit for {key}") for key, value in bead_commits.items()}
    for key, commit in commits.items():
        _ancestor(repository, commit, candidate, f"commit for {key}")
    receipt = _receipt(owner_session_receipt, item["session_binding"], "owner_session_receipt", candidate)
    forbidden_ids = {
        actor["actual_session_id"]
        for shard in updated["subpacks"]
        for actor in ([shard.get("owner_session_receipt")] if shard.get("owner_session_receipt") else [])
    }
    forbidden_ids.update(
        round_[key]["actual_session_id"]
        for shard in updated["subpacks"]
        for loop in shard.get("member_loops", {}).values()
        for round_ in loop["rounds"]
        for key in ("implementation_receipt", "review_receipt")
    )
    forbidden_ids.update(
        value for value in (updated.get("actual_parent_session_id"), updated.get("actual_parent_repair_session_id")) if value
    )
    loops = _member_loops(member_loops, item, commits, receipt["actual_session_id"], forbidden_ids)
    new_receipts = [receipt] + [
        round_[key]
        for loop in loops.values()
        for round_ in loop["rounds"]
        for key in ("implementation_receipt", "review_receipt")
    ]
    _require_fresh_receipts(updated, *new_receipts)
    actor_ids = {
        round_[key]["actual_session_id"]
        for loop in loops.values()
        for round_ in loop["rounds"]
        for key in ("implementation_receipt", "review_receipt")
    } | {receipt["actual_session_id"]}
    if actor_ids & {
        value for value in (updated.get("actual_parent_session_id"), updated.get("actual_parent_repair_session_id")) if value
    }:
        raise SubpackContractError("Sub-Pack actor reuses an actual parent session")
    item.update({
        "status": "complete", "candidate_sha": candidate, "bead_commits": commits,
        "owner_session_receipt": receipt, "actual_owner_session_id": receipt["actual_session_id"],
        "member_loops": loops,
        "implementation_interval": _interval(implementation_interval, "implementation_interval"),
    })
    return updated


def reconcile_subpack(state: dict[str, Any], *, subpack_id: str, owner_session_receipt: dict[str, Any], parent_candidate_sha: str, reconciled_candidate_sha: str, verification_evidence: dict[str, Any], conflict_files: list[str]) -> dict[str, Any]:
    updated = deepcopy(state)
    _require_next(updated, subpack_id)
    item = _subpack(updated, subpack_id)
    if updated["wave_status"] != "active" or item["status"] != "complete":
        raise SubpackContractError(f"Sub-Pack {subpack_id} is not complete")
    repository = Path(updated["repository"])
    parent = _commit(repository, parent_candidate_sha, "parent_candidate_sha")
    if parent != updated["current_parent_sha"]:
        raise SubpackContractError("parent candidate is stale")
    candidate = _commit(repository, reconciled_candidate_sha, "reconciled_candidate_sha")
    receipt = _receipt(owner_session_receipt, item["session_binding"], "owner_session_receipt", candidate)
    _require_fresh_receipts(updated, receipt)
    if receipt["actual_session_id"] != item["actual_owner_session_id"]:
        raise SubpackContractError("reconciliation must return to the actual Sub-Pack owner session")
    _ancestor(repository, item["candidate_sha"], candidate, "candidate ancestry")
    _ancestor(repository, parent, candidate, "parent ancestry")
    item.update({
        "status": "reconciled", "reconciled_parent_sha": parent, "reconciled_candidate_sha": candidate,
        "reconciliation_owner_receipt": receipt,
        "verification_evidence": _evidence(verification_evidence, "reconciliation", candidate, "verification_evidence"),
        "conflict_files": _list(conflict_files, "conflict_files", empty=True),
    })
    return updated


def integrate_subpack(state: dict[str, Any], *, subpack_id: str, parent_session_receipt: dict[str, Any], parent_repair_session_receipt: dict[str, Any], merged_parent_sha: str, gate_evidence: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(state)
    _require_next(updated, subpack_id)
    item = _subpack(updated, subpack_id)
    if updated["wave_status"] != "active" or item["status"] != "reconciled":
        raise SubpackContractError(f"Sub-Pack {subpack_id} is not reconciled")
    repository = Path(updated["repository"])
    merged = _commit(repository, merged_parent_sha, "merged_parent_sha")
    receipt = _receipt(parent_session_receipt, updated["parent_session_binding"], "parent_session_receipt", merged)
    repair_receipt = _receipt(parent_repair_session_receipt, updated["parent_repair_session_binding"], "parent_repair_session_receipt", merged)
    _require_fresh_receipts(updated, receipt, repair_receipt)
    if receipt["actual_session_id"] == repair_receipt["actual_session_id"]:
        raise SubpackContractError("parent owner and repair actor must be distinct")
    if updated.get("actual_parent_session_id") not in {None, receipt["actual_session_id"]}:
        raise SubpackContractError("integration must use the actual persistent parent session")
    if updated.get("actual_parent_repair_session_id") not in {None, repair_receipt["actual_session_id"]}:
        raise SubpackContractError("integration must use the actual persistent parent repair session")
    shard_actor_ids = {
        actor["actual_session_id"]
        for shard in updated["subpacks"]
        for actor in ([shard.get("owner_session_receipt")] if shard.get("owner_session_receipt") else [])
    }
    shard_actor_ids.update(
        round_[key]["actual_session_id"]
        for shard in updated["subpacks"]
        for loop in shard.get("member_loops", {}).values()
        for round_ in loop["rounds"]
        for key in ("implementation_receipt", "review_receipt")
    )
    if {receipt["actual_session_id"], repair_receipt["actual_session_id"]} & shard_actor_ids:
        raise SubpackContractError("parent actor reuses an actual Sub-Pack session")
    _ancestor(repository, updated["current_parent_sha"], merged, "parent integration ancestry")
    _ancestor(repository, item["reconciled_candidate_sha"], merged, "Sub-Pack integration ancestry")
    item.update({"status": "integrated", "merged_parent_sha": merged, "focused_gate_evidence": _evidence(gate_evidence, "focused_integration_gate", merged, "gate_evidence")})
    updated["actual_parent_session_id"] = receipt["actual_session_id"]
    updated["actual_parent_repair_session_id"] = repair_receipt["actual_session_id"]
    updated["current_parent_sha"] = merged
    updated["integrated_subpacks"].append(subpack_id)
    updated["remaining_bead_ids"] = [bead for bead in updated["remaining_bead_ids"] if bead not in item["ordered_bead_ids"]]
    return _metrics(updated)


def record_final_gate(state: dict[str, Any], *, parent_session_receipt: dict[str, Any], candidate_sha: str, gate_evidence: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(state)
    if updated["wave_status"] != "active" or updated["remaining_bead_ids"]:
        raise SubpackContractError("all Sub-Packs must be integrated before the final gate")
    candidate = _commit(Path(updated["repository"]), candidate_sha, "candidate_sha")
    if candidate != updated["current_parent_sha"]:
        raise SubpackContractError("final gate must bind the current parent candidate")
    receipt = _receipt(parent_session_receipt, updated["parent_session_binding"], "parent_session_receipt", candidate)
    _require_fresh_receipts(updated, receipt)
    if receipt["actual_session_id"] != updated.get("actual_parent_session_id"):
        raise SubpackContractError("final gate must use the actual persistent parent session")
    updated["final_gate_evidence"] = _evidence(gate_evidence, "full_final_gate", candidate, "gate_evidence")
    updated["ready_for_final_review"] = True
    updated["wave_status"] = "ready_for_final_review"
    return _metrics(updated)


def record_parent_repair(state: dict[str, Any], *, repair_session_receipt: dict[str, Any], candidate_sha: str, repair_evidence: dict[str, Any], reason: str) -> dict[str, Any]:
    updated = deepcopy(state)
    if updated["wave_status"] not in {"active", "ready_for_final_review"}:
        raise SubpackContractError("wave is not eligible for parent repair")
    if updated.get("actual_parent_repair_session_id") is None:
        raise SubpackContractError("parent repair requires at least one completed integration")
    repository = Path(updated["repository"])
    candidate = _commit(repository, candidate_sha, "candidate_sha")
    receipt = _receipt(repair_session_receipt, updated["parent_repair_session_binding"], "repair_session_receipt", candidate)
    _require_fresh_receipts(updated, receipt)
    if receipt["actual_session_id"] != updated.get("actual_parent_repair_session_id"):
        raise SubpackContractError("parent repair must use the actual persistent repair session")
    _ancestor(repository, updated["current_parent_sha"], candidate, "parent repair ancestry")
    if _git(Path(updated["parent_worktree"]), "rev-parse", "HEAD") != candidate:
        raise SubpackContractError("parent repair candidate must equal parent worktree HEAD")
    if updated.get("final_gate_evidence"):
        updated.setdefault("superseded_final_gates", []).append(updated["final_gate_evidence"])
    updated["final_gate_evidence"] = None
    updated["ready_for_final_review"] = False
    updated["wave_status"] = "active"
    updated["current_parent_sha"] = candidate
    updated.setdefault("parent_repairs", []).append({
        "reason": _text(reason, "reason"),
        "candidate_sha": candidate,
        "repair_session_receipt": receipt,
        "repair_evidence": _evidence(repair_evidence, "parent_repair", candidate, "repair_evidence"),
    })
    return _metrics(updated)


def fail_subpack(state: dict[str, Any], *, subpack_id: str, reason: str) -> dict[str, Any]:
    updated = deepcopy(state)
    if updated["wave_status"] not in {"active", "failed"}:
        raise SubpackContractError("wave is not eligible for another Sub-Pack failure")
    item = _subpack(updated, subpack_id)
    if item["status"] not in {"active", "complete", "reconciled"}:
        raise SubpackContractError("Sub-Pack is not eligible for failure")
    item.update({"status": "failed", "failure_reason": _text(reason, "reason")})
    updated["wave_status"] = "failed"
    return updated


def abort_wave(state: dict[str, Any], *, reason: str) -> dict[str, Any]:
    updated = deepcopy(state)
    if updated["wave_status"] not in {"active", "failed", "ready_for_final_review"}:
        raise SubpackContractError("wave is not eligible for abort")
    updated.update({"wave_status": "aborted", "abort_reason": _text(reason, "reason"), "ready_for_final_review": False})
    return updated


def serial_fallback(state: dict[str, Any], *, reason: str) -> dict[str, Any]:
    updated = deepcopy(state)
    if updated["wave_status"] not in {"active", "failed", "aborted", "ready_for_final_review"}:
        raise SubpackContractError("wave is not eligible for serial fallback")
    updated["wave_status"] = "serial_fallback"
    updated["serial_fallback"] = {
        "reason": _text(reason, "reason"), "base_sha": updated["current_parent_sha"],
        "preserved_integrated_subpacks": updated["integrated_subpacks"].copy(),
        "remaining_bead_ids": updated["remaining_bead_ids"].copy(),
    }
    updated["ready_for_final_review"] = False
    return updated


def _seconds(interval: Mapping[str, str]) -> float:
    return (datetime.fromisoformat(interval["ended_at"]) - datetime.fromisoformat(interval["started_at"])).total_seconds()


def _metrics(state: dict[str, Any]) -> dict[str, Any]:
    implementation = [
        round_["implementation_interval"]
        for item in state["subpacks"]
        for loop in item.get("member_loops", {}).values()
        for round_ in loop["rounds"]
    ]
    spans = sorted((datetime.fromisoformat(item["started_at"]), datetime.fromisoformat(item["ended_at"])) for item in implementation)
    union = 0.0
    if spans:
        start, end = spans[0]
        for next_start, next_end in spans[1:]:
            if next_start <= end:
                end = max(end, next_end)
            else:
                union += (end - start).total_seconds()
                start, end = next_start, next_end
        union += (end - start).total_seconds()
    total = sum(_seconds(item) for item in implementation)
    overhead = [
        evidence["interval"]
        for item in state["subpacks"]
        for key in ("verification_evidence", "focused_gate_evidence")
        if (evidence := item.get(key))
    ]
    overhead.extend(
        round_["review_interval"]
        for item in state["subpacks"]
        for loop in item.get("member_loops", {}).values()
        for round_ in loop["rounds"]
    )
    if state.get("final_gate_evidence"):
        overhead.append(state["final_gate_evidence"]["interval"])
    state["observed_metrics"] = {
        "status": "observed_intervals_only_not_a_predictive_speed_claim",
        "implementation_total_seconds": total, "implementation_union_seconds": union,
        "implementation_overlap_seconds": max(0.0, total - union),
        "review_reconciliation_and_gate_seconds": sum(_seconds(item) for item in overhead),
        "conflict_file_count": sum(len(item.get("conflict_files", [])) for item in state["subpacks"]),
    }
    return state


def _registry_path() -> Path:
    override = os.environ.get("COGNOVIS_BEADS_REGISTRY")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base).expanduser() / "cognovis" / "beads-repos.toml"


def _issue_tracker_name(repo_root: str | Path) -> str | None:
    """Return github/forgejo when the checkout's registry entry names a tracker."""
    try:
        loaded = tomllib.loads(_registry_path().read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    checkout = Path(repo_root).expanduser().resolve()
    for entry in loaded.get("repository", []):
        raw = entry.get("path")
        if not raw:
            continue
        try:
            entry_path = Path(str(raw)).expanduser().resolve()
        except OSError:
            continue
        if entry_path != checkout:
            continue
        name = str(entry.get("tracker") or "").strip()
        if name in {"github", "forgejo"}:
            return name
        return None
    return None


def _live_beads(beads: list[str], repository: Path, bd_bin: str) -> dict[str, dict[str, Any]]:
    pending, records = list(beads), {}
    tracker = _issue_tracker_name(repository)
    while pending:
        bead = pending.pop(0)
        if bead in records:
            continue
        if not tracker:
            result = subprocess.run([bd_bin, "show", bead, "--json"], cwd=repository, text=True, capture_output=True, check=False)
            if result.returncode:
                raise SubpackContractError(f"bd show {bead} failed: {result.stderr.strip()}")
            payload = json.loads(result.stdout)
            record = payload[0] if isinstance(payload, list) and len(payload) == 1 else payload
            if not isinstance(record, dict):
                raise SubpackContractError(f"bd show {bead} did not return one object")
        else:
            result = subprocess.run(["ccore", "tracker", "show", bead], cwd=repository, text=True, capture_output=True, check=False)
            if result.returncode:
                raise SubpackContractError(f"ccore tracker show {bead} failed: {result.stderr.strip()}")
            payload = json.loads(result.stdout)
            data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
            if not isinstance(data, dict):
                raise SubpackContractError(f"ccore tracker show {bead} did not return one object")
            record = dict(data)
            record.setdefault("id", bead)
            record.setdefault("description", record.get("body") or "")
        records[bead] = record
        pending.extend(dependency for dependency in _dependencies(record) if dependency not in records)
    return records


def _persist(path: Path, state: dict[str, Any], *, create: bool = False) -> None:
    if create and path.exists():
        raise SubpackContractError(f"state file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


@contextmanager
def _lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(f"{path.suffix}.lock").open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    admit_parser = commands.add_parser("admit")
    for flag in ("plan-file", "state-file", "bead-repo"):
        admit_parser.add_argument(f"--{flag}", type=Path, required=True)
    admit_parser.add_argument("--bd-bin", default="bd")
    for name in ("complete", "reconcile", "integrate", "parent-repair", "final-gate", "fail", "abort", "fallback-serial", "show"):
        command = commands.add_parser(name)
        command.add_argument("--state-file", type=Path, required=True)
        if name in {"complete", "reconcile", "integrate", "fail"}:
            command.add_argument("--subpack-id", required=True)
        if name in {"complete", "reconcile"}:
            command.add_argument("--owner-session-receipt-file", type=Path, required=True)
        fields = {
            "complete": (("candidate-sha", str), ("bead-commits-file", Path), ("member-loops-file", Path), ("implementation-interval-file", Path)),
            "reconcile": (("parent-candidate-sha", str), ("reconciled-candidate-sha", str), ("verification-evidence-file", Path), ("conflict-files-file", Path)),
            "integrate": (("parent-session-receipt-file", Path), ("parent-repair-session-receipt-file", Path), ("merged-parent-sha", str), ("gate-evidence-file", Path)),
            "parent-repair": (("repair-session-receipt-file", Path), ("candidate-sha", str), ("repair-evidence-file", Path), ("reason", str)),
            "final-gate": (("parent-session-receipt-file", Path), ("candidate-sha", str), ("gate-evidence-file", Path)),
        }.get(name, ())
        for flag, kind in fields:
            command.add_argument(f"--{flag}", type=kind, required=True)
        if name in {"fail", "abort", "fallback-serial"}:
            command.add_argument("--reason", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        with _lock(args.state_file):
            if args.command == "admit":
                plan = _load(args.plan_file)
                if args.bead_repo.resolve() != Path(_text(plan.get("repository"), "repository")).resolve():
                    raise SubpackContractError("bead-repo must equal plan.repository")
                beads = _list(plan.get("ordered_bead_ids"), "ordered_bead_ids")
                state = admit(plan, _live_beads(beads, args.bead_repo, args.bd_bin))
                _persist(args.state_file, state, create=True)
            else:
                state = _load(args.state_file)
                if state.get("contract") != CONTRACT:
                    raise SubpackContractError(f"state is not {CONTRACT}")
                if args.command == "complete":
                    state = complete_subpack(state, subpack_id=args.subpack_id, owner_session_receipt=_load(args.owner_session_receipt_file), candidate_sha=args.candidate_sha, bead_commits=_load(args.bead_commits_file), member_loops=_load(args.member_loops_file), implementation_interval=_load(args.implementation_interval_file))
                elif args.command == "reconcile":
                    state = reconcile_subpack(state, subpack_id=args.subpack_id, owner_session_receipt=_load(args.owner_session_receipt_file), parent_candidate_sha=args.parent_candidate_sha, reconciled_candidate_sha=args.reconciled_candidate_sha, verification_evidence=_load(args.verification_evidence_file), conflict_files=_load(args.conflict_files_file))
                elif args.command == "integrate":
                    state = integrate_subpack(state, subpack_id=args.subpack_id, parent_session_receipt=_load(args.parent_session_receipt_file), parent_repair_session_receipt=_load(args.parent_repair_session_receipt_file), merged_parent_sha=args.merged_parent_sha, gate_evidence=_load(args.gate_evidence_file))
                elif args.command == "parent-repair":
                    state = record_parent_repair(state, repair_session_receipt=_load(args.repair_session_receipt_file), candidate_sha=args.candidate_sha, repair_evidence=_load(args.repair_evidence_file), reason=args.reason)
                elif args.command == "final-gate":
                    state = record_final_gate(state, parent_session_receipt=_load(args.parent_session_receipt_file), candidate_sha=args.candidate_sha, gate_evidence=_load(args.gate_evidence_file))
                elif args.command == "fail":
                    state = fail_subpack(state, subpack_id=args.subpack_id, reason=args.reason)
                elif args.command == "abort":
                    state = abort_wave(state, reason=args.reason)
                elif args.command == "fallback-serial":
                    state = serial_fallback(state, reason=args.reason)
                if args.command != "show":
                    _persist(args.state_file, state)
        print(json.dumps(state, indent=2, sort_keys=True))
        return 0
    except (SubpackContractError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": "subpack_contract_error", "message": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
