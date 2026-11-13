"""One-off ingest of the authoritative PT org roster CSV
(portal_uploads/to-portal/PT_Org_Structure_OACS.csv) into Brilliance Engine.

Updates, for each matched employee: email (replaces the Phase-1 derived
guess with the real address), department, team, and manager_id. Creates
EmployeeProfile.title is NEVER touched here -- title comes from the
org-chart.md source (job titles), not this CSV (which only has a Role
Level like "C-Suite"/"Director", not a job title). User.name is NEVER
changed by this script, even when the CSV spells a name differently
(e.g. "Shahbaz Ali" vs seeded "Shabaz Ali") -- see NAME_OVERRIDES below,
which exists purely to let the matcher find the right existing row.

Idempotent: safe to re-run. Diffs are computed field-by-field; a field
is only written (and only logged) if its new value differs from the
current value. Every write is mirrored into AuditLog (actor=None,
i.e. "system import") in the same transaction.

Usage:
    python3 scripts/ingest_org_csv.py                 # dry run (default)
    python3 scripts/ingest_org_csv.py --apply          # actually writes + commits

Run from the brilliance-engine repo root with DATABASE_URL pointed at the
target DB (the live paid Postgres requires the ipAllowList to be
temporarily opened -- see memory note on this).
"""
import os
import sys
import csv
import json
import secrets
import argparse
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import User, EmployeeProfile
from app.audit import log_change

CSV_PATH = os.environ.get(
    'ORG_CSV_PATH',
    '/home/aiciv/portal_uploads/to-portal/PT_Org_Structure_OACS.csv'
)

# CSV Name -> existing seeded DB User.name. Only for genuine spelling/nickname
# variants of the SAME person (verified by cross-checking department, manager,
# and role level against the existing record) -- never changes User.name.
NAME_OVERRIDES = {
    "mireille dirany": "mireille dirary",
    "michael schuman": "mike schuman",
    "zenia tata": "zeena tata",
    "edward brennan": "edward brosnan",
    "roger beaini": "roger besini",
    "cora salvador": "cara salvador",
    "jessie cruz": "jesse cruz",
    "mohamad el madhoun": "mohammad el madhoun",
    "phillip bliss": "philip bliss",
    "robert orlowski": "robert oriowski",
    "natasha carrasco": "natasha green",   # CSV email itself still "natasha.green@..." -- confirms same person
    "ashley tom": "ashley tann",
    "ahsen awan": "alonso awan",
    "ethan devore": "ethan devore",         # capitalization only, included for clarity
    "zafeer hassan": "zaheer hassan",
    "shahbaz ali": "shabaz ali",
}

# CSV names that are intentionally NOT auto-matched -- too ambiguous to guess.
# ("Chris Ishii", Operations/C-Suite/reports-to-Jared) vs existing seeded
# ("Chris Isbit", Finance/VP/reports-to-Nils) differ in department, level,
# AND manager -- too large a gap to be simple spelling noise. Could be the
# same person with a corrected name AND a promotion, or two different real
# people. Flagged for Mike/HR to confirm rather than guessed.
AMBIGUOUS_CSV_NAMES = {"chris ishii"}

# Role Level (CSV) -> User.role, used ONLY when creating a brand-new user
# record for someone in the CSV who has no existing seeded row at all.
ROLE_LEVEL_TO_USER_ROLE = {
    "ceo": "admin", "c-suite": "manager", "evp": "manager", "svp": "manager",
    "vp": "employee", "director": "employee", "manager": "manager",
    "team lead": "employee", "individual contributor": "employee",
}

EXCLUDE_USER_IDS = set()  # populated at runtime with non-PT system accounts (e.g. "Meridian")


def norm(name):
    return " ".join(name.strip().lower().split())


