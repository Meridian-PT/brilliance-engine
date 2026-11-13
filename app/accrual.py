"""Nightly PTO accrual engine (Production Hardening, Nov 2026).

Applies every active AccrualPolicy to every active employee, crediting the
matching PTOBalance.*_total field by `rate_per_period`.

Idempotency: the real guarantee is a DB-level UNIQUE constraint on
`accrual_runs(policy_id, user_id, period_key)` (see AccrualRun in
app/models.py). The job always attempts an INSERT for the current period
before crediting the balance; if that period has already been accrued for
that employee under that policy, the INSERT is rejected and the balance is
left untouched. This means the job is safe to run multiple times a day, after
a crash mid-run, or concurrently -- it is not relying on "only run once a
month" scheduling discipline to stay correct, only on the DB constraint.

Usage:
    flask accrue-pto                    # registered CLI command (recommended)
    python3 -m app.accrual              # standalone script entrypoint

Scheduling: intended to run nightly via a Render Cron Job
(`flask accrue-pto`), see render.yaml.
"""
from datetime import date

from sqlalchemy import extract
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import AccrualPolicy, AccrualRun, EmployeeProfile, PTOBalance

LEAVE_FIELD = {
    'vacation': 'vacation_total',
    'sick': 'sick_total',
    'personal': 'personal_total',
}

# Anchor Monday for the first per_pay (biweekly) period. Only used by
# 'per_pay' policies; adjust if Pure Technology's actual payroll calendar
# anchor differs -- flagged as a placeholder in the handoff report.
PAY_PERIOD_ANCHOR = date(2026, 1, 5)


def _period_key(policy, run_date):
    if policy.period == 'monthly':
        return f"{run_date.year}-{run_date.month:02d}"
    if policy.period == 'annual':
        return f"{run_date.year}"
    if policy.period == 'per_pay':
        idx = (run_date - PAY_PERIOD_ANCHOR).days // 14
        return f"pay-{idx}"
    # Unrecognized period value on a policy -- still produce a deterministic,
    # per-day key so it doesn't collide with a real period and doesn't crash;
    # caller surfaces this as an error for admin attention.
    return f"unknown-{run_date.isoformat()}"


def run_accrual(run_date=None):
    """Run accrual for all active policies against all active employees.

    Returns a summary dict. Safe to call repeatedly for the same run_date or
    across retries -- see module docstring for the idempotency guarantee.
    """
    run_date = run_date or date.today()
    summary = {
        'run_date': run_date.isoformat(),
        'policies_evaluated': 0,
        'accrued': 0,
        'skipped_already_run': 0,
        'skipped_capped': 0,
        'errors': [],
    }

    policies = AccrualPolicy.query.filter_by(is_active=True).all()
    employees = EmployeeProfile.query.filter_by(employment_status='active').all()

    for policy in policies:
        summary['policies_evaluated'] += 1
        field = LEAVE_FIELD.get(policy.leave_type)
        if not field:
            summary['errors'].append(
                f"policy {policy.id} ({policy.name}): unrecognized leave_type "
                f"'{policy.leave_type}', skipped entirely")
            continue

        period_key = _period_key(policy, run_date)

        for profile in employees:
            user_id = profile.user_id

            if policy.annual_cap is not None:
                ytd = db.session.query(db.func.coalesce(db.func.sum(AccrualRun.amount), 0.0)).filter(
                    AccrualRun.policy_id == policy.id,
                    AccrualRun.user_id == user_id,
                    extract('year', AccrualRun.run_at) == run_date.year,
                ).scalar()
                if ytd >= policy.annual_cap:
                    summary['skipped_capped'] += 1
                    continue
                amount = min(policy.rate_per_period, policy.annual_cap - ytd)
            else:
                amount = policy.rate_per_period

            if amount <= 0:
                summary['skipped_capped'] += 1
                continue

            # Idempotent insert -- DB unique constraint is the real guard,
            # not this check. A second concurrent/duplicate run gets an
            # IntegrityError here and simply skips crediting the balance.
            run_row = AccrualRun(policy_id=policy.id, user_id=user_id,
                                  period_key=period_key, amount=amount)
            db.session.add(run_row)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                summary['skipped_already_run'] += 1
                continue

            balance = PTOBalance.query.filter_by(user_id=user_id, year=run_date.year).first()
            if balance is None:
                balance = PTOBalance(user_id=user_id, year=run_date.year,
                                      vacation_total=0, vacation_used=0,
                                      sick_total=0, sick_used=0,
                                      personal_total=0, personal_used=0)
                db.session.add(balance)
                db.session.flush()

            setattr(balance, field, (getattr(balance, field) or 0) + amount)
            db.session.commit()
            summary['accrued'] += 1

    return summary


def register_cli(app):
    """Register `flask accrue-pto` as a CLI command on the given app."""
    @app.cli.command('accrue-pto')
    def accrue_pto_command():
        """Run the nightly PTO accrual job once, for today."""
        result = run_accrual()
        print(result)


if __name__ == '__main__':
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import create_app

    app = create_app(os.environ.get('FLASK_CONFIG', 'production'))
    with app.app_context():
        print(run_accrual())
