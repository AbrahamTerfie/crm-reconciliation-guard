# Reproducible offline run on ARM64

## Scope

This is a one-shot CLI verification workload, not a hosted web service. It needs Python 3.10+ and a local copy of this repository, including `tools`, `tests`, and the synthetic `examples`. There are no third-party runtime dependencies or architecture-specific binaries. Run directly from source; `pip install`, Docker, an API key, a database server and root privileges are unnecessary.

The same source-run approach is intended for a future Linux ARM64 VM, for example an Ubuntu ARM64 image on an Oracle Ampere VM if available and eligible under the account's actual terms. No Oracle account, VM, availability, quota, price, Always Free entitlement or deployment has been verified by this project. Provisioning and any cost-bearing action are separate decisions. Nothing here creates cloud resources, opens ports, enables services or uploads data.

## Local command

From the repository root, choose a fresh output directory whose parent exists:

```sh
python3 --version
mkdir -p output
PYTHONDONTWRITEBYTECODE=1 python3 tools/run_synthetic_demo.py --output output/arm64-check-001
```

Use a different directory for each run. An existing path is refused without running tests or overwriting reports. Do not run as root. The runner sets an owner-only file creation mask while executing and restores the caller's mask afterward. Existing parent directory permissions are not modified.

The runner:

1. Runs the complete offline unittest suite, without external services or model calls.
2. Audits bundled synthetic incoming.csv against crm.csv. Exit 2 is expected: one create, one update, one unchanged, six issue records.
3. Audits against the candidate preview. Exit 2 remains expected: no creates or updates, three unchanged, the same unresolved issues.
4. Generates the aggregate-only AI facts file, explicitly labeled **no AI inference**.
5. Confirms the input and Python source hashes are unchanged and writes a verification manifest with runtime, architecture, code/input hashes and counts.

On success the runner exits 0. Any failed subprocess, changed counts, changed input, malformed report or timeout returns 1. Each subprocess has a 120-second timeout. A failure after tests may leave partial outputs; only a final `verification.json` with status `passed` indicates completion. Keep the full directory for inspection, or deliberately choose another fresh location after fixing the cause.

## Output

- `tests.log`: test names and outcomes.
- `baseline/` and `rerun/`: plan, machine CSV and text-review JSON.
- `ai-facts.json`: allowlisted aggregate counts; no model output.
- `verification.json`: pass status, Python/OS/architecture, elapsed duration and source/input SHA-256 values.

Read JSON in a text editor or JSON viewer. The raw CSV formula caveat from the README still applies. These are synthetic fixtures, not measured client results or proof of live CRM behavior.

## Future VM checklist (not executed)

- Confirm the actual VM offer, ARM64 shape, region capacity, quota and billing terms before provisioning. Do not assume a resource is free from its name.
- Select a supported ARM64 Linux image with Python 3.10+ already available, or obtain approval for installing prerequisites. Ubuntu 24.04 is a candidate, not a tested deployment claim.
- Use an unprivileged account and a private directory. Transfer a reviewed, fixed source revision through an authorized channel, with no customer exports, output directories, caches or credentials. Preserve the complete source tree, including `tools` and `tests`.
- Verify Python version, CPU architecture and source hashes. Run the command above locally on the VM. Inspect `verification.json` and test logs; do not equate a Mac pass with Linux validation.
- No incoming application ports, public web endpoint, reverse proxy, cron job or systemd service is required. This does not change existing SSH/network settings.
- Keep AI inference disabled for this smoke run. Installing/downloading a model or exposing Ollama is out of scope; AI inference remains unverified.
- Stop after the one-shot validation. Scheduling, hosting, live data, monitoring and production integrations require separate design and authorization.

## Verification record

The implementation was exercised on macOS ARM64 with Python 3.14 using the full local suite. Linux ARM64/Oracle execution has not yet been performed. The runner records each actual environment in its manifest instead of claiming cross-platform validation in advance.


### Fixture provenance and hash limits

The bundled example CSVs were reviewed as synthetic at repository revision `c8542c9c84cac0abe1d322a71ea29b689ccffe38`; this preparation does not modify them. Use that reviewed fixture content or review the exact fixture revision you intend to run. A filename, `.test` email address, matching expected counts or SHA-256 digest does not independently prove that data is synthetic or non-sensitive. Hashes here detect changes during a run and identify bytes for comparison; they do not authenticate provenance. Never replace the fixtures with customer data for this smoke demonstration.

The runner records and compares Python source hashes before and after execution. This detects ordinary edits during verification, not malicious transient changes or a hostile host. A fixed, reviewed source revision and trusted runtime are still required.
