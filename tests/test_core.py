import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from crm_guard.core import read_csv, reconcile, preview_target, write_csv
from crm_guard.__main__ import main


def row(email='a@example.test', name='A', company='Demo'):
    return dict(email=email, name=name, company=company)


class ReconciliationTests(unittest.TestCase):
    def test_normalization_does_not_create_duplicate(self):
        plan = reconcile([row(' A@EXAMPLE.TEST ', company='New')], [row()])
        self.assertEqual(plan['summary']['creates'], 0)
        self.assertEqual(plan['summary']['updates'], 1)

    def test_blank_fields_preserve_existing(self):
        plan = reconcile([row(name='', company='')], [row()])
        self.assertEqual(plan['changes'], [])

    def test_duplicates_quarantine_all_source_copies(self):
        plan = reconcile([row(), row('A@example.test')], [])
        self.assertEqual(plan['changes'], [])
        self.assertEqual(len(plan['issues']), 2)

    def test_ambiguous_target_never_updated(self):
        plan = reconcile([row(company='New')], [row(), row('A@example.test')])
        self.assertEqual(plan['changes'], [])
        self.assertEqual(plan['issues'][-1]['reason'], 'ambiguous_target_email')

    def test_invalid_email_quarantined(self):
        for email in ('', 'abc', 'a@@b.test', 'a b@example.test'):
            with self.subTest(email=email):
                self.assertFalse(reconcile([row(email)], [])['changes'])

    def test_plus_alias_not_merged(self):
        plan = reconcile([row('a+sales@example.test')], [row()])
        self.assertEqual(plan['summary']['creates'], 1)

    def test_repeat_run_is_idempotent(self):
        source = [row(company='New'), row('b@example.test')]
        target = [row()]
        plan = reconcile(source, target)
        preview = preview_target(target, plan)
        self.assertEqual(reconcile(source, preview)['changes'], [])
        self.assertEqual(target, [row()])

    def test_stale_target_rejected(self):
        plan = reconcile([row()], [])
        with self.assertRaisesRegex(ValueError, 'Target changed'):
            preview_target([row()], plan)

    def test_plan_is_deterministic(self):
        self.assertEqual(reconcile([row()], []), reconcile([row()], []))

    def test_target_only_contact_not_deleted(self):
        plan = reconcile([], [row()])
        self.assertEqual(preview_target([row()], plan), [row()])

    def test_invalid_target_reported(self):
        self.assertEqual(reconcile([], [row('invalid')])['issues'][0]['side'], 'target')


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def csv(self, text):
        path = self.root / 'input.csv'
        path.write_text(text, encoding='utf-8')
        return path

    def test_bom_and_quoted_comma(self):
        rows = read_csv(self.csv('\ufeffemail,name,company\na@example.test,"A, B",Demo\n'))
        self.assertEqual(rows[0]['name'], 'A, B')

    def test_missing_header(self):
        with self.assertRaises(ValueError):
            read_csv(self.csv('email,name\na@example.test,A\n'))

    def test_duplicate_header(self):
        with self.assertRaises(ValueError):
            read_csv(self.csv('email,name,company,name\na@example.test,A,Demo,B\n'))

    def test_malformed_record(self):
        for line in ('a@example.test,A', 'a@example.test,A,Demo,extra'):
            with self.subTest(line=line), self.assertRaises(ValueError):
                read_csv(self.csv('email,name,company\n' + line + '\n'))

    def test_write_refuses_overwrite(self):
        path = self.root / 'result.csv'
        write_csv(path, [row()])
        with self.assertRaises(FileExistsError):
            write_csv(path, [])

    def test_cli_end_to_end_and_exit_code(self):
        source = self.csv('email,name,company\na@example.test,A,Demo\ninvalid,X,Demo\n')
        target = self.root / 'crm.csv'
        target.write_text('email,name,company\n', encoding='utf-8')
        output = self.root / 'out'
        args = ['--source', str(source), '--target', str(target), '--output', str(output)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 2)
        plan = json.loads((output / 'plan.json').read_text())
        self.assertEqual(plan['summary']['creates'], 1)
        self.assertEqual(len(read_csv(output / 'target-preview.csv')), 1)
        self.assertEqual(read_csv(target), [])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 1)

    def test_cli_clean_exit(self):
        source = self.csv('email,name,company\na@example.test,A,Demo\n')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--source', str(source), '--target', str(source),
                                   '--output', str(self.root / 'out')]), 0)


if __name__ == '__main__':
    unittest.main()
