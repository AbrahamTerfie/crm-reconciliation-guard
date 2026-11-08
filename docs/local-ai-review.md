# Local AI review: optional prototype

## Buyer problem

An operator receives a reconciliation report but still has to translate technical issue counts into a short review checklist. This optional module asks an already-installed local Ollama model to draft that explanation. It never edits the reconciliation plan, selects a winning contact, merges records, writes to a CRM, or approves an import.

## Honest current status

The adapter and safeguards are implemented and covered by offline tests with a stubbed model response. On the development Mac, Ollama was installed and running but reported **no installed models**. Real model generation has therefore **not been tested**, and no generated note is presented as a live AI result. No model, service or credential was downloaded or purchased.

A truthful portfolio description is: “I built an optional local-model triage adapter that limits model input to aggregate audit counts and keeps AI suggestions separate from deterministic repair logic. Its input/output safety behavior is tested; live inference still requires validation with a local model.”

## Try the no-model path

First run the ordinary audit from the README, using synthetic fixtures and a fresh output directory. Then:

```sh
python3 -m crm_guard.ai_review --plan output/demo/plan.json --output output/demo/ai-facts.json --facts-only
```

This writes only the exact allowlisted aggregate input. It performs **no AI inference** and is labeled `facts_only_no_ai`. Do not call it an AI-generated explanation.

## Optional inference when a local model is available

```sh
python3 -m crm_guard.ai_review --plan output/demo/plan.json --output output/demo/ai-review.json --model YOUR_ALREADY_INSTALLED_LOCAL_MODEL
```

Use the exact installed name. The program never downloads models. It contacts only `127.0.0.1:11434`, disables HTTP proxy use and redirects, rejects obvious cloud-model names and reported remote-backed models, and checks that the selected model exists. The local Ollama service itself is a trust boundary: use a trusted configuration and verify the model actually runs locally. These checks are not a network sandbox for Ollama or proof about the server's implementation.

The only model input is numeric summary counts plus allowlisted issue-reason/side counts. Names, emails, IDs, custom headers, cell values, source paths and proposed changes are not sent. Even aggregate business counts can be sensitive; inspect the facts first and obtain the data owner's authorization before using real business data.

Responses must have a bounded summary and one to five review steps. They are written as JSON with `unverified_ai_draft` and an explicit human-review warning. Shape validation cannot prove factual correctness: a model can still invent causes or recommend bad actions. Compare it against the included facts before use. Do not render it as trusted HTML or execute any suggested command. No response is applied automatically.

## Limits and tests

Timeout: 60 seconds. Response size cap: 256 KiB. Plan file cap: 10 MiB. Existing output files are refused. Local model execution consumes machine resources even when no API fee applies. Ollama may retain operational logs; this tool does not manage their retention.

Eighteen offline tests cover count-only input, unknown-reason and inconsistent-count rejection, stubbed output validation, missing-model refusal, cloud/remote-backed refusal, explicit no-AI facts output, no overwrite, malformed catalog/details/generation responses, request timeout configuration, timeout propagation, bounded response reads, oversized/invalid JSON replies, disabled proxies and redirect refusal. Transport checks use mocked HTTP boundaries, not real inference. They do not establish model quality or performance. Next acceptance step: with an approved installed local model, compare its output on the synthetic fixture against the deterministic facts and record the actual latency and model identity.
