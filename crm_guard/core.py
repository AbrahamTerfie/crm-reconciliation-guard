"""Deterministic CSV reconciliation. No API calls or CRM writes."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

FIELDS = ('email', 'name', 'company')
EMAIL = re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]+\Z')


class CSVRows(list):
    """Rows and ordered headers, including header-only exports."""
    def __init__(self, rows=(), *, fieldnames=FIELDS):
        super().__init__(rows)
        self.fieldnames = tuple(fieldnames)


def columns(rows):
    if isinstance(rows, CSVRows):
        return rows.fieldnames
    return tuple(dict.fromkeys([*FIELDS, *(field for row in rows for field in row)]))


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        headers = reader.fieldnames or []
        if any(not h or not h.strip() for h in headers):
            raise ValueError('Blank CSV headers are not allowed')
        if len(headers) != len(set(headers)):
            raise ValueError('Duplicate CSV headers are not allowed')
        if not set(FIELDS).issubset(headers):
            raise ValueError('CSV must include email, name, company headers')
        rows = CSVRows(fieldnames=headers)
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'Malformed CSV record at line {reader.line_num}')
            rows.append({field: (value.strip() if field in FIELDS else value)
                         for field, value in row.items()})
        return rows


def key(row):
    # Explicit business policy: matching is case-insensitive. No Gmail-specific
    # dot/plus rewriting, which could merge distinct customers.
    return row['email'].strip().lower()


def fingerprint(rows):
    return hashlib.sha256(json.dumps({'fields': columns(rows), 'rows': rows}, sort_keys=True).encode()).hexdigest()


def reconcile(source, target):
    source_counts = Counter(key(row) for row in source)
    target_counts = Counter(key(row) for row in target)
    target_by_email = {key(row): row for row in target}
    issues, changes, unchanged = [], [], 0
    for number, row in enumerate(target, 2):
        email = key(row)
        if not EMAIL.fullmatch(email):
            issues.append({'side': 'target', 'row': number, 'reason': 'invalid_email'})
        elif target_counts[email] > 1:
            issues.append({'side': 'target', 'row': number, 'reason': 'duplicate_email'})
    for number, row in enumerate(source, 2):
        email = key(row)
        reason = None
        if not EMAIL.fullmatch(email):
            reason = 'invalid_email'
        elif source_counts[email] > 1:
            reason = 'duplicate_source_email'
        elif target_counts[email] > 1:
            reason = 'ambiguous_target_email'
        if reason:
            issues.append({'side': 'source', 'row': number, 'reason': reason})
            continue
        existing = target_by_email.get(email)
        # Empty upstream fields never erase existing values.
        desired = {'email': email, **{
            field: row[field].strip() or (existing[field] if existing else '')
            for field in ('name', 'company')
        }}
        if existing is None:
            changes.append({'action': 'create', **desired})
        elif any(desired[field] != existing[field] for field in ('name', 'company')):
            changes.append({'action': 'update', **desired})
        else:
            unchanged += 1
    return {
        'schema_version': 2,
        'field_policy': {
            'mapped_fields': list(FIELDS),
            'target_columns': list(columns(target)),
            'preserved_target_fields': [f for f in columns(target) if f not in FIELDS],
            'ignored_source_fields': [f for f in columns(source) if f not in FIELDS],
            'new_record_unmapped_values': 'blank',
        },
        'target_fingerprint': fingerprint(target),
        'summary': {'source_rows': len(source), 'target_rows': len(target),
                    'creates': sum(c['action'] == 'create' for c in changes),
                    'updates': sum(c['action'] == 'update' for c in changes),
                    'unchanged': unchanged, 'issues': len(issues)},
        'issues': issues, 'changes': changes,
    }


def preview_target(target, plan):
    """Apply an in-memory plan to a copy, guarding against stale snapshots."""
    if (not isinstance(plan, dict) or type(plan.get('schema_version')) is not int
            or plan.get('schema_version') != 2):
        raise ValueError('Unsupported plan schema_version; regenerate the plan')
    if fingerprint(target) != plan.get('target_fingerprint'):
        raise ValueError('Target changed since planning; regenerate the plan')
    changes = plan.get('changes')
    if not isinstance(changes, list):
        raise ValueError('Plan changes must be a list')
    seen = set()
    counts = Counter(key(row) for row in target)
    for change in changes:
        if (not isinstance(change, dict) or change.get('action') not in ('create', 'update')
                or any(not isinstance(change.get(f), str) for f in FIELDS)):
            raise ValueError('Invalid plan change')
        email = key(change)
        if not EMAIL.fullmatch(email) or email in seen:
            raise ValueError('Invalid or duplicate identity in plan changes')
        seen.add(email)
        if counts[email] != (0 if change['action'] == 'create' else 1):
            raise ValueError('Plan action conflicts with target identity count')
    result = CSVRows((dict(row) for row in target), fieldnames=columns(target))
    positions = {key(row): i for i, row in enumerate(result)}
    for change in plan['changes']:
        row = {field: change[field] for field in FIELDS}
        if change['action'] == 'create':
            positions[key(row)] = len(result)
            result.append({field: row.get(field, '') for field in result.fieldnames})
        else:
            result[positions[key(row)]].update(row)
    return result


def write_csv(path, rows):
    """Write machine CSV. Do not open untrusted values in a spreadsheet."""
    with Path(path).open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns(rows))
        writer.writeheader()
        writer.writerows(rows)