def load_csv_rows():
    with open(CSV_PATH, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def build_existing_index():
    """name (normalized) -> User, excluding non-employee system accounts."""
    idx = {}
    for u in User.query.all():
        if norm(u.name) == 'meridian':
            # The agent's own admin account -- not a PT employee, not in the org CSV.
            EXCLUDE_USER_IDS.add(u.id)
            continue
        idx[norm(u.name)] = u
    return idx


def resolve_csv_name(csv_name, existing_idx, created_this_run):
    """Return (User or None, status) for a CSV name against current state."""
    key = norm(csv_name)
    if key in AMBIGUOUS_CSV_NAMES:
        return None, 'ambiguous'
    if key in existing_idx:
        return existing_idx[key], 'matched_exact'
    override_target = NAME_OVERRIDES.get(key)
    if override_target and override_target in existing_idx:
        return existing_idx[override_target], 'matched_override'
    if key in created_this_run:
        return created_this_run[key], 'matched_new'
    return None, 'unmatched'


def run(apply_changes=False):
    app = create_app('production')
    report = {
        'updated': [],       # list of dicts: name, fields changed
        'created': [],       # new users created
        'unmatched_csv': [], # csv rows we could not resolve to any user
        'ambiguous': [],     # explicitly flagged, not auto-resolved
        'unmatched_db': [],  # existing DB employees not present in the CSV at all
    }

    with app.app_context():
        rows = load_csv_rows()
        existing_idx = build_existing_index()
        matched_csv_keys = set()
        created_this_run = {}  # normalized name -> User (for newly created rows, within this run)

        # ── Pass 1: resolve / create every CSV row's own User record ──────
        for row in rows:
            name = row['Name'].strip()
            key = norm(name)
            user, status = resolve_csv_name(name, existing_idx, created_this_run)

            if status == 'ambiguous':
                report['ambiguous'].append({
                    'csv_name': name, 'csv_email': row['Email'],
                    'csv_department': row['Department'], 'csv_manager': row['Manager Name'],
                    'reason': 'Department/manager/level differ too much from any similarly-named '
                              'existing record to auto-match -- needs a human decision.',
                })
                continue

            if user is None:
                # Genuinely new person in the CSV with no seeded record at all.
                role_level = (row.get('Role Level') or '').strip().lower()
                user_role = ROLE_LEVEL_TO_USER_ROLE.get(role_level, 'employee')
                if apply_changes:
                    user = User(
                        email=row['Email'].strip().lower(),
                        name=name,
                        password_hash=generate_password_hash('Seed!' + secrets.token_hex(8)),
                        role=user_role,
                        is_active_user=True,
                    )
                    db.session.add(user)
                    db.session.flush()
                    profile = EmployeeProfile(
                        user_id=user.id,
                        department=row['Department'].strip(),
                        team=row['Team'].strip() or None,
                        title=None,  # not provided by this source -- do NOT fabricate
                        employment_status='active',
                    )
                    db.session.add(profile)
                    db.session.flush()
                    log_change(None, 'User', user.id, 'created_via', None, 'ingest_org_csv.py', action='create')
                report['created'].append({
                    'name': name, 'email': row['Email'], 'department': row['Department'],
                    'team': row['Team'], 'role_level': row['Role Level'],
                    'note': 'No existing seeded record -- created new (title left blank, not provided by CSV).',
                })
                created_this_run[key] = user  # None in dry-run, real object when applying
            matched_csv_keys.add(key)
            if user is not None:
                created_this_run.setdefault(key, user)

        # Re-resolve name->user map including anything created in pass 1,
        # for manager lookups in pass 2 (dry-run: user objects are None for
        # "created" rows, so manager assignment for those is reported only).
        full_idx = dict(existing_idx)
        full_idx.update({k: v for k, v in created_this_run.items() if v is not None})
        pending_new_names = {k for k, v in created_this_run.items() if v is None}

        # ── Pass 2: update email / department / team / manager for every
        #     resolved row ──────────────────────────────────────────────
        for row in rows:
            name = row['Name'].strip()
            key = norm(name)
            if key in AMBIGUOUS_CSV_NAMES:
                continue
            user = full_idx.get(key)
            if user is None or getattr(user, 'id', None) is None:
                # dry-run "created" row with no real persisted id yet -- nothing to diff.
                continue

            profile = EmployeeProfile.query.filter_by(user_id=user.id).first()
            if profile is None:
                # Shouldn't happen (we create profiles for new users above), but
                # guard anyway rather than crash on an unexpected gap.
                continue

            changes = {}
            new_email = row['Email'].strip().lower()
            cur_email = (user.email or '').lower()
            if new_email and new_email != cur_email:
                changes['email'] = (user.email, new_email)

            new_dept = row['Department'].strip()
            new_team = row['Team'].strip() or None
            cur_dept = (profile.department if profile else None)
            cur_team = (profile.team if profile else None)
            if new_dept and new_dept != cur_dept:
                changes['department'] = (cur_dept, new_dept)
            if new_team != cur_team:
                changes['team'] = (cur_team, new_team)

            mgr_name = (row.get('Manager Name') or '').strip()
            new_mgr_user = None
            if mgr_name:
                mgr_key = norm(mgr_name)
                new_mgr_user = full_idx.get(mgr_key) or full_idx.get(NAME_OVERRIDES.get(mgr_key, ''))
            cur_mgr_id = (profile.manager_id if profile else None)
            new_mgr_id = new_mgr_user.id if new_mgr_user else None
            if mgr_name and new_mgr_user is None:
                if norm(mgr_name) in pending_new_names:
                    changes['manager'] = (
                        'PENDING: "%s" will be created by this same run -- manager_id resolves once applied' % mgr_name,
                        None)
                else:
                    changes['manager'] = ('UNRESOLVED: could not find manager "%s" in DB' % mgr_name, None)
            elif new_mgr_id != cur_mgr_id:
                changes['manager_id'] = (cur_mgr_id, new_mgr_id)

            if changes:
                report['updated'].append({'name': user.name, 'user_id': user.id, 'changes': changes})
                if apply_changes:
                    if 'email' in changes:
                        log_change(None, 'User', user.id, 'email', changes['email'][0], changes['email'][1])
                        user.email = new_email
                    if 'department' in changes:
                        log_change(None, 'EmployeeProfile', profile.id, 'department', changes['department'][0], changes['department'][1])
                        profile.department = new_dept
                    if 'team' in changes:
                        log_change(None, 'EmployeeProfile', profile.id, 'team', changes['team'][0], changes['team'][1])
                        profile.team = new_team
                    if 'manager_id' in changes:
                        log_change(None, 'EmployeeProfile', profile.id, 'manager_id', changes['manager_id'][0], changes['manager_id'][1])
                        profile.manager_id = new_mgr_id

        # ── Unmatched CSV rows (shouldn't normally happen given pass 1 always
        #     creates-or-flags, but keep as a safety net) ────────────────────
        for row in rows:
            key = norm(row['Name'].strip())
            if key not in matched_csv_keys and key not in AMBIGUOUS_CSV_NAMES:
                report['unmatched_csv'].append(row['Name'])

        # ── Existing DB employees with no corresponding CSV row at all ──────
        csv_keys_resolved = set()
        for row in rows:
            k = norm(row['Name'].strip())
            if k in AMBIGUOUS_CSV_NAMES:
                continue
            csv_keys_resolved.add(k)
            if k in NAME_OVERRIDES:
                csv_keys_resolved.add(NAME_OVERRIDES[k])
        for key, u in existing_idx.items():
            if key not in csv_keys_resolved:
                report['unmatched_db'].append(u.name)

        if apply_changes:
            db.session.commit()
        else:
            db.session.rollback()

    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Actually write + commit (default is dry-run)')
    args = parser.parse_args()

    result = run(apply_changes=args.apply)

    print(f"\n{'APPLYING' if args.apply else 'DRY RUN'} -- {CSV_PATH}\n")
    print(f"=== UPDATED ({len(result['updated'])}) ===")
    for item in result['updated']:
        print(f"- {item['name']} (user_id={item['user_id']})")
        for field, (old, new) in item['changes'].items():
            print(f"    {field}: {old!r} -> {new!r}")

    print(f"\n=== CREATED NEW ({len(result['created'])}) ===")
    for item in result['created']:
        print(f"- {item['name']} <{item['email']}> dept={item['department']} team={item['team']} level={item['role_level']}")
        print(f"    {item['note']}")

    print(f"\n=== AMBIGUOUS -- NOT AUTO-MATCHED ({len(result['ambiguous'])}) ===")
    for item in result['ambiguous']:
        print(f"- CSV \"{item['csv_name']}\" <{item['csv_email']}> dept={item['csv_department']} mgr={item['csv_manager']}")
        print(f"    {item['reason']}")

    print(f"\n=== CSV ROWS NOT MATCHED TO ANY USER ({len(result['unmatched_csv'])}) ===")
    for name in result['unmatched_csv']:
        print(f"- {name}")

    print(f"\n=== EXISTING DB EMPLOYEES NOT IN THE CSV ({len(result['unmatched_db'])}) ===")
    for name in result['unmatched_db']:
        print(f"- {name}")

    print()
