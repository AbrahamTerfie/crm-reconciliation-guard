"""Optional local-model review; no model downloads, cloud endpoints or CRM writes."""
import argparse
from collections import Counter
import json
from pathlib import Path
import urllib.request

REASONS = {'invalid_email', 'duplicate_email', 'duplicate_source_email', 'ambiguous_target_email'}
SUMMARY = ('source_rows', 'target_rows', 'creates', 'updates', 'unchanged', 'issues')
BASE = 'http://127.0.0.1:11434'
LIMIT = 256 * 1024


def review_facts(plan):
    """Allowlist counts only. Never pass raw fields, headers, IDs or changes."""
    if not isinstance(plan, dict) or type(plan.get('schema_version')) is not int or plan['schema_version'] != 2:
        raise ValueError('Expected a version 2 reconciliation plan')
    summary = plan.get('summary', {})
    if not isinstance(summary, dict) or any(type(summary.get(k)) is not int or not 0 <= summary[k] <= 10**9 for k in SUMMARY):
        raise ValueError('Invalid summary counts')
    issues = plan.get('issues')
    if not isinstance(issues, list) or len(issues) != summary['issues']:
        raise ValueError('Issue count does not match evidence')
    counts = Counter()
    for issue in issues:
        if not isinstance(issue, dict) or issue.get('reason') not in REASONS or issue.get('side') not in ('source', 'target'):
            raise ValueError('Unsupported issue evidence')
        counts[(issue['side'], issue['reason'])] += 1
    return {'summary': {k: summary[k] for k in SUMMARY},
            'issue_counts': [{'side': side, 'reason': reason, 'count': count}
                             for (side, reason), count in sorted(counts.items())]}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class LocalOllama:
    def __init__(self):
        # Do not let environment proxy settings redirect localhost traffic.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(BASE + path, data=data, headers={'Content-Type': 'application/json'})
        with self.opener.open(request, timeout=60) as response:
            body = response.read(LIMIT + 1)
        if len(body) > LIMIT:
            raise ValueError('Local model response exceeds size limit')
        return json.loads(body)


def validate_note(note):
    if not isinstance(note, dict) or set(note) != {'summary', 'review_steps'}:
        raise ValueError('Model returned an invalid review structure')
    def text(value):
        return isinstance(value, str) and 0 < len(value) <= 2000 and not any(ord(c) < 32 and c not in '\n\t' for c in value)
    if not text(note['summary']) or not isinstance(note['review_steps'], list) or not 1 <= len(note['review_steps']) <= 5 or not all(text(s) for s in note['review_steps']):
        raise ValueError('Model returned invalid review text')
    return note


def generate_review(plan, model, client=None):
    facts = review_facts(plan)
    client = client or LocalOllama()
    if not isinstance(model, str) or not model or len(model) > 200 or 'cloud' in model.lower():
        raise ValueError('Choose an installed local model, not a cloud model')
    tags = client.request('/api/tags')
    if not isinstance(tags, dict) or not isinstance(tags.get('models'), list):
        raise ValueError('Invalid local model catalog response')
    installed = tags['models']
    if any(not isinstance(m, dict) or not isinstance(m.get('name'), str) or not m['name']
           for m in installed):
        raise ValueError('Invalid local model catalog entry')
    if not any(m.get('name') == model for m in installed):
        raise ValueError('Model is not installed locally; no model was downloaded')
    details = client.request('/api/show', {'model': model})
    if not isinstance(details, dict):
        raise ValueError('Invalid local model details response')
    if details.get('remote_host') or details.get('remote_model'):
        raise ValueError('Remote-backed models are not allowed')
    response = client.request('/api/generate', {
        'model': model, 'stream': False, 'format': 'json', 'keep_alive': 0,
        'options': {'temperature': 0, 'num_predict': 500},
        'system': ('You explain a synthetic CRM reconciliation audit to an operator. '
                   'Use only supplied counts. Do not infer identities, revenue, deployments or successful repairs. '
                   'Do not recommend automatic merges, deletions or importing the full preview. '
                   'Provide a short plain-language summary and 1-5 human review steps. '
                   'Return only JSON with summary (string) and review_steps (array of strings). '
                   'Unresolved issues remain unresolved; no CRM was modified.'),
        'prompt': json.dumps(facts, sort_keys=True),
    })
    if not isinstance(response, dict):
        raise ValueError('Invalid local generation response')
    if response.get('done') is not True:
        raise ValueError('Model generation did not finish')
    if not isinstance(response.get('response'), str):
        raise ValueError('Invalid local generation text')
    note = validate_note(json.loads(response['response']))
    return {'status': 'unverified_ai_draft', 'model': model, 'facts': facts,
            'warning': 'Human review required. AI may be wrong. No CRM was modified.', 'draft': note}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Create an optional local AI review from aggregate counts only.')
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New JSON file; never overwrite')
    parser.add_argument('--model', help='Exact installed Ollama model name; no downloads')
    parser.add_argument('--facts-only', action='store_true', help='Inspect aggregate model input without inference')
    args = parser.parse_args(argv)
    if not args.facts_only and not args.model:
        parser.error('--model is required unless --facts-only is selected')
    try:
        if args.output.exists():
            raise ValueError('Output already exists')
        if args.plan.stat().st_size > 10 * 1024 * 1024:
            raise ValueError('Plan exceeds 10 MiB limit')
        plan = json.loads(args.plan.read_text(encoding='utf-8'))
        result = {'status': 'facts_only_no_ai', 'facts': review_facts(plan)} if args.facts_only else generate_review(plan, args.model)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2, ensure_ascii=True)
            stream.write('\n')
    except (OSError, ValueError, TypeError) as error:
        print(f'Review not generated: {error}')
        return 1
    print('Review saved locally. No CRM was modified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
