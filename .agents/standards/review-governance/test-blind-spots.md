# Test Blind Spots

Green tests are bounded evidence. Each blind spot below produced a real shipped-or-nearly-shipped defect that one or more review layers graded as passing.

| Blind spot | Mechanism | Documented evidence |
| --- | --- | --- |
| Agreement-only tests | The suite covers only the case where system A and system B agree; the risk lives entirely in the divergence path, which no test exercises | Explicit caller-supplied type silently overwritten by classifier — the only untested path (open-brain-hws) |
| Unit-green without persistence | Business-logic tests prove the computed value, not that it reaches the storage layer; a claimed field's actual write site in the data layer decides | Classifier output never reached the Postgres `type` column — column default persisted instead (open-brain-hws) |
| Mocked DB connections | Stubbed fetch/execute cannot surface SQL-planner-level errors; SQL-touching code needs executable MoC against a real database | `IndeterminateDatatypeError` from untyped bind parameter in `jsonb_build_object()`, invisible through TDD, pair, cold, and adversarial review (open-brain-slu) |
| Hand-authored fixtures | Fixtures set fields directly and are schema-valid without reproducing how real data populates them; grouping/join/dedup keys need live-data verification | `requesterId` frequently unpopulated on real data; fixtures masked it and the feature never triggered live (mira-76rux) |
| Shared-column writes | Persisting a new value into a column other pipelines key off silently auto-activates machinery never designed for that input; all readers of the column are checked before the write ships | LLM-inferred person mentions would have fed an unreviewed dedup/enrichment pipeline keyed on `type='person'` (open-brain-hws) |
| Duplicate logic blocks / dual entry points | Parallel code blocks (query vs browse mode, live gate vs backtest path) each need the new filter or gate; a fix landing in one block leaves the other silently wrong for identical input | `capture_status` filter in one of two blocks (open-brain-slu); fail-closed gate in `evaluateBillingCase()` but not `evaluate()` (polaris-lrgw3). Durable fix: extract one shared helper |
| Reachability vs correctness | Diff-scoped layers answer "does this code do what it claims"; none answers "does this code ever run". Only live UAT on the running stack proves a route reaches the changed code | Modified UI component was dead code — the live page defines its own inline columns (mira-4h07f) |
