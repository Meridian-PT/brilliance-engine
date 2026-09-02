import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date, timezone
from app import db
from app.models import (User, Candidate, Position, Interview, Scorecard,
                         NewHire, OnboardingTask, Document, FileAttachment,
                         PIPELINE_STAGES)

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin')


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied. Admin only.', 'error')
            return redirect(url_for('auth.landing'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    total_candidates = Candidate.query.count()
    active_candidates = Candidate.query.filter(Candidate.status.in_(['active', 'interviewing'])).count()
    total_positions = Position.query.count()
    open_positions = Position.query.filter_by(status='open').count()
    total_hires = Candidate.query.filter_by(status='hired').count()
    total_newhires = NewHire.query.count()
    total_documents = Document.query.count()

    # Pipeline breakdown
    pipeline = {}
    for key, label in PIPELINE_STAGES:
        count = Candidate.query.filter_by(current_stage=key, status='active').count()
        count += Candidate.query.filter_by(current_stage=key, status='interviewing').count()
        pipeline[label] = count

    # Recent candidates
    recent_candidates = Candidate.query.order_by(Candidate.applied_at.desc()).limit(10).all()

    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           total_candidates=total_candidates,
                           active_candidates=active_candidates,
                           total_positions=total_positions,
                           open_positions=open_positions,
                           total_hires=total_hires,
                           total_newhires=total_newhires,
                           total_documents=total_documents,
                           pipeline=pipeline,
                           recent_candidates=recent_candidates,
                           stages=PIPELINE_STAGES)


# ── Users ────────────────────────────────────────────────────────────────────

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'candidate')

        if not all([name, email, password]):
            flash('All fields are required.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Email already exists.', 'error')
        else:
            user = User(name=name, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(f'User {name} created as {role}.', 'success')
            return redirect(url_for('admin.users'))

    return render_template('admin/create_user.html')


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.name = request.form.get('name', user.name).strip()
        email = request.form.get('email', user.email).strip().lower()
        role = request.form.get('role', user.role)
        password = request.form.get('password', '').strip()

        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if existing:
            flash('Email already in use by another user.', 'error')
        else:
            user.email = email
            user.role = role
            if password:
                user.set_password(password)
            db.session.commit()
            flash(f'User {user.name} updated.', 'success')
            return redirect(url_for('admin.users'))

    return render_template('admin/edit_user.html', user=user)


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate yourself.', 'error')
    else:
        user.is_active_user = not user.is_active_user
        db.session.commit()
        status = 'activated' if user.is_active_user else 'deactivated'
        flash(f'{user.name} has been {status}.', 'success')
    return redirect(url_for('admin.users'))


# ── Positions ────────────────────────────────────────────────────────────────

@admin_bp.route('/positions/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_position():
    if request.method == 'POST':
        position = Position(
            title=request.form.get('title', '').strip(),
            department=request.form.get('department', '').strip(),
            location=request.form.get('location', '').strip(),
            employment_type=request.form.get('employment_type', 'Full-Time'),
            description=request.form.get('description', '').strip(),
            requirements=request.form.get('requirements', '').strip(),
            salary_range_low=int(request.form.get('salary_low', 0)) or None,
            salary_range_high=int(request.form.get('salary_high', 0)) or None,
            hiring_manager_id=int(request.form.get('hiring_manager_id', 0)) or None,
            status='open',
        )
        db.session.add(position)
        db.session.commit()
        flash(f'Position "{position.title}" created.', 'success')
        return redirect(url_for('manager.positions'))

    managers = User.query.filter(User.role.in_(['manager', 'admin'])).all()
    return render_template('admin/create_position.html', managers=managers)


@admin_bp.route('/positions/<int:position_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_position(position_id):
    position = Position.query.get_or_404(position_id)

    if request.method == 'POST':
        position.title = request.form.get('title', position.title).strip()
        position.department = request.form.get('department', '').strip()
        position.location = request.form.get('location', '').strip()
        position.employment_type = request.form.get('employment_type', 'Full-Time')
        position.description = request.form.get('description', '').strip()
        position.requirements = request.form.get('requirements', '').strip()
        position.salary_range_low = int(request.form.get('salary_low', 0)) or None
        position.salary_range_high = int(request.form.get('salary_high', 0)) or None
        position.hiring_manager_id = int(request.form.get('hiring_manager_id', 0)) or None
        position.status = request.form.get('status', position.status)
        db.session.commit()
        flash(f'Position "{position.title}" updated.', 'success')
        return redirect(url_for('manager.positions'))

    managers = User.query.filter(User.role.in_(['manager', 'admin'])).all()
    return render_template('admin/edit_position.html', position=position, managers=managers)


# ── Onboarding ───────────────────────────────────────────────────────────────

@admin_bp.route('/onboarding/setup/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def setup_onboarding(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        start_date_str = request.form.get('start_date', '')
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None

        # Create or update NewHire profile
        profile = NewHire.query.filter_by(user_id=user_id).first()
        if not profile:
            profile = NewHire(user_id=user_id)
            db.session.add(profile)

        profile.start_date = start_date
        profile.department = request.form.get('department', '')
        profile.manager_id = int(request.form.get('manager_id', 0)) or None
        profile.buddy_id = int(request.form.get('buddy_id', 0)) or None
        profile.position_id = int(request.form.get('position_id', 0)) or None

        # Update user role to newhire
        user.role = 'newhire'

        db.session.commit()

        # Create default onboarding tasks
        _create_default_tasks(profile.id)

        flash(f'Onboarding set up for {user.name}.', 'success')
        return redirect(url_for('admin.dashboard'))

    managers = User.query.filter(User.role.in_(['manager', 'admin'])).all()
    all_users = User.query.filter(User.role.in_(['manager', 'admin', 'newhire'])).all()
    positions = Position.query.all()

    return render_template('admin/setup_onboarding.html',
                           user=user, managers=managers,
                           all_users=all_users, positions=positions)


# ── Documents ────────────────────────────────────────────────────────────────

@admin_bp.route('/documents')
@login_required
@admin_required
def documents():
    docs = Document.query.order_by(Document.category, Document.title).all()
    # Build file lookup for documents that have uploaded files
    file_lookup = {}
    for doc in docs:
        attachment = FileAttachment.query.filter_by(
            attachment_type='document', attachment_id=doc.id
        ).first()
        if attachment:
            file_lookup[doc.id] = attachment
    return render_template('admin/documents.html', documents=docs, file_lookup=file_lookup)


@admin_bp.route('/documents/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_document():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        module = request.form.get('module', '').strip()
        description = request.form.get('description', '').strip()
        is_template = 'is_template' in request.form
        file = request.files.get('file')

        if not title:
            flash('Title is required.', 'error')
        else:
            file_type = ''
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                file_type = ext

            doc = Document(
                title=title,
                category=category or None,
                module=module or None,
                description=description or None,
                file_type=file_type or None,
                origin='uploaded',
                is_template=is_template,
            )
            db.session.add(doc)
            db.session.flush()

            if file and file.filename:
                stored_name = f"{uuid.uuid4().hex}.{file_type}" if file_type else uuid.uuid4().hex
                attachment = FileAttachment(
                    filename=stored_name,
                    original_filename=file.filename,
                    mime_type=file.content_type,
                    file_size=0,
                    file_data=file.read(),
                    uploaded_by=current_user.id,
                    attachment_type='document',
                    attachment_id=doc.id,
                )
                attachment.file_size = len(attachment.file_data)
                db.session.add(attachment)

            db.session.commit()
            flash(f'Document "{title}" uploaded.', 'success')
            return redirect(url_for('admin.documents'))

    return render_template('admin/upload_document.html')


# ── Search ───────────────────────────────────────────────────────────────────

@admin_bp.route('/search')
@login_required
@admin_required
def search():
    q = request.args.get('q', '').strip()
    results = {'users': [], 'candidates': [], 'positions': [], 'documents': []}

    if q:
        like = f'%{q}%'
        results['users'] = User.query.filter(
            db.or_(User.name.ilike(like), User.email.ilike(like))
        ).limit(20).all()
        results['candidates'] = Candidate.query.join(User).join(Position).filter(
            db.or_(User.name.ilike(like), User.email.ilike(like), Position.title.ilike(like))
        ).limit(20).all()
        results['positions'] = Position.query.filter(
            db.or_(Position.title.ilike(like), Position.department.ilike(like),
                   Position.location.ilike(like))
        ).limit(20).all()
        results['documents'] = Document.query.filter(
            db.or_(Document.title.ilike(like), Document.description.ilike(like),
                   Document.category.ilike(like))
        ).limit(20).all()

    total = sum(len(v) for v in results.values())
    return render_template('admin/search.html', q=q, results=results, total=total)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _create_default_tasks(new_hire_id):
    """Create the standard Pure Start onboarding tasks."""
    existing = OnboardingTask.query.filter_by(new_hire_id=new_hire_id).count()
    if existing > 0:
        return

    tasks = [
        # Pre-Start
        ('Sign offer letter and employment agreement', 'pre_start', -5, 'newhire', 'Complete and return your signed offer letter'),
        ('Complete background check authorization', 'pre_start', -5, 'newhire', 'Submit the background check form'),
        ('Set up IT accounts (email, Slack, tools)', 'pre_start', -2, 'it', 'IT team creates all necessary accounts'),
        ('Prepare welcome package and swag', 'pre_start', -1, 'hr', 'Culture card, welcome letter, company swag'),
        ('Assign onboarding buddy', 'pre_start', -1, 'hr', 'Pair with a team member for the first 90 days'),

        # Day 1
        ('Welcome meeting with manager', 'day_1', 0, 'manager', 'Meet your manager, discuss expectations and first-week plan'),
        ('Read the Culture Card', 'day_1', 0, 'newhire', 'Understand PT\'s 7 pillars and Actualizing Brilliance philosophy'),
        ('Watch the Welcome Video', 'day_1', 0, 'newhire', 'CEO welcome and company overview'),
        ('Meet your onboarding buddy', 'day_1', 0, 'buddy', 'Your go-to person for questions and guidance'),
        ('Complete IT setup and tool access', 'day_1', 0, 'newhire', 'Verify all accounts work and you have access to everything'),
        ('Read the Employee Handbook', 'day_1', 0, 'newhire', 'Review policies, benefits, and expectations'),

        # Week 1
        ('Team introductions (all departments)', 'week_1', 3, 'manager', 'Meet the broader team'),
        ('Review role expectations and KPIs', 'week_1', 3, 'manager', 'Clear alignment on what success looks like'),
        ('Complete mandatory compliance training', 'week_1', 5, 'newhire', 'Required training modules'),
        ('Shadow key team members', 'week_1', 5, 'newhire', 'Observe how the team works day-to-day'),
        ('End-of-week check-in with manager', 'week_1', 5, 'manager', 'How was the first week? Questions? Concerns?'),

        # 30-Day
        ('30-day check-in with manager', 'day_30', 30, 'manager', 'Review progress, address any concerns, adjust expectations'),
        ('Self-assessment: How am I doing?', 'day_30', 30, 'newhire', 'Reflect on your first month — what\'s working, what needs support'),
        ('Buddy check-in', 'day_30', 30, 'buddy', 'Informal check — are you settling in?'),
        ('Complete all initial training modules', 'day_30', 30, 'newhire', 'Finish any remaining training'),

        # 60-Day
        ('60-day performance check-in', 'day_60', 60, 'manager', 'Progress review — are we on track?'),
        ('Begin independent project work', 'day_60', 60, 'newhire', 'Start contributing independently to team goals'),
        ('Feedback session: What can we improve?', 'day_60', 60, 'newhire', 'Your fresh eyes are valuable — tell us what you see'),

        # 90-Day
        ('90-day formal review', 'day_90', 90, 'manager', 'Comprehensive review of performance, fit, and development plan'),
        ('Probation review (if applicable)', 'day_90', 90, 'hr', 'Formal probation period assessment'),
        ('Set goals for next quarter', 'day_90', 90, 'manager', 'Align on objectives for the next 90 days'),
        ('Onboarding complete celebration', 'day_90', 90, 'hr', 'You made it! Welcome to the team — for real.'),
    ]

    for title, category, due_day, assigned_to, description in tasks:
        task = OnboardingTask(
            new_hire_id=new_hire_id,
            title=title,
            category=category,
            due_day=due_day,
            assigned_to=assigned_to,
            description=description,
        )
        db.session.add(task)

    db.session.commit()
