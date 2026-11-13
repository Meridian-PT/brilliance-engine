"""Idempotent importer for a Gusto "Employees" CSV export.

Replaces the Phase-1 PLACEHOLDER fields -- email, start_date, employee_number
-- with real values from Gusto, for already-seeded employees. Does NOT touch
title, department, team, or manager (those come from the org-chart /
PT_Org_Structure_OACS.csv sources -- see scripts/ingest_org_csv.py); Title
and Manager columns here are read only for logging/cross-check context, not
written to the DB.

Matching: primarily by name (first + last). If the employee already has a
real (post-Gusto) employee_number from a PRIOR run of this script, matches
by employee_number take priority over name -- this is what makes re-running
idempotent/safe even if a name is spelled slightly differently between runs.
A still-placeholder employee_number (format "PT-####", seeded by
app/pt_seed.py) is never used for matching -- only a number this importer
itself previously wrote counts.

Expected CSV columns (header row, case-sensitive):
    First Name, Last Name, Email, Hire Date, Employee Number, Title, Manager

    - First Name, Last Name: used to match an existing employee by name.
    - Email: replaces the placeholder derived email.
    - Hire Date: YYYY-MM-DD (also accepts M/D/YYYY, Gusto's common export
      format) -- replaces the placeholder start_date.
    - Employee Number: replaces the placeholder "PT-####" employee_number;
      also used for matching on subsequent runs (see above).
    - Title, Manager: read for the diff report only, never written here.

Usage:
    python3 scripts/import_gusto_export.py path/to/gusto_export.csv              # dry run
    python3 scripts/import_gusto_export.py path/to/gusto_export.csv --apply       # write + commit
"""
import os
import sys
import csv
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User, EmployeeProfile
from app.audit import log_change

REQUIRED_COLUMNS = ['First Name', 'Last Name', 'Email', 'Hire Date', 'Employee Number', 'Title', 'Manager']

PLACEHOLDER_EMPNO_PREFIX = 'PT-'  # app/pt_seed.py's placeholder scheme (PT-1001, PT-1002, ...)

DATE_FORMATS = ['%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y']


def norm(name):
    return " ".join(name.strip().lower().split())


def parse_date(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f'Unrecognized date format: {raw!r} (expected one of {DATE_FORMATS})')


def is_placeholder_empno(value):
    return bool(value) and value.startswith(PLACEHOLDER_EMPNO_PREFIX)


def load_csv_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                f'CSV is missing required column(s): {missing}. '
                f'Expected header: {REQUIRED_COLUMNS}. Found: {reader.fieldnames}'
            )
        return list(reader)


def run(csv_path, apply_changes=False):
    app = create_app('production' if os.environ.get('DATABASE_URL') else 'development')
    report = {'updated': [], 'unmatched': [], 'ambiguous_name': [], 'errors': []}

    with app.app_context():
        rows = load_csv_rows(csv_path)

        # Build lookup indexes once.
        by_name = {}
        for u in User.query.all():
            by_name.setdefault(norm(u.name), []).append(u)
        by_real_empno = {
            p.employee_number: p
            for p in EmployeeProfile.query.all()
            if p.employee_number and not is_placeholder_empno(p.employee_number)
        }

        for i, row in enumerate(rows, start=2):  # start=2: header is line 1
            first, last = row['First Name'].strip(), row['Last Name'].strip()
            full_name = f'{first} {last}'.strip()
            gusto_empno = row['Employee Number'].strip()

            user = None
            if gusto_empno and gusto_empno in by_real_empno:
                user = by_real_empno[gusto_empno].user
            else:
                candidates = by_name.get(norm(full_name), [])
                if len(candidates) == 1:
                    user = candidates[0]
                elif len(candidates) > 1:
                    report['ambiguous_name'].append({
                        'row': i, 'name': full_name,
                        'reason': f'{len(candidates)} existing users share this name -- use Employee Number to disambiguate.',
                    })
                    continue

            if user is None:
                report['unmatched'].append({'row': i, 'name': full_name, 'email': row['Email']})
                continue

            profile = EmployeeProfile.query.filter_by(user_id=user.id).first()
            if profile is None:
                report['errors'].append({'row': i, 'name': full_name, 'error': 'matched user has no EmployeeProfile'})
                continue

            try:
                new_hire_date = parse_date(row['Hire Date'])
            except ValueError as e:
                report['errors'].append({'row': i, 'name': full_name, 'error': str(e)})
                continue

            changes = {}
            new_email = row['Email'].strip().lower()
            if new_email and new_email != (user.email or '').lower():
                changes['email'] = (user.email, new_email)
            if new_hire_date and new_hire_date != profile.start_date:
                changes['start_date'] = (profile.start_date, new_hire_date)
            if gusto_empno and gusto_empno != profile.employee_number:
                changes['employee_number'] = (profile.employee_number, gusto_empno)

            if changes:
                report['updated'].append({
                    'row': i, 'name': user.name, 'user_id': user.id, 'changes': changes,
                    'csv_title': row['Title'], 'csv_manager': row['Manager'],
                })
                if apply_changes:
                    if 'email' in changes:
                        log_change(None, 'User', user.id, 'email', changes['email'][0], changes['email'][1])
                        user.email = new_email
                    if 'start_date' in changes:
                        log_change(None, 'EmployeeProfile', profile.id, 'start_date',
                                    changes['start_date'][0], changes['start_date'][1])
                        profile.start_date = new_hire_date
                    if 'employee_number' in changes:
                        log_change(None, 'EmployeeProfile', profile.id, 'employee_number',
                                    changes['employee_number'][0], changes['employee_number'][1])
                        profile.employee_number = gusto_empno

        if apply_changes:
            db.session.commit()
        else:
            db.session.rollback()

    return report


def _print_report(report, csv_path, apply_changes):
    print(f"\n{'APPLYING' if apply_changes else 'DRY RUN'} -- {csv_path}\n")
    print(f"=== UPDATED ({len(report['updated'])}) ===")
    for item in report['updated']:
        print(f"- row {item['row']}: {item['name']} (user_id={item['user_id']})")
        for field, (old, new) in item['changes'].items():
            print(f"    {field}: {old!r} -> {new!r}")
        print(f"    (context only, not written) title={item['csv_title']!r} manager={item['csv_manager']!r}")

    print(f"\n=== UNMATCHED ROWS ({len(report['unmatched'])}) ===")
    for item in report['unmatched']:
        print(f"- row {item['row']}: {item['name']} <{item['email']}> -- no existing employee found by name or employee number")

    print(f"\n=== AMBIGUOUS NAME MATCHES ({len(report['ambiguous_name'])}) ===")
    for item in report['ambiguous_name']:
        print(f"- row {item['row']}: {item['name']} -- {item['reason']}")

    print(f"\n=== ERRORS ({len(report['errors'])}) ===")
    for item in report['errors']:
        print(f"- row {item['row']}: {item['name']} -- {item['error']}")
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_path')
    parser.add_argument('--apply', action='store_true', help='Actually write + commit (default is dry-run)')
    args = parser.parse_args()

    result = run(args.csv_path, apply_changes=args.apply)
    _print_report(result, args.csv_path, args.apply)
