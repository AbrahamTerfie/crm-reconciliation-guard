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
- `target-preview.json`: full candidate snapshot and ordered columns for review in a plain-text editor or JSON viewer.
- `target-preview.csv`: full candidate snapshot, including untouched target records; **not** a standalone CRM delta/import file.
- Exit `0`: audit succeeded with no issues.
- Exit `2`: audit succeeded but one or more records need review.
- Exit `1`: input, schema, encoding, or filesystem error. A filesystem failure can leave partial output; remove the incomplete directory deliberately before retrying.

Issue row numbers are CSV record positions with the header counted as row 1, not physical line numbers for multiline quoted fields. The summary counts issue records on both sides, not unique people.

## Architecture

`CSV exports → schema validation → normalized matching → conflict quarantine → change plan → local preview`

- `crm_guard/core.py`: pure reconciliation logic, target fingerprint, CSV boundary functions.
- `crm_guard/__main__.py`: CLI and exit-code contract.
- `tests/test_core.py`: 35 regression and integration tests across test_core.py and test_safety.py.
- `docs/repair-walkthrough.md`: diagnosis, tradeoffs, and a short demo script.
- `docs/github-actions-tests.yml`: inactive CI template for Python 3.10–3.13. The current GitHub OAuth grant lacks workflow scope, so remote CI is not enabled. An authorized maintainer can copy this to `.github/workflows/tests.yml` later.

## Scope and safety

The CSV contract requires `email,name,company`. Extra target columns, their order, and their raw values are preserved on existing contacts, including untouched and quarantined rows. Core fields retain the original whitespace-trimming policy. Source extras are ignored, even if their names match target columns. New records have blank extra fields; IDs, consent and required custom values are not fabricated. This is not an automatically safe CRM import.

Header-only exports retain their schema. Blank/duplicate headers are rejected. Strict Python Excel-dialect CSV parsing rejects unterminated quotes and trailing garbage after closing quotes while accepting valid multiline/escaped-quote fields. This is not a universal dialect detector.

Plan schema version 2 includes explicit field-policy metadata. Fingerprints cover headers and extra values. Regenerate version 1 plans. Preview validation rejects unknown versions/actions, malformed or duplicate changes, and conflicting target identity counts. Validation is not authorization or cryptographic protection for edited plans. Programmatic callers should retain the CSVRows returned by read_csv to preserve headers on empty exports. Treat generated plans and CSVs as sensitive if you substitute real contact data. Console summaries and issue records omit raw contact values, but the changes and preview necessarily contain them.

This is an educational prototype, not a production CRM adapter. Email case folding is a documented business policy, not a claim about every mail server. Email validation is intentionally not full RFC validation. Plus-addresses and dots are not rewritten. Conflicts require a human decision; no “last writer wins.” Inputs are loaded in memory, and there is no connector, network retry layer, deletion support, field-level consent model, or transactional CRM write path.

CSV output preserves original field content and may contain spreadsheet formulas if inputs are untrusted. Prefer target-preview.json in a plain-text editor or JSON viewer: formula-like strings remain literal data without silently changing CSV values. This is not sanitization for subsequent import. Never open untrusted raw CSV in an auto-evaluating spreadsheet. A production adapter should add authentication, stable CRM IDs, optimistic concurrency, field mapping, redaction/retention controls, streaming for large files, and rate-limit handling.


## Optional local AI review (prototype; live inference unverified)

See [local AI review](docs/local-ai-review.md) for a count-only triage adapter and a no-model facts preview. It requires no API keys and never downloads a model or applies AI suggestions. Live generation is not yet verified: the development Ollama service has no installed model. The deterministic audit remains independent of AI. The complete local suite now has 53 passing tests, including eighteen offline adapter and transport tests; stub responses are not evidence of live model quality.
