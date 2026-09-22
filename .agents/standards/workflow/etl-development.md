# ETL Development Standard

## Principle

Every ETL path follows a three-phase workflow: **Inspect → Implement → Verify**.
Never map blindly against a data source — always inspect the real structure
first, then validate against real data.

## Source of truth

The live database is the authority for source shape. The catalog and inventory are indexes
of that database, not replacements for it. ADRs record decisions, not source facts.
Database-backed fixtures are generated, never authored.
When choosing a read surface, prefer views before tables before hand-written joins:
a vendor view is the vendor's own documentation of how tables combine.

Regenerate dated schema artifacts with the adapter CLI (`discover`, `schema`,
`schema-verify`). Fail-closed freshness and drift belong to that CLI and
`@polaris/adapter-testkit`, not to a Library generator. Do not treat a committed
JSON inventory as ground truth.

## Target-side structural validation

Expected FHIR resources are validated structurally against the pinned
Implementation Guide and re-confirmed when the IG pin moves. The project must
name its validation command (typically the existing `fhir-validation` skill
invocation). If none exists, a reviewer records that absence as a finding.

## Reviewer live-check

At least one review of an adapter change verifies column names, read surface,
and value space against the live source, not against repository fixtures or
inventories that agree with the code under review.

## Phase 1: Inspect (BEFORE the implementation)

Before writing mappers, row interfaces, or transformation logic:

1. **Inspect the schema**: read column names, data types (int/varchar/datetime/money/bit/...), and nullable constraints from the source database
2. **Read sample data**: look at 3-5 real rows to understand value ranges, NULL frequency, encoding, and edge cases
3. **Reconcile the row interface**: validate TypeScript/Python types against the real schema — umlauts (Straße vs Strasse), aliases (AS clauses), optional fields

Use a toolbox or describe tool when one exists:
```bash
bun run pvs:werkzeugbox:describe <table>
```

Without such a tool: run the adapter CLI `discover` / `schema` / `sample` against
the live database. Do not inspect a hand-written inventory in place of the
database. Do not paste catalog SQL when the adapter CLI exists.

## Phase 2: Implement

- Row interfaces matching the inspected schema exactly
- Mapper functions with explicit handling for NULL, falsy values (0 is a valid int!), and date formats
- Anonymization: identify PII fields and pass the `--anonymize` flag through

## Phase 3: Verify (AFTER the implementation)

1. **Dry run with a limit**: test the mapper against real data WITHOUT writing to the target system
   ```bash
   bun run pvs:x-isynet:sync --table=<new-table> --limit=50 --dry-run
   ```
2. **Live run with a limit**: push a small amount into the target system and check the result
   ```bash
   bun run pvs:x-isynet:sync --table=<new-table> --limit=50
   ```
3. **Target validation**: spot-check the loaded resources in the target system (for example a FHIR bundle or a DB query)

## Checklist

- [ ] Source table schema inspected (columns + types) against the live database
- [ ] Vendor views considered before tables and before hand-written joins
- [ ] Sample data reviewed (edge cases, NULLs, encoding)
- [ ] Row interface and types match the real schema
- [ ] Mapper implemented with NULL/falsy handling
- [ ] PII fields identified and anonymization implemented
- [ ] DB-backed fixtures generated with adapter CLI `fixtures` through the declared anonymization boundary
- [ ] Dry run with --limit successful (no mapper errors)
- [ ] Live run with --limit successful (data correct in the target system)
- [ ] Expected FHIR resources validated against the pinned Implementation Guide
- [ ] Reviewer live-check of column names, read surface, and value space recorded
