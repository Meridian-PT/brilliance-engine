"""Phase 4 — generic ingestion API for external systems.

Currently exposes a single endpoint (`POST /api/v1/time-entries`) that lets
an external time-tracking product push time entries into Brilliance Engine
without a logged-in session. This blueprint is exempted from Flask-WTF's
CSRFProtect (see app/__init__.py) since it's authenticated via a static
token header instead of a session cookie.
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User, EmployeeProfile, TimeEntry

api_bp = Blueprint('api', __name__)


def _check_token():
    """Static-token auth: compare the X-API-Token header against
    current_app.config['TIMETRACK_API_TOKEN'] (env var TIMETRACK_API_TOKEN
    in production, dev default in config.py)."""
    token = request.headers.get('X-API-Token', '')
    expected = current_app.config.get('TIMETRACK_API_TOKEN', '')
    return bool(token) and bool(expected) and token == expected


def _resolve_user(payload):
    """Resolve the target employee from `employee_email` or
    `employee_number` (matching EmployeeProfile.employee_number)."""
    email = (payload.get('employee_email') or '').strip().lower()
    if email:
        return User.query.filter_by(email=email).first()
    emp_number = (payload.get('employee_number') or '').strip()
    if emp_number:
        profile = EmployeeProfile.query.filter_by(employee_number=emp_number).first()
        return profile.user if profile else None
    return None


def _create_entry_from_payload(payload):
    """Validate a single entry payload and stage a TimeEntry row
    (added to db.session, NOT committed). Returns (entry, None) on success
    or (None, error_message) on validation failure."""
    user = _resolve_user(payload)
    if not user:
        return None, 'Unknown employee — employee_email or employee_number did not match any user.'

    work_date_str = payload.get('work_date', '')
    try:
        work_date = datetime.strptime(work_date_str, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None, 'work_date is required in YYYY-MM-DD format.'

    try:
        hours = Decimal(str(payload.get('hours', '')))
        if hours <= 0:
            raise InvalidOperation('hours must be positive')
    except (InvalidOperation, TypeError, ValueError):
        return None, 'hours is required and must be a positive number.'

    entry = TimeEntry(
        user_id=user.id,
        work_date=work_date,
        hours=hours,
        project_or_task=(payload.get('project_or_task') or '').strip() or None,
        description=(payload.get('description') or '').strip() or None,
        status='submitted',
        source='imported',
    )
    db.session.add(entry)
    return entry, None


@api_bp.route('/time-entries', methods=['POST'])
def create_time_entries():
    """Ingestion hook for an external time-tracking system.

    Auth: static token via the `X-API-Token` request header, checked
    against the TIMETRACK_API_TOKEN config value. Missing or mismatched
    token -> 401.

    Expected JSON body — a single entry object:
        {
          "employee_email": "jordan.blake@puretechnology.nyc",
          "work_date": "2026-10-27",
          "hours": 7.5,
          "project_or_task": "Client X — onboarding flow",
          "description": "optional free-text notes"
        }

    ...or a batch of entries:
        { "entries": [ { ... }, { ... } ] }

    Either `employee_email` or `employee_number` (matching
    EmployeeProfile.employee_number) must be provided to identify the
    employee. `work_date` (YYYY-MM-DD) and a positive `hours` are required;
    `project_or_task` and `description` are optional free text.

    Every row created via this endpoint is stamped `source='imported'` and
    `status='submitted'`, so it flows through the same manager-approval
    queue as self-logged entries (see manager.time_approvals) — no special
    handling needed once a row lands in the table.

    Responses:
      - Single entry: 201 {"success": true, "id": <int>} on success,
        400 {"success": false, "error": "..."} on validation failure.
      - Batch: 201 {"results": [...]} if every entry succeeded, 207 if some
        (but not all) succeeded, 400 if none succeeded.
      - 401 if the X-API-Token header is missing or incorrect.
    """
    if not _check_token():
        return jsonify({'error': 'Unauthorized — missing or invalid X-API-Token header.'}), 401

    body = request.get_json(silent=True)
    if not body or not isinstance(body, dict):
        return jsonify({'error': 'Request body must be a JSON object.'}), 400

    payloads = body['entries'] if isinstance(body.get('entries'), list) else [body]
    if not payloads:
        return jsonify({'error': 'No entries provided.'}), 400

    results = []
    any_success = False
    any_failure = False
    for payload in payloads:
        if not isinstance(payload, dict):
            results.append({'success': False, 'error': 'Entry must be a JSON object.'})
            any_failure = True
            continue
        entry, error = _create_entry_from_payload(payload)
        if error:
            results.append({'success': False, 'error': error})
            any_failure = True
        else:
            db.session.flush()
            results.append({'success': True, 'id': entry.id})
            any_success = True

    if not any_success:
        db.session.rollback()
        return jsonify({'results': results} if len(payloads) > 1 else results[0]), 400

    db.session.commit()

    if len(payloads) == 1:
        return jsonify(results[0]), 201

    status_code = 201 if not any_failure else 207
    return jsonify({'results': results}), status_code
