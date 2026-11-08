# Repair walkthrough

## Scenario

A fictional team exports leads from a form tool to a CRM every day. The feed may repeat contacts with different capitalization and contain empty fields. A previous “find by exact email, then overwrite” design would be unsafe.

This repository implements the replacement boundary rather than inventing an outage at a real company.

## Diagnose → repair → prove

1. **Duplicate identity:** ` AVERY@example.test ` already exists as `avery@example.test`. Normalize the matching key, producing one update instead of another contact. Regression: `test_normalization_does_not_create_duplicate`.
2. **Data loss:** Blair's incoming name is empty. Keep the stored name. Regression: `test_blank_fields_preserve_existing`.
3. **Conflicting source:** Two Casey records normalize to one key. Quarantine both instead of choosing whichever is last. Regression: `test_duplicates_quarantine_all_source_copies`.
4. **Conflicting destination:** Two Frankie records exist in the target. Report both and block the source update. Regression: `test_ambiguous_target_never_updated`.
5. **Invalid identity:** `not-an-email` cannot identify a contact reliably. Quarantine it. Regression: `test_invalid_email_quarantined`.
6. **Legitimate new contact:** Ellis produces one create proposal.
7. **Replay safety:** Rerunning against the preview produces no new changes. Regression: `test_repeat_run_is_idempotent`.
8. **Stale snapshot:** The in-memory preview function refuses a different target fingerprint. This is a demonstration of an optimistic concurrency check, not a live CRM guarantee. Regression: `test_stale_target_rejected`.

## Two-minute demo

- Explain the naive import's three risks: identity mismatch, destructive blanks, and ambiguous duplicates.
- Run the 18 tests.
- Run the sample command from the README. Explain why exit 2 is an expected review signal, not a crash.
- Open `plan.json`: one create, one update, and six issue records.
- Open the preview and show Blair's name was retained.
- Run against the preview and show zero creates and zero updates.
- Close with the production limitations rather than suggesting this has already operated on a client's data.

## Integration outline

A Zapier, Make, n8n, or scheduled Python workflow could call a packaged version of this boundary after receiving a CSV. Branch on exit 2 to a review queue and exit 1 to an operational alert. Do not automatically import the full preview. A production CRM adapter would translate reviewed changes to provider-specific operations and use stable IDs plus version checks. It must also decide what to do with extra CSV fields, permission boundaries, deletion requests and data retention.

The project is deliberately read-only with respect to external systems. Adding live writes is a separate engineering and authorization step.
