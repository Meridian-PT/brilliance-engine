"""Outbound transactional email for Brilliance Engine (invite / password reset).

Sends via the Meridian PT Gmail account over SMTP port 587 + STARTTLS (port 465
is blocked in this environment -- same gotcha documented for the agent's own
mail tooling). Credentials come from environment variables only, never
hardcoded: MERIDIAN_GMAIL_EMAIL / MERIDIAN_GMAIL_APP_PASSWORD. These must be
set as Render env vars on the brilliance-engine web service (and are picked up
locally from /home/aiciv/.env during development/testing).

Display name is always "Pure Technology - People Team" regardless of the
underlying Gmail address, so recipients see a people-ops-branded sender.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

SENDER_DISPLAY_NAME = "Pure Technology - People Team"


class MailerNotConfigured(RuntimeError):
    pass


def _credentials():
    email = os.environ.get('MERIDIAN_GMAIL_EMAIL')
    password = os.environ.get('MERIDIAN_GMAIL_APP_PASSWORD')
    if not email or not password:
        raise MailerNotConfigured(
            'MERIDIAN_GMAIL_EMAIL / MERIDIAN_GMAIL_APP_PASSWORD are not set in the environment.'
        )
    return email, password


def _send_via_smtp(to_email, subject, html_body, text_body):
    sender_email, app_password = _credentials()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = formataddr((SENDER_DISPLAY_NAME, sender_email))
    msg['To'] = to_email

    if text_body:
        msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    # Explicit timeout: without one, a blocked/filtered outbound SMTP port
    # (common on PaaS hosts) causes smtplib to hang until the OS TCP
    # timeout, which is longer than gunicorn's worker timeout -- the worker
    # gets SIGKILLed mid-request (a bare 500, no clean exception) instead of
    # this raising a catchable socket.timeout. Fail fast and loud instead.
    with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as server:
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, [to_email], msg.as_string())


def _send_via_agentmail(to_email, subject, html_body, text_body):
    """Fallback transport: Render's web service network blocks outbound
    SMTP (confirmed via live E2E test, Nov 13 2026 -- `[Errno 101] Network
    is unreachable` connecting to smtp.gmail.com:587). AgentMail's send is
    a plain HTTPS POST, unaffected by that egress restriction. Same
    display name is set as the From header; the underlying address is the
    PT AgentMail inbox rather than the Gmail account when this path is used."""
    api_key = os.environ.get('AGENTMAIL_API_KEY')
    inbox_id = os.environ.get('AGENTMAIL_INBOX_ID', 'meridian-pt@agentmail.to')
    if not api_key:
        raise MailerNotConfigured('Neither SMTP nor AgentMail (AGENTMAIL_API_KEY) is usable from this host.')

    from agentmail import AgentMail
    client = AgentMail(api_key=api_key)
    client.inboxes.messages.send(
        inbox_id,
        to=to_email,
        subject=subject,
        html=html_body,
        text=text_body,
        headers={'From': formataddr((SENDER_DISPLAY_NAME, inbox_id))},
    )


def send_email(to_email, subject, html_body, text_body=None):
    """Send one email, SMTP first (matches the originally-specified Gmail
    sender), automatically falling back to AgentMail's HTTPS API only on a
    network-level failure (not on auth/credential errors, which should
    surface as-is). Raises MailerNotConfigured if neither transport is
    usable; raises the underlying exception on a genuine send failure --
    callers should catch and flash/log rather than let this 500 an
    admin-facing request."""
    try:
        _send_via_smtp(to_email, subject, html_body, text_body)
    except MailerNotConfigured:
        _send_via_agentmail(to_email, subject, html_body, text_body)
    except OSError:
        # Network is unreachable / connection refused / timed out -- the
        # egress-blocked case. Fall back rather than fail the request.
        _send_via_agentmail(to_email, subject, html_body, text_body)


def _app_base_url():
    return os.environ.get('APP_BASE_URL', 'https://brilliance-engine.onrender.com').rstrip('/')


def send_invite_email(user, raw_token):
    link = f"{_app_base_url()}/set-password/{raw_token}"
    subject = "Set up your Brilliance Engine login — Pure Technology"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto;">
      <h2 style="color:#f1420b;">Welcome to Brilliance Engine</h2>
      <p>Hi {user.name},</p>
      <p>Pure Technology's HR system, <strong>Brilliance Engine</strong>, is ready for you. Click below
      to set your own password and log in:</p>
      <p style="margin: 24px 0;">
        <a href="{link}" style="background:#f1420b;color:#fff;padding:12px 24px;border-radius:6px;
           text-decoration:none;font-weight:bold;">Set my password</a>
      </p>
      <p style="color:#888; font-size: 0.85rem;">This link expires in 7 days and can only be used once.
      If you didn't expect this email, you can ignore it.</p>
      <p>— Pure Technology People Team</p>
    </div>
    """
    text = f"Hi {user.name},\n\nSet up your Brilliance Engine login here (expires in 7 days):\n{link}\n\n— Pure Technology People Team"
    send_email(user.email, subject, html, text)


def send_reset_email(user, raw_token):
    link = f"{_app_base_url()}/reset-password/{raw_token}"
    subject = "Reset your Brilliance Engine password — Pure Technology"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto;">
      <h2 style="color:#f1420b;">Password reset requested</h2>
      <p>Hi {user.name},</p>
      <p>We received a request to reset your Brilliance Engine password. Click below to choose a new one:</p>
      <p style="margin: 24px 0;">
        <a href="{link}" style="background:#f1420b;color:#fff;padding:12px 24px;border-radius:6px;
           text-decoration:none;font-weight:bold;">Reset my password</a>
      </p>
      <p style="color:#888; font-size: 0.85rem;">This link expires in 2 hours and can only be used once.
      If you didn't request this, you can safely ignore this email — your password will not change.</p>
      <p>— Pure Technology People Team</p>
    </div>
    """
    text = f"Hi {user.name},\n\nReset your Brilliance Engine password here (expires in 2 hours):\n{link}\n\n— Pure Technology People Team"
    send_email(user.email, subject, html, text)
