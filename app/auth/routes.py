from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
from app.tokens import consume_token, create_token, mark_used
from app.audit import log_change

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for(f'{current_user.role}.dashboard'))
    return render_template('landing.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(f'{current_user.role}.dashboard'))

    role = request.args.get('role', 'candidate')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            flash(f'Welcome back, {user.name}!', 'success')
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for(f'{user.role}.dashboard'))
        else:
            flash('Invalid email or password.', 'error')

    role_labels = {
        'candidate': ('Candidate Portal', 'Track your application and get to know us'),
        'newhire': ('New Hire Portal', 'Your onboarding journey starts here'),
        'employee': ('Employee Hub', 'Policies, training, time off, performance, and more'),
        'manager': ('Hiring Manager Portal', 'Manage your pipeline and build your team'),
        'admin': ('HR Admin Portal', 'Full system access'),
    }
    label, subtitle = role_labels.get(role, role_labels['candidate'])

    return render_template('auth/login.html', role=role, label=label, subtitle=subtitle)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(f'{current_user.role}.dashboard'))

    role = request.args.get('role', 'candidate')

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        reg_role = request.form.get('role', 'candidate')

        if not all([name, email, password]):
            flash('All fields are required.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        elif len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
        elif reg_role in ('admin', 'manager'):
            flash('Admin and Manager accounts must be created by HR.', 'error')
        else:
            user = User(name=name, email=email, role=reg_role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=True)
            flash(f'Welcome to Pure Technology, {name}!', 'success')
            return redirect(url_for(f'{reg_role}.dashboard'))

    return render_template('auth/register.html', role=role)


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if name:
            current_user.name = name
        if email and email != current_user.email:
            existing = User.query.filter(User.email == email, User.id != current_user.id).first()
            if existing:
                flash('Email already in use.', 'error')
                return redirect(url_for('auth.profile'))
            current_user.email = email

        if new_password:
            if not current_user.check_password(current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('auth.profile'))
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('auth.profile'))
            if len(new_password) < 8:
                flash('Password must be at least 8 characters.', 'error')
                return redirect(url_for('auth.profile'))
            current_user.set_password(new_password)

        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.landing'))


# ── Invite / Forgot-Password (Phase 6) ────────────────────────────────────────

@auth_bp.route('/set-password/<token>', methods=['GET', 'POST'])
def set_password(token):
    """Landing page for an invite link -- lets a seeded employee (whose
    account exists with an unknown system-generated password) choose their
    own password for the first time."""
    if current_user.is_authenticated:
        logout_user()

    record = consume_token(token, purpose='invite')
    if record is None:
        flash('This invite link is invalid or has expired. Ask HR to resend it.', 'error')
        return redirect(url_for('auth.landing'))

    user = record.user

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        else:
            old_hash = user.password_hash
            user.set_password(password)
            mark_used(record)
            log_change(None, 'User', user.id, 'password_hash', 'invite-set', 'set-by-user', action='update')
            db.session.commit()
            login_user(user, remember=True)
            flash(f'Welcome, {user.name}! Your password is set — you\'re logged in.', 'success')
            return redirect(url_for(f'{user.role}.dashboard'))

    return render_template('auth/set_password.html', user=user, mode='invite', token=token)


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first() if email else None
        if user and user.is_active_user:
            from app.mailer import send_reset_email, MailerNotConfigured
            record, raw_token = create_token(user, purpose='reset')
            db.session.commit()
            try:
                send_reset_email(user, raw_token)
            except MailerNotConfigured:
                flash('Mail is not configured on this deployment. Contact HR directly.', 'error')
                return render_template('auth/forgot_password.html')
            except Exception:
                flash('Could not send the reset email right now. Try again shortly.', 'error')
                return render_template('auth/forgot_password.html')
        # Deliberately identical messaging whether or not the email matched,
        # so this endpoint can't be used to enumerate valid accounts.
        flash('If that email is on file, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.landing'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        logout_user()

    record = consume_token(token, purpose='reset')
    if record is None:
        flash('This reset link is invalid or has expired. Request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))

    user = record.user

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        else:
            user.set_password(password)
            mark_used(record)
            log_change(None, 'User', user.id, 'password_hash', 'reset-requested', 'reset-by-user', action='update')
            db.session.commit()
            flash('Password updated. You can now log in.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/set_password.html', user=user, mode='reset', token=token)
