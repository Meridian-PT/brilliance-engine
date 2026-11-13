"""Token helpers for the invite / forgot-password flow (Phase 6).

Raw tokens are 32-byte url-safe random strings (secrets.token_urlsafe),
sent only in the email link. We persist a SHA-256 hash of the token, never
the token itself -- mirrors how passwords are never stored in plaintext.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app import db
from app.models import PasswordResetToken

INVITE_EXPIRY_HOURS = 24 * 7   # 7 days -- employees may not check email same-day
RESET_EXPIRY_HOURS = 2          # forgot-password links are short-lived


def _hash(raw_token):
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def create_token(user, purpose='invite', created_by=None):
    """Invalidate any outstanding unused tokens of this purpose for the user,
    then create + return (PasswordResetToken, raw_token). Caller is
    responsible for committing."""
    now = datetime.now(timezone.utc)
    PasswordResetToken.query.filter_by(user_id=user.id, purpose=purpose, used_at=None).update(
        {'used_at': now}
    )

    raw_token = secrets.token_urlsafe(32)
    hours = INVITE_EXPIRY_HOURS if purpose == 'invite' else RESET_EXPIRY_HOURS
    record = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash(raw_token),
        purpose=purpose,
        expires_at=now + timedelta(hours=hours),
        created_by=(created_by.id if created_by else None),
    )
    db.session.add(record)
    db.session.flush()
    return record, raw_token


def consume_token(raw_token, purpose=None):
    """Look up a valid (unused, unexpired) token by its raw value. Returns
    the PasswordResetToken record (NOT yet marked used -- caller marks it
    used only after successfully setting the new password, in the same
    transaction) or None if invalid/expired/already used/wrong purpose."""
    if not raw_token:
        return None
    record = PasswordResetToken.query.filter_by(token_hash=_hash(raw_token)).first()
    if record is None:
        return None
    if purpose and record.purpose != purpose:
        return None
    if not record.is_valid:
        return None
    return record


def mark_used(record):
    record.used_at = datetime.now(timezone.utc)
