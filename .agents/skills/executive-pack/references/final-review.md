## Final Pack perspectives

After the last member and repository gates:

1. Keep current implementation and documentation, invoking `doc-changelog-updater` when
   the delivery carries a material user-visible, API, configuration, deployment,
   operator-workflow, or developer-workflow change.
2. As the delivery owner, capture live claims and the signed resource registry: every
   admitted Bead AC/MoC and current documented capability claim, bound to the candidate.
3. Run agentic acceptance via `ccore acceptance run` through a fresh `uat-validator`
   against those signed resource boundaries. Acceptance applies only where the caller
   trust surface is provisioned: when the canary exits 3 with a
   `status: "not_configured"` result (no `AGENTIC_ACCEPTANCE_*` trust material on this
   host), record that typed result verbatim as explicit not-applicable acceptance
   evidence bound to the candidate and continue with the remaining perspectives — do
   not stop the delivery and do not ask the human to provision trust material.
   Recognize `not_configured` only from the typed canary output written to `--output`,
   never from your own judgment about the environment. On a provisioned host, any
   non-passing acceptance outcome (`failed`, `blocked`, exit 2) blocks delivery. Any source
   repair invalidates the acceptance result and requires a fresh run before those later
   reviews continue. The native first-party validator reaches real interfaces through
   the caller-owned bounded surface broker while authenticated host state and trust keys
   remain outside the validator capsule. For the authoritative acceptance command, run
   `ccore acceptance run --help`. Default transport is `codex-cli`. Use the `acpx`
   transport only with an explicit project `.acpxrc.json`. If `ccore` is absent, stop
   with `ccore_not_installed`; do not scan for or invoke skill-bundled Python files.
4. Run the final review the admitted preset requires over the whole Pack
   base-to-candidate diff. High Assurance: one complete different-family adversarial
   review by Reviewer 2, one security review, and every applicable project-specific
   perspective. Light: one fresh Reviewer 1 pass, different in family from the
   implementation actor, plus the same applicable project-specific perspectives, with
   Reviewer 2 and security recorded as `not_required`. Each produces distinct
   evidence; `not_applicable` must be explicit where permitted.
   `passed` means no accepted substantive finding remains; `changes_requested` carries
   actionable findings into triage; unavailable or invalid outcomes block.
5. Triage before repairing. Run `scripts/finding_triage.py` with the accepted findings,
   the Pack diff paths and the admitted AC references. Only its `repair` set enters
   convergence; its `deferred` set, with reasons, goes into the pull request text or a
   follow-up work order. A reviewer suggestion outside the Pack diff is not a repair.
   Consolidate the `repair` set into one implementation-owned repair
   lineage with `start_repair_convergence`, bound to the current logical implementation
   owner, implementation session and committed candidate. Repair convergence is a
   single cumulative closing bugfix phase over the whole Pack diff, not a re-run of the
   member sequence. One round is the default; the helper refuses a second round unless
   the delivery owner records a typed reason. Dispatch it as follows:

   - In normal serial execution, rotate once from the current implementation session to
     one fresh repair session through `create_implementation_handoff` and
     `accept_implementation_handoff`; the fresh session retains the same logical owner.
     In the Sub-Pack shape, use the already-bound parent-integration repair session and
     do not rebind it.
   - Authorize the repair turn with `authorize_repair_dispatch` before every dispatch. It
     refuses a foreign or replacement session and refuses any dispatch that carries
     fewer than all remaining findings, so one dispatch always holds the complete
     remaining set.
   - Dispatch the current repair implementer (the one fresh Sol-with-high-reasoning
     session in normal Codex execution, or the fixed Sub-Pack parent repair session)
     with that complete set at once, in the shared Pack worktree. It owns the whole
     cumulative repair diff, including any test it needs for its own fix, and its own
     focused verification.
   - That repair implementer is a repair actor, not a member loop. Do not re-enter
     `implementation-loop`, do not dispatch `tdd-test-author`, do not run a RED/GREEN
     slice choreography, and do not replay the ordered Bead sequence. Accepted
     findings here are cumulative bugfixes on an existing candidate, not new Bead
     implementations.
   - After each return, run focused verification and consume the matching pending
     dispatch with `record_repair_round`. If findings remain, authorize another turn to
     that same persistent repair session with the complete remaining set; do not create
     another implementer or commit an intermediate closing repair.
   - Once no accepted substantive finding remains, rerun the invalidated acceptance
     evidence required by step 3, run final focused verification, and create exactly one
     closing repair commit. Do not repeat every full perspective after each repair.
6. Interrupt normal progression only for disputed findings, contradictory
   recommendations, suspicious summaries, or intent mismatch. The delivery owner
   returns the typed disposition. Clean consistent evidence bypasses adjudication.

`scripts/pack_review_contract.py` validates these small evidence seams. It never selects
actors, parses role prose, freezes a candidate lifecycle, or exports internal review
state. The signed agentic-acceptance runtime is the installed `ccore acceptance run`
command; this skill does not ship a Python fallback.
