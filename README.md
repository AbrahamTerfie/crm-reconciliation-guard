# CRM Reconciliation Guard

A small, runnable automation-repair project: audit a CSV feed against a CRM export, explain unsafe records, and prepare a proposed next snapshot without changing a CRM.

**Portfolio demonstration, not client work.** All bundled names, organizations and `.test` addresses are synthetic. This project does not claim a production deployment or measured business savings.

## The failure being repaired

A naive import compares email addresses literally, chooses the last duplicate record, and overwrites fields even when the feed contains blanks. The result can be duplicate contacts, lost names, and silently conflicting updates.

This replacement makes the rules explicit:

- Trim surrounding whitespace and match email case-insensitively.
- Quarantine every duplicate source record and every ambiguous target match.
- Reject malformed email identifiers with a deliberately simple validation rule.
- Preserve existing values when incoming fields are blank.
- Generate deterministic create/update proposals and a local CSV preview.
- Retain target-only contacts. Never delete contacts or call external services.
- Detect a changed target snapshot before applying an in-memory plan.

## Run in under a minute

Python 3.10+ is required. Runtime and tests use only the standard library; no installation or credentials are needed.

```bash
python -m unittest discover -s tests -v
python -m crm_guard --source examples/incoming.csv --target examples/crm.csv --output output/demo
```

The demo intentionally exits **2**, meaning that review issues were found and reports were written. Expected summary:

```json
{"creates": 1, "issues": 6, "source_rows": 7, "target_rows": 4, "unchanged": 1, "updates": 1}
```

Inspect `output/demo/plan.json` and `output/demo/target-preview.csv`. These are local proposals, not a CRM import performed on your behalf. Output directories must not already exist, protecting previous runs from accidental overwrite.

### Verify the repaired flow is repeatable

```bash
python -m crm_guard --source examples/incoming.csv --target output/demo/target-preview.csv --output output/rerun
```

Expected: zero creates, zero updates, three unchanged eligible records, and the same six unresolved issues. Exit 2 remains correct: rerunning does not resolve conflicting source or target data.

## Outputs and exit codes

- `plan.json`: schema version, target fingerprint, aggregate counts, issue locations and proposed changes.
- `target-preview.csv`: full candidate snapshot, including untouched target records; **not** a standalone CRM delta/import file.
- Exit `0`: audit succeeded with no issues.
- Exit `2`: audit succeeded but one or more records need review.
- Exit `1`: input, schema, encoding, or filesystem error. A filesystem failure can leave partial output; remove the incomplete directory deliberately before retrying.

Issue row numbers are CSV record positions with the header counted as row 1, not physical line numbers for multiline quoted fields. The summary counts issue records on both sides, not unique people.

## Architecture

`CSV exports → schema validation → normalized matching → conflict quarantine → change plan → local preview`

- `crm_guard/core.py`: pure reconciliation logic, target fingerprint, CSV boundary functions.
- `crm_guard/__main__.py`: CLI and exit-code contract.
- `tests/test_core.py`: 18 regression and integration tests.
- `docs/repair-walkthrough.md`: diagnosis, tradeoffs, and a short demo script.
- `docs/github-actions-tests.yml`: inactive CI template for Python 3.10–3.13. The current GitHub OAuth grant lacks workflow scope, so remote CI is not enabled. An authorized maintainer can copy this to `.github/workflows/tests.yml` later.

## Scope and safety

The CSV contract requires `email,name,company`; extra columns are ignored and omitted from the preview. Do not use the preview as a replacement for an export containing other required fields. Treat generated plans and CSVs as sensitive if you substitute real contact data. Console summaries and issue records omit raw contact values, but the changes and preview necessarily contain them.

This is an educational prototype, not a production CRM adapter. Email case folding is a documented business policy, not a claim about every mail server. Email validation is intentionally not full RFC validation. Plus-addresses and dots are not rewritten. Conflicts require a human decision; no “last writer wins.” Inputs are loaded in memory, and there is no connector, network retry layer, deletion support, field-level consent model, or transactional CRM write path.

CSV output preserves original field content and may contain spreadsheet formulas if inputs are untrusted. Inspect it with a text editor or safe CSV viewer, not an auto-evaluating spreadsheet. A production adapter should add authentication, stable CRM IDs, optimistic concurrency, field mapping, redaction/retention controls, streaming for large files, and rate-limit handling.
