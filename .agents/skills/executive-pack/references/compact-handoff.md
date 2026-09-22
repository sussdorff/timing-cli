# Compact implementation handoff

The logical implementation owner remains responsible for the candidate when a fresh
implementation session takes over. A replacement is valid only at a clean committed
worktree candidate with no pending repair dispatch. Call
`scripts/pack_review_contract.py:create_implementation_handoff`, then consume the
result with `accept_implementation_handoff` when repair convergence is active.
This contract rotates an implementation session only. It never rotates or replaces the
invoking repository delivery owner.

The handoff contains only:

- the Bead contract and applicable ADR references;
- the committed candidate SHA;
- open work and every remaining accepted finding;
- relevant repository paths and focused test or review evidence; and
- the stable logical owner plus old-to-new session lineage.

References point to repository material and evidence instead of embedding large file
contents. Never forward conversation chronology, chat history, transcripts, messages,
or a general session summary. Dispatch the new session without parent history
inheritance (`fork_turns="none"` where supported). Stop the old writing session before
dispatching the new one; after acceptance, only the new session may write or record
repair rounds. This is an internal delivery transition and requires no human approval.

The optional Luna coordination profile follows the same state boundary. Reduce an
advisor answer to the decision, remaining uncertainty, and repository or evidence
pointers in the coordinator packet. Do not place advisor transcripts in an
implementation handoff or add the advisor to the writer lineage.

STATUS: The helper validates the compact shape, owner and finding continuity, distinct
session IDs, current Git HEAD, ancestry from the prior candidate, and a clean worktree.
It cannot prove that an external writer has stopped; the repository delivery owner
enforces that behavioral boundary.

Optional Sub-Packs keep the fixed session bindings and receipts enforced by
`subpack_contract.py`. Their prompts still use compact inputs and every member review
starts in a fresh bounded context, but session rotation inside a Sub-Pack or its parent
repair actor is outside this handoff seam. If one of those bound sessions is lost, use
the existing typed failure or serial fallback instead of rebinding it.
