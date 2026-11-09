import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tools.run_synthetic_demo import BASELINE, RERUN, main, run_step, verify_reports


class LocalRunTests(unittest.TestCase):
    def test_expected_review_exit_is_success(self):
        with patch('tools.run_synthetic_demo.subprocess.run', return_value=subprocess.CompletedProcess([], 2, 'review', '')) as run:
            self.assertEqual(run_step(['-m', 'crm_guard'], expected=2), 'review')
        self.assertEqual(run.call_args.kwargs['timeout'], 120)
        self.assertEqual(run.call_args.kwargs['env']['PYTHONDONTWRITEBYTECODE'], '1')

    def test_unexpected_exit_fails(self):
        with patch('tools.run_synthetic_demo.subprocess.run', return_value=subprocess.CompletedProcess([], 1, '', 'failure')):
            with self.assertRaises(RuntimeError): run_step(['-m', 'crm_guard'], expected=2)

    def test_existing_directory_refused_before_tests(self):
        with tempfile.TemporaryDirectory() as tmp, patch('tools.run_synthetic_demo.run_step') as run:
            sentinel = Path(tmp) / 'keep'; sentinel.write_text('unchanged')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--output', tmp]), 1)
            run.assert_not_called()
            self.assertEqual(sentinel.read_text(), 'unchanged')

    def test_verify_contract_and_no_ai_claim(self):
        a = {'summary': BASELINE, 'issues': []}
        b = {'summary': RERUN, 'issues': []}
        facts = {'status': 'facts_only_no_ai', 'facts': {'summary': BASELINE}}
        verify_reports(a, b, facts)
        with self.assertRaises(ValueError): verify_reports(a, b, dict(facts, status='unverified_ai_draft'))
        with self.assertRaises(ValueError): verify_reports(a, dict(b, summary={}), facts)
        with self.assertRaises(ValueError): verify_reports(a, dict(b, issues=['changed']), facts)

    def test_failed_tests_do_not_create_output(self):
        with tempfile.TemporaryDirectory() as tmp, patch('tools.run_synthetic_demo.run_step', side_effect=RuntimeError('tests failed')):
            output = Path(tmp) / 'new'
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--output', str(output)]), 1)
            self.assertFalse(output.exists())
