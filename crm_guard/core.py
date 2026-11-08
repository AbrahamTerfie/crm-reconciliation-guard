"""Deterministic CSV reconciliation. No API calls or CRM writes."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

FIELDS = ('email', 'name', 'company')
EMAIL = re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]+\Z')


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise ValueError('Duplicate CSV headers are not allowed')
        if not set(FIELDS).issubset(headers):
            raise ValueError('CSV must include email, name, company headers')
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'Malformed CSV record at line {reader.line_num}')
            rows.append({field: row[field].strip() for field in FIELDS})
        return rows


def key(row):
    # Explicit business policy: matching is case-insensitive. No Gmail-specific
    # dot/plus rewriting, which could merge distinct customers.
    return row['email'].strip().lower()


def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


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
        'schema_version': 1,
        'target_fingerprint': fingerprint(target),
        'summary': {'source_rows': len(source), 'target_rows': len(target),
                    'creates': sum(c['action'] == 'create' for c in changes),
                    'updates': sum(c['action'] == 'update' for c in changes),
                    'unchanged': unchanged, 'issues': len(issues)},
        'issues': issues, 'changes': changes,
    }


def preview_target(target, plan):
    """Apply an in-memory plan to a copy, guarding against stale snapshots."""
    if fingerprint(target) != plan['target_fingerprint']:
        raise ValueError('Target changed since planning; regenerate the plan')
    result = [dict(row) for row in target]
    positions = {key(row): i for i, row in enumerate(result)}
    for change in plan['changes']:
        row = {field: change[field] for field in FIELDS}
        if change['action'] == 'create':
            positions[key(row)] = len(result)
            result.append(row)
        else:
            result[positions[key(row)]] = row
    return result


def write_csv(path, rows):
    """Write machine CSV. Do not open untrusted values in a spreadsheet."""
    with Path(path).open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
