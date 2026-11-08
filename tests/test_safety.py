"""Synthetic regression coverage for schema preservation and safe review."""
import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from crm_guard.core import CSVRows, read_csv, reconcile, preview_target, write_csv
from crm_guard.__main__ import main


def row(**kw):
    return dict(dict(email='a@example.test', name='A', company='Demo'), **kw)


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def load(self, text, name='input.csv'):
        path = self.root / name
        path.write_text(text)
        return read_csv(path)

    def test_preserve_extra_values_order(self):
        t = self.load('id,email,name,company,notes\n007,a@example.test,A,Old,"  Keep, exactly  "\n')
        s = [row(company='New', id='bad', notes='bad')]
        p = reconcile(s, t)
        result = preview_target(t, p)
        self.assertEqual(result[0]['id'], '007')
        self.assertEqual(result[0]['notes'], '  Keep, exactly  ')
        self.assertEqual(result.fieldnames, ('id','email','name','company','notes'))
        self.assertEqual(p['field_policy']['ignored_source_fields'], ['id','notes'])
        self.assertEqual(t[0]['company'], 'Old')

    def test_create_blank_extras(self):
        t = self.load('email,name,company,id,consent\n')
        result = preview_target(t, reconcile([row(id='bad', consent='yes', extra='ignored')], t))
        self.assertEqual(result[0], row(id='', consent=''))

    def test_empty_headers_preserved(self):
        t = self.load('id,email,name,company\n')
        out = self.root / 'out.csv'
        write_csv(out, preview_target(t, reconcile([], t)))
        self.assertEqual(out.read_text(), 'id,email,name,company\n')

    def test_extra_value_stale(self):
        t = [row(id='1')]; p = reconcile([], t)
        with self.assertRaises(ValueError): preview_target([row(id='2')], p)

    def test_empty_schema_stale(self):
        t = CSVRows(fieldnames=('email','name','company','id'))
        p = reconcile([], t)
        with self.assertRaises(ValueError): preview_target(CSVRows(), p)

    def test_ambiguous_and_untouched_extras(self):
        t = [row(id='1'), row(id='2'), row(email='b@example.test', id='3')]
        self.assertEqual(preview_target(t, reconcile([row(company='New')], t)), t)

    def test_blank_header(self):
        with self.assertRaises(ValueError): self.load('email,name,company,\na@example.test,A,Demo,x\n')

    def test_plain_list_extra_roundtrip(self):
        t = [row(id='001')]; result = preview_target(t, reconcile([row(company='New')], t))
        out = self.root / 'out.csv'; write_csv(out, result)
        self.assertEqual(read_csv(out)[0]['id'], '001')

    def test_cli_extra_rerun(self):
        src = self.root / 'source.csv'; target = self.root / 'target.csv'
        src.write_text('email,name,company,id\na@example.test,,New,bad\nb@example.test,B,Demo,bad2\n')
        target.write_text('id,email,name,company\n001,a@example.test,A,Old\n')
        before = target.read_bytes(); out = self.root / 'out'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--source',str(src),'--target',str(target),'--output',str(out)]),0)
        result = read_csv(out / 'target-preview.csv')
        self.assertEqual([r['id'] for r in result], ['001',''])
        self.assertEqual(reconcile(read_csv(src), result)['changes'], [])
        self.assertEqual(target.read_bytes(), before)

    def test_unterminated_quote(self):
        with self.assertRaises(csv.Error): self.load('email,name,company\na@example.test,"unfinished,Demo\n')

    def test_trailing_quote_garbage(self):
        with self.assertRaises(csv.Error): self.load('email,name,company\na@example.test,"Name"garbage,Demo\n')

    def test_valid_multiline(self):
        t = self.load('email,name,company,notes\na@example.test,A,Demo,"one\nline ""two"""\n')
        self.assertEqual(t[0]['notes'], 'one\nline "two"')

    def test_malformed_cli_no_output(self):
        src=self.root/'source.csv';src.write_text('email,name,company\na@example.test,"bad,Demo\n')
        out=self.root/'out'
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--source',str(src),'--target',str(src),'--output',str(out)]),1)
        self.assertFalse(out.exists())

    def test_json_formula_review(self):
        vals=['=1+1','+SUM(1)','-2+3','@SUM(1)','\t=1+1','<script>alert(1)</script>']
        t=self.root/'target.csv';write_csv(t,[row(email=f'p{i}@example.test',notes=v) for i,v in enumerate(vals)])
        out=self.root/'out'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--source',str(t),'--target',str(t),'--output',str(out)]),0)
        self.assertEqual([r['notes'] for r in json.loads((out/'target-preview.json').read_text())['rows']], vals)
        self.assertEqual([r['notes'] for r in read_csv(out/'target-preview.csv')],vals)

    def test_schema_rejected(self):
        for v in [None,1,3,'2',2.0]:
            p=reconcile([row()],[]);p['schema_version']=v
            with self.assertRaises(ValueError):preview_target([],p)

    def test_bad_changes_rejected(self):
        for change in [None,{'action':'create'},row(action='delete'),row(action='create',name=123)]:
            p=reconcile([],[]);p['changes']=[change]
            with self.assertRaises(ValueError):preview_target([],p)

    def test_duplicate_and_wrong_action_rejected(self):
        p=reconcile([row()],[]);p['changes'].append(dict(p['changes'][0]))
        with self.assertRaises(ValueError):preview_target([],p)
        p=reconcile([row()],[]);p['changes'][0]['action']='update'
        with self.assertRaises(ValueError):preview_target([],p)
