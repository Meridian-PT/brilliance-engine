"""Audit trail helper for sensitive changes (Phase 2 — Employee System-of-Record).

Usage:
    from app.audit import log_change
    log_change(current_user, 'CompensationRecord', record.id, 'base_salary',
               old_value=None, new_value=str(record.base_salary), action='create')

Call this for: CompensationRecord/BonusRecord creation, employment_status
changes, terminations, and user role changes. Does not commit — callers
should add the AuditLog to the same db.session.commit() as the underlying
change so both succeed or fail together.
"""
from datetime import datetime, timezone
from app import db
from app.models import AuditLog


def log_change(actor, entity_type, entity_id, field_name, old_value, new_value, action='update'):
    """Create an AuditLog row (added to session, not committed).

    Args:
        actor: the User performing the change (current_user), or None for system actions.
        entity_type: string name of the model being changed (e.g. 'CompensationRecord').
        entity_id: primary key of the affected row (may be None for not-yet-flushed rows).
        field_name: the specific field changed (e.g. 'base_salary', 'employment_status').
        old_value: previous value, stringified (or None).
        new_value: new value, stringified (or None).
        action: 'create', 'update', or 'delete'.
    """
    entry = AuditLog(
        actor_id=actor.id if actor is not None and getattr(actor, 'id', None) else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(entry)
    return entry
