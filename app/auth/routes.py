from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User

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
