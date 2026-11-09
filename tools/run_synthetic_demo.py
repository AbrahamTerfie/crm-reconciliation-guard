"""Reproducible offline smoke deployment using bundled synthetic fixtures only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BASELINE = dict(source_rows=7, target_rows=4, creates=1, updates=1, unchanged=1, issues=6)
RERUN = dict(source_rows=7, target_rows=5, creates=0, updates=0, unchanged=3, issues=6)


def run_step(args, expected=0):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=120)
    if result.returncode != expected:
        raise RuntimeError(f'{args[0]} exited {result.returncode}; expected {expected}.\n'
                           f'{result.stdout}\n{result.stderr}')
    return result.stdout + result.stderr


def verify_reports(baseline, rerun, facts):
    if baseline.get('summary') != BASELINE or rerun.get('summary') != RERUN:
        raise ValueError('Synthetic baseline/rerun counts differ from the acceptance contract')
    if baseline.get('issues') != rerun.get('issues'):
        raise ValueError('Rerun unexpectedly changed unresolved issues')
    if facts.get('status') != 'facts_only_no_ai' or facts.get('facts', {}).get('summary') != BASELINE:
        raise ValueError('Expected a matching facts-only report, not model inference')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New local output directory; existing paths refused')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        parser.error('Python 3.10 or later is required')
    # Refuse symlinks too, including a dangling symlink at the requested location.
    output = args.output.absolute()
    if output.exists() or output.is_symlink():
        print('Refusing existing output path.', file=sys.stderr)
        return 1
    start = time.monotonic()
    old_umask = os.umask(0o077)
    try:
        fixtures = [ROOT / 'examples/incoming.csv', ROOT / 'examples/crm.csv']
        before = {p.name: digest(p) for p in fixtures}
        sources = sorted([*ROOT.glob('crm_guard/*.py'), *ROOT.glob('tests/*.py'), *ROOT.glob('tools/*.py')])
        source_before = {str(p.relative_to(ROOT)): digest(p) for p in sources}
        test_log = run_step(['-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        # Parent must exist; do not create an arbitrary directory tree.
        output.mkdir(mode=0o700)
        (output / 'tests.log').write_text(test_log, encoding='utf-8')
        source, target = fixtures
        base, repeat = output / 'baseline', output / 'rerun'
        run_step(['-m', 'crm_guard', '--source', str(source), '--target', str(target), '--output', str(base)], expected=2)
        run_step(['-m', 'crm_guard', '--source', str(source), '--target', str(base / 'target-preview.csv'), '--output', str(repeat)], expected=2)
        facts_path = output / 'ai-facts.json'
        run_step(['-m', 'crm_guard.ai_review', '--plan', str(base / 'plan.json'), '--output', str(facts_path), '--facts-only'])
        baseline = json.loads((base / 'plan.json').read_text())
        rerun = json.loads((repeat / 'plan.json').read_text())
        verify_reports(baseline, rerun, json.loads(facts_path.read_text()))
        if before != {p.name: digest(p) for p in fixtures}:
            raise ValueError('Input fixtures changed during execution')
        # Record code hashes without relying on Git or including user identity.
        sources_after = sorted([*ROOT.glob('crm_guard/*.py'), *ROOT.glob('tests/*.py'), *ROOT.glob('tools/*.py')])
        if source_before != {str(p.relative_to(ROOT)): digest(p) for p in sources_after}:
            raise ValueError('Python source changed during execution')
        report = {'status': 'passed', 'data': 'bundled_fixtures_expected_synthetic', 'ai_inference': False,
                  'python': platform.python_version(), 'system': platform.system(), 'machine': platform.machine(),
                  'duration_seconds': round(time.monotonic() - start, 3),
                  'baseline': BASELINE, 'rerun': RERUN, 'fixture_sha256': before,
                  'source_sha256': source_before, 'source_unchanged_during_run': True}
        (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(f'Synthetic verification passed. Reports: {output}')
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'Verification failed: {error}', file=sys.stderr)
        print('Partial outputs may remain; no completion manifest is promised.', file=sys.stderr)
        return 1
    finally:
        os.umask(old_umask)


if __name__ == '__main__':
    raise SystemExit(main())
