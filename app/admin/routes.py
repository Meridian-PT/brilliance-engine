import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from app import db
from app.models import (User, Candidate, Position, Interview, Scorecard,
                         NewHire, OnboardingTask, Document, FileAttachment,
                         PIPELINE_STAGES, EmployeeProfile, Policy,
                         PolicyAcknowledgment, TrainingCourse, TrainingCompletion,
                         AssessmentTemplate, AssessmentResult, PTOBalance,
                         PTORequest, ReviewCycle, PerformanceReview,
                         CompensationRecord, BonusRecord, SalaryBand, AuditLog,
                         BenefitPlan, BenefitEnrollment, OpenEnrollmentWindow,
                         AccrualPolicy, Announcement, get_active_announcements_for)
from app.audit import log_change

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

    announcements = get_active_announcements_for(current_user)

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
                           stages=PIPELINE_STAGES,
                           announcements=announcements)


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
            old_role = user.role
            user.email = email
            user.role = role
            if old_role != role:
                log_change(current_user, 'User', user.id, 'role', old_role, role, action='update')
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


# ── Employee Management ─────────────────────────────────────────────────────

@admin_bp.route('/promote-to-employee/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def promote_to_employee(user_id):
    user = User.query.get_or_404(user_id)
    if user.role not in ('newhire', 'candidate'):
        flash(f'{user.name} cannot be promoted to employee from role "{user.role}".', 'error')
        return redirect(url_for('admin.users'))

    profile = EmployeeProfile.query.filter_by(user_id=user.id).first()
    if not profile:
        newhire = NewHire.query.filter_by(user_id=user.id).first()
        profile = EmployeeProfile(
            user_id=user.id,
            department=newhire.department if newhire else '',
            start_date=newhire.start_date if newhire else date.today(),
            manager_id=newhire.manager_id if newhire else None,
            employee_number=f'PT-{1000 + user.id}',
        )
        if newhire and newhire.position:
            profile.title = newhire.position.title
        db.session.add(profile)

    user.role = 'employee'
    db.session.commit()
    flash(f'{user.name} promoted to employee.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/employee-reports')
@login_required
@admin_required
def employee_reports():
    employees = User.query.filter_by(role='employee').all()
    employee_count = len(employees)

    policy_ack_data = []
    for policy in Policy.query.filter_by(is_active=True, requires_acknowledgment=True).all():
        ack_count = PolicyAcknowledgment.query.filter_by(policy_id=policy.id).count()
        policy_ack_data.append({
            'title': policy.title,
            'acknowledged': ack_count,
            'total': employee_count,
            'pct': int(ack_count / employee_count * 100) if employee_count else 0,
        })

    training_data = []
    for course in TrainingCourse.query.filter_by(is_active=True).all():
        completed = TrainingCompletion.query.filter_by(
            course_id=course.id, module_id=None).count()
        training_data.append({
            'title': course.title,
            'required': course.is_required,
            'completed': completed,
            'total': employee_count,
            'pct': int(completed / employee_count * 100) if employee_count else 0,
        })

    assessment_data = []
    for tmpl in AssessmentTemplate.query.filter_by(is_active=True).all():
        taken = AssessmentResult.query.filter_by(template_id=tmpl.id).count()
        passed = AssessmentResult.query.filter_by(template_id=tmpl.id, passed=True).count()
        assessment_data.append({
            'title': tmpl.title,
            'taken': taken,
            'passed': passed,
            'pass_rate': int(passed / taken * 100) if taken else 0,
        })

    pending_pto = PTORequest.query.filter_by(status='pending').count()
    approved_pto = PTORequest.query.filter_by(status='approved').count()

    active_cycles = ReviewCycle.query.filter_by(status='active').all()
    cycle_data = []
    for cycle in active_cycles:
        total_reviews = cycle.reviews.count()
        completed = cycle.reviews.filter_by(status='complete').count()
        cycle_data.append({
            'title': cycle.title,
            'total': total_reviews,
            'completed': completed,
            'pending_self': cycle.reviews.filter_by(status='pending_self').count(),
            'pending_manager': cycle.reviews.filter_by(status='pending_manager').count(),
        })

    return render_template('admin/employee_reports.html',
                           employee_count=employee_count,
                           policy_ack_data=policy_ack_data,
                           training_data=training_data,
                           assessment_data=assessment_data,
                           pending_pto=pending_pto,
                           approved_pto=approved_pto,
                           cycle_data=cycle_data)


# ── Employee System-of-Record (Phase 2) ──────────────────────────────────────

EMPLOYMENT_STATUSES = ['active', 'on_leave', 'terminated', 'suspended']
EMPLOYMENT_TYPES = ['full_time', 'part_time', 'contract', 'intern']


@admin_bp.route('/employees')
@login_required
@admin_required
def employees():
    """Admin-wide employee list (all EmployeeProfile records, any manager)."""
    q = request.args.get('q', '').strip()
    query = EmployeeProfile.query.join(User, EmployeeProfile.user_id == User.id)
    if q:
        like = f'%{q}%'
        query = query.filter(db.or_(User.name.ilike(like), User.email.ilike(like),
                                     EmployeeProfile.department.ilike(like)))
    profiles = query.order_by(User.name).all()
    return render_template('admin/employees.html', profiles=profiles, search=q)


@admin_bp.route('/employees/<int:user_id>')
@login_required
@admin_required
def employee_detail(user_id):
    """Full employee system-of-record view: profile + compensation history."""
    user = User.query.get_or_404(user_id)
    profile = EmployeeProfile.query.filter_by(user_id=user_id).first()

    comp_history = CompensationRecord.query.filter_by(user_id=user_id) \
        .order_by(CompensationRecord.effective_date.desc()).all()
    current_comp = comp_history[0] if comp_history else None
    bonus_history = BonusRecord.query.filter_by(user_id=user_id) \
        .order_by(BonusRecord.award_date.desc()).all()

    managers = User.query.filter(User.role.in_(['manager', 'admin'])).order_by(User.name).all()

    return render_template('admin/employee_detail.html',
                           user=user, profile=profile,
                           comp_history=comp_history, current_comp=current_comp,
                           bonus_history=bonus_history,
                           employment_statuses=EMPLOYMENT_STATUSES,
                           employment_types=EMPLOYMENT_TYPES,
                           managers=managers)


@admin_bp.route('/employees/<int:user_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_employee_profile(user_id):
    """Admin edit of EmployeeProfile — includes employment_status/type/termination,
    which are admin-only (not surfaced on the employee self-service form)."""
    user = User.query.get_or_404(user_id)
    profile = EmployeeProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        profile = EmployeeProfile(user_id=user_id)
        db.session.add(profile)
        db.session.flush()  # assign profile.id before it's used in audit log entries below

    profile.department = request.form.get('department', '').strip() or None
    profile.title = request.form.get('title', '').strip() or None
    profile.employee_number = request.form.get('employee_number', '').strip() or None
    profile.phone = request.form.get('phone', '').strip() or None
    manager_id = request.form.get('manager_id', '')
    profile.manager_id = int(manager_id) if manager_id else None

    start_date_str = request.form.get('start_date', '')
    profile.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else profile.start_date

    profile.address_line1 = request.form.get('address_line1', '').strip() or None
    profile.address_line2 = request.form.get('address_line2', '').strip() or None
    profile.city = request.form.get('city', '').strip() or None
    profile.province_state = request.form.get('province_state', '').strip() or None
    profile.postal_code = request.form.get('postal_code', '').strip() or None
    profile.country = request.form.get('country', '').strip() or None

    dob_str = request.form.get('date_of_birth', '')
    profile.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None

    # ── Sensitive employment fields — audited ──
    old_status = profile.employment_status
    new_status = request.form.get('employment_status', old_status or 'active')
    old_type = profile.employment_type
    new_type = request.form.get('employment_type', '').strip() or None

    term_date_str = request.form.get('termination_date', '')
    new_term_date = datetime.strptime(term_date_str, '%Y-%m-%d').date() if term_date_str else None
    new_term_reason = request.form.get('termination_reason', '').strip() or None

    if new_status != old_status:
        log_change(current_user, 'EmployeeProfile', profile.id or user_id,
                   'employment_status', old_status, new_status, action='update')
        if new_status == 'terminated':
            log_change(current_user, 'EmployeeProfile', profile.id or user_id,
                       'termination', old_status,
                       f'terminated effective {new_term_date or "unspecified"}: {new_term_reason or "no reason given"}',
                       action='update')

    if old_type != new_type:
        log_change(current_user, 'EmployeeProfile', profile.id or user_id,
                   'employment_type', old_type, new_type, action='update')

    profile.employment_status = new_status
    profile.employment_type = new_type
    profile.termination_date = new_term_date
    profile.termination_reason = new_term_reason

    db.session.commit()
    flash(f'{user.name}\'s employee record updated.', 'success')
    return redirect(url_for('admin.employee_detail', user_id=user_id))


# ── Compensation (SENSITIVE — admin-only write) ──────────────────────────────

@admin_bp.route('/employees/<int:user_id>/compensation/add', methods=['POST'])
@login_required
@admin_required
def add_compensation(user_id):
    user = User.query.get_or_404(user_id)

    try:
        base_salary = Decimal(request.form.get('base_salary', '0').strip() or '0')
    except InvalidOperation:
        flash('Invalid base salary amount.', 'error')
        return redirect(url_for('admin.employee_detail', user_id=user_id))

    effective_date_str = request.form.get('effective_date', '')
    if not effective_date_str or base_salary <= 0:
        flash('Base salary and effective date are required.', 'error')
        return redirect(url_for('admin.employee_detail', user_id=user_id))

    record = CompensationRecord(
        user_id=user_id,
        base_salary=base_salary,
        currency=request.form.get('currency', 'CAD').strip() or 'CAD',
        pay_frequency=request.form.get('pay_frequency', '').strip() or None,
        effective_date=datetime.strptime(effective_date_str, '%Y-%m-%d').date(),
        change_reason=request.form.get('change_reason', '').strip() or None,
        created_by=current_user.id,
    )
    db.session.add(record)
    db.session.flush()
    log_change(current_user, 'CompensationRecord', record.id, 'base_salary',
               None, f'{record.base_salary} {record.currency} eff. {record.effective_date}',
               action='create')
    db.session.commit()
    flash(f'Compensation record added for {user.name}.', 'success')
    return redirect(url_for('admin.employee_detail', user_id=user_id))


@admin_bp.route('/employees/<int:user_id>/bonus/add', methods=['POST'])
@login_required
@admin_required
def add_bonus(user_id):
    user = User.query.get_or_404(user_id)

    try:
        amount = Decimal(request.form.get('amount', '0').strip() or '0')
    except InvalidOperation:
        flash('Invalid bonus amount.', 'error')
        return redirect(url_for('admin.employee_detail', user_id=user_id))

    award_date_str = request.form.get('award_date', '')
    if not award_date_str or amount <= 0:
        flash('Amount and award date are required.', 'error')
        return redirect(url_for('admin.employee_detail', user_id=user_id))

    record = BonusRecord(
        user_id=user_id,
        amount=amount,
        currency=request.form.get('currency', 'CAD').strip() or 'CAD',
        bonus_type=request.form.get('bonus_type', '').strip() or None,
        award_date=datetime.strptime(award_date_str, '%Y-%m-%d').date(),
        note=request.form.get('note', '').strip() or None,
        created_by=current_user.id,
    )
    db.session.add(record)
    db.session.flush()
    log_change(current_user, 'BonusRecord', record.id, 'amount',
               None, f'{record.amount} {record.currency} ({record.bonus_type or "bonus"})',
               action='create')
    db.session.commit()
    flash(f'Bonus record added for {user.name}.', 'success')
    return redirect(url_for('admin.employee_detail', user_id=user_id))


# ── Salary Bands (admin reference data) ──────────────────────────────────────

@admin_bp.route('/salary-bands', methods=['GET', 'POST'])
@login_required
@admin_required
def salary_bands():
    if request.method == 'POST':
        try:
            salary_min = Decimal(request.form.get('salary_min', '').strip() or '0') or None
            salary_mid = Decimal(request.form.get('salary_mid', '').strip() or '0') or None
            salary_max = Decimal(request.form.get('salary_max', '').strip() or '0') or None
        except InvalidOperation:
            flash('Salary band values must be numbers.', 'error')
            return redirect(url_for('admin.salary_bands'))

        level = request.form.get('level', '').strip()
        if not level:
            flash('Level is required.', 'error')
            return redirect(url_for('admin.salary_bands'))

        band = SalaryBand(
            level=level,
            department=request.form.get('department', '').strip() or None,
            currency=request.form.get('currency', 'CAD').strip() or 'CAD',
            salary_min=salary_min,
            salary_mid=salary_mid,
            salary_max=salary_max,
        )
        db.session.add(band)
        db.session.commit()
        flash(f'Salary band "{level}" created.', 'success')
        return redirect(url_for('admin.salary_bands'))

    bands = SalaryBand.query.order_by(SalaryBand.department, SalaryBand.level).all()
    return render_template('admin/salary_bands.html', bands=bands)


# ── Audit Trail ───────────────────────────────────────────────────────────────

@admin_bp.route('/audit')
@login_required
@admin_required
def audit_log():
    entity_type = request.args.get('entity_type', '').strip()
    query = AuditLog.query
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    entries = query.order_by(AuditLog.created_at.desc()).limit(200).all()

    entity_types = sorted(set(
        r[0] for r in db.session.query(AuditLog.entity_type).distinct().all() if r[0]
    ))

    return render_template('admin/audit.html', entries=entries,
                           entity_types=entity_types, current_type=entity_type)


# ── Benefits Administration (Phase 3) ─────────────────────────────────────────

BENEFIT_PLAN_TYPES = ['health', 'dental', 'vision', 'life', 'rrsp', 'other']


@admin_bp.route('/benefits', methods=['GET', 'POST'])
@login_required
@admin_required
def benefits():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        plan_type = request.form.get('plan_type', '').strip()
        if not name or not plan_type:
            flash('Plan name and type are required.', 'error')
            return redirect(url_for('admin.benefits'))

        plan = BenefitPlan(
            name=name,
            plan_type=plan_type,
            provider=request.form.get('provider', '').strip() or None,
            tier=request.form.get('tier', '').strip() or None,
            description=request.form.get('description', '').strip() or None,
        )
        db.session.add(plan)
        db.session.commit()
        flash(f'Benefit plan "{name}" created.', 'success')
        return redirect(url_for('admin.benefits'))

    plans = BenefitPlan.query.order_by(BenefitPlan.is_active.desc(), BenefitPlan.name).all()
    return render_template('admin/benefits.html', plans=plans, plan_types=BENEFIT_PLAN_TYPES)


@admin_bp.route('/benefits/<int:plan_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_benefit_plan(plan_id):
    plan = BenefitPlan.query.get_or_404(plan_id)

    if request.method == 'POST':
        plan.name = request.form.get('name', plan.name).strip()
        plan.plan_type = request.form.get('plan_type', plan.plan_type).strip()
        plan.provider = request.form.get('provider', '').strip() or None
        plan.tier = request.form.get('tier', '').strip() or None
        plan.description = request.form.get('description', '').strip() or None
        plan.is_active = 'is_active' in request.form
        db.session.commit()
        flash(f'Benefit plan "{plan.name}" updated.', 'success')
        return redirect(url_for('admin.benefits'))

    return render_template('admin/benefit_edit.html', plan=plan, plan_types=BENEFIT_PLAN_TYPES)


@admin_bp.route('/benefits/<int:plan_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_benefit_plan(plan_id):
    plan = BenefitPlan.query.get_or_404(plan_id)
    plan.is_active = not plan.is_active
    db.session.commit()
    flash(f'"{plan.name}" {"activated" if plan.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin.benefits'))


@admin_bp.route('/enrollment-windows', methods=['GET', 'POST'])
@login_required
@admin_required
def enrollment_windows():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        start_str = request.form.get('start_date', '')
        end_str = request.form.get('end_date', '')

        if not name or not start_str or not end_str:
            flash('Name, start date, and end date are required.', 'error')
            return redirect(url_for('admin.enrollment_windows'))

        start = datetime.strptime(start_str, '%Y-%m-%d').date()
        end = datetime.strptime(end_str, '%Y-%m-%d').date()
        if end < start:
            flash('End date must be on or after start date.', 'error')
            return redirect(url_for('admin.enrollment_windows'))

        window = OpenEnrollmentWindow(name=name, start_date=start, end_date=end, is_active=True)
        db.session.add(window)
        db.session.commit()
        flash(f'Enrollment window "{name}" created.', 'success')
        return redirect(url_for('admin.enrollment_windows'))

    windows = OpenEnrollmentWindow.query.order_by(OpenEnrollmentWindow.start_date.desc()).all()
    return render_template('admin/enrollment_windows.html', windows=windows)


@admin_bp.route('/enrollment-windows/<int:window_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_enrollment_window(window_id):
    window = OpenEnrollmentWindow.query.get_or_404(window_id)

    if request.method == 'POST':
        window.name = request.form.get('name', window.name).strip()
        start_str = request.form.get('start_date', '')
        end_str = request.form.get('end_date', '')
        if start_str:
            window.start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        if end_str:
            window.end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        window.is_active = 'is_active' in request.form
        db.session.commit()
        flash(f'Enrollment window "{window.name}" updated.', 'success')
        return redirect(url_for('admin.enrollment_windows'))

    return render_template('admin/enrollment_window_edit.html', window=window)


@admin_bp.route('/enrollment-windows/<int:window_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_enrollment_window(window_id):
    window = OpenEnrollmentWindow.query.get_or_404(window_id)
    window.is_active = not window.is_active
    db.session.commit()
    flash(f'"{window.name}" {"activated" if window.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin.enrollment_windows'))


# ── Leave Management — Accrual Policies (Phase 3) ────────────────────────────

ACCRUAL_LEAVE_TYPES = ['vacation', 'sick', 'personal']
ACCRUAL_PERIODS = ['monthly', 'per_pay', 'annual']


@admin_bp.route('/accrual-policies', methods=['GET', 'POST'])
@login_required
@admin_required
def accrual_policies():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        leave_type = request.form.get('leave_type', '').strip()
        try:
            rate = float(request.form.get('rate_per_period', '0') or '0')
        except ValueError:
            flash('Rate per period must be a number.', 'error')
            return redirect(url_for('admin.accrual_policies'))

        if not name or not leave_type or rate <= 0:
            flash('Name, leave type, and a positive accrual rate are required.', 'error')
            return redirect(url_for('admin.accrual_policies'))

        annual_cap = request.form.get('annual_cap', '').strip()
        carryover_max = request.form.get('carryover_max', '').strip()

        policy = AccrualPolicy(
            name=name,
            leave_type=leave_type,
            rate_per_period=rate,
            period=request.form.get('period', 'monthly'),
            annual_cap=float(annual_cap) if annual_cap else None,
            carryover_max=float(carryover_max) if carryover_max else None,
        )
        db.session.add(policy)
        db.session.commit()
        flash(f'Accrual policy "{name}" created.', 'success')
        return redirect(url_for('admin.accrual_policies'))

    policies = AccrualPolicy.query.order_by(AccrualPolicy.is_active.desc(), AccrualPolicy.name).all()
    return render_template('admin/accrual_policies.html', policies=policies,
                           leave_types=ACCRUAL_LEAVE_TYPES, periods=ACCRUAL_PERIODS)


@admin_bp.route('/accrual-policies/<int:policy_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_accrual_policy(policy_id):
    policy = AccrualPolicy.query.get_or_404(policy_id)

    if request.method == 'POST':
        policy.name = request.form.get('name', policy.name).strip()
        policy.leave_type = request.form.get('leave_type', policy.leave_type).strip()
        try:
            policy.rate_per_period = float(request.form.get('rate_per_period', policy.rate_per_period))
        except ValueError:
            flash('Rate per period must be a number.', 'error')
            return redirect(url_for('admin.edit_accrual_policy', policy_id=policy_id))
        policy.period = request.form.get('period', policy.period)
        annual_cap = request.form.get('annual_cap', '').strip()
        carryover_max = request.form.get('carryover_max', '').strip()
        policy.annual_cap = float(annual_cap) if annual_cap else None
        policy.carryover_max = float(carryover_max) if carryover_max else None
        policy.is_active = 'is_active' in request.form
        db.session.commit()
        flash(f'Accrual policy "{policy.name}" updated.', 'success')
        return redirect(url_for('admin.accrual_policies'))

    return render_template('admin/accrual_policy_edit.html', policy=policy,
                           leave_types=ACCRUAL_LEAVE_TYPES, periods=ACCRUAL_PERIODS)


# ── Reporting & Analytics (Phase 3) ───────────────────────────────────────────

@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    # Headcount by department (active employees)
    headcount_rows = db.session.query(
        EmployeeProfile.department, db.func.count(EmployeeProfile.id)
    ).filter(EmployeeProfile.employment_status == 'active').group_by(EmployeeProfile.department).all()
    headcount_labels = [r[0] or 'Unassigned' for r in headcount_rows]
    headcount_values = [r[1] for r in headcount_rows]

    # Employment status breakdown
    status_rows = db.session.query(
        EmployeeProfile.employment_status, db.func.count(EmployeeProfile.id)
    ).group_by(EmployeeProfile.employment_status).all()
    status_labels = [(r[0] or 'active').replace('_', ' ').title() for r in status_rows]
    status_values = [r[1] for r in status_rows]

    # Turnover by month (last 12 months, based on termination_date)
    terminated = EmployeeProfile.query.filter(
        EmployeeProfile.employment_status == 'terminated',
        EmployeeProfile.termination_date.isnot(None)
    ).all()
    turnover_counts = {}
    for p in terminated:
        key = p.termination_date.strftime('%Y-%m')
        turnover_counts[key] = turnover_counts.get(key, 0) + 1
    turnover_labels = sorted(turnover_counts.keys())
    turnover_values = [turnover_counts[k] for k in turnover_labels]

    # PTO utilization (used vs total) per employee, current year
    pto_rows = PTOBalance.query.filter_by(year=date.today().year).join(
        User, PTOBalance.user_id == User.id).order_by(User.name).all()
    pto_labels = [p.user.name for p in pto_rows]
    pto_used = [p.vacation_used + p.sick_used + p.personal_used for p in pto_rows]
    pto_total = [p.vacation_total + p.sick_total + p.personal_total for p in pto_rows]

    # Policy acknowledgment rate
    employee_count = User.query.filter_by(role='employee').count()
    policy_labels, policy_values = [], []
    for policy in Policy.query.filter_by(is_active=True, requires_acknowledgment=True).all():
        ack_count = PolicyAcknowledgment.query.filter_by(policy_id=policy.id).count()
        policy_labels.append(policy.title)
        policy_values.append(int(ack_count / employee_count * 100) if employee_count else 0)

    # Training completion rate
    training_labels, training_values = [], []
    for course in TrainingCourse.query.filter_by(is_active=True).all():
        completed = TrainingCompletion.query.filter_by(course_id=course.id, module_id=None).count()
        training_labels.append(course.title)
        training_values.append(int(completed / employee_count * 100) if employee_count else 0)

    return render_template('admin/analytics.html',
                           headcount_labels=headcount_labels, headcount_values=headcount_values,
                           status_labels=status_labels, status_values=status_values,
                           turnover_labels=turnover_labels, turnover_values=turnover_values,
                           pto_labels=pto_labels, pto_used=pto_used, pto_total=pto_total,
                           policy_labels=policy_labels, policy_values=policy_values,
                           training_labels=training_labels, training_values=training_values)


@admin_bp.route('/analytics/export/headcount.csv')
@login_required
@admin_required
def export_headcount_csv():
    import csv
    import io
    from flask import Response

    rows = db.session.query(
        EmployeeProfile.department, db.func.count(EmployeeProfile.id)
    ).filter(EmployeeProfile.employment_status == 'active').group_by(EmployeeProfile.department).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Department', 'Active Headcount'])
    for department, count in rows:
        writer.writerow([department or 'Unassigned', count])

    return Response(buf.getvalue(), mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename=headcount.csv'})


@admin_bp.route('/analytics/export/pto.csv')
@login_required
@admin_required
def export_pto_csv():
    import csv
    import io
    from flask import Response

    rows = PTOBalance.query.filter_by(year=date.today().year).join(
        User, PTOBalance.user_id == User.id).order_by(User.name).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Employee', 'Email', 'Year', 'Vacation Used', 'Vacation Total',
                      'Sick Used', 'Sick Total', 'Personal Used', 'Personal Total', 'Total Remaining'])
    for p in rows:
        writer.writerow([p.user.name, p.user.email, p.year,
                          p.vacation_used, p.vacation_total,
                          p.sick_used, p.sick_total,
                          p.personal_used, p.personal_total,
                          p.total_remaining])

    return Response(buf.getvalue(), mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename=pto_utilization.csv'})


# ── Announcements / Company News (Phase 3) ────────────────────────────────────

@admin_bp.route('/announcements', methods=['GET', 'POST'])
@login_required
@admin_required
def announcements():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        if not title or not content:
            flash('Title and content are required.', 'error')
            return redirect(url_for('admin.announcements'))

        expires_str = request.form.get('expires_at', '')
        expires_at = datetime.strptime(expires_str, '%Y-%m-%d') if expires_str else None

        ann = Announcement(
            title=title,
            content=content,
            audience=request.form.get('audience', '').strip() or 'all',
            author_id=current_user.id,
            published_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            is_pinned='is_pinned' in request.form,
        )
        db.session.add(ann)
        db.session.commit()
        flash(f'Announcement "{title}" published.', 'success')
        return redirect(url_for('admin.announcements'))

    departments = db.session.query(EmployeeProfile.department).filter(
        EmployeeProfile.department.isnot(None)).distinct().all()
    departments = sorted(set(d[0] for d in departments if d[0]))

    all_announcements = Announcement.query.order_by(
        Announcement.is_pinned.desc(), Announcement.published_at.desc()).all()
    return render_template('admin/announcements.html', announcements=all_announcements,
                           departments=departments)


@admin_bp.route('/announcements/<int:announcement_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_announcement(announcement_id):
    ann = Announcement.query.get_or_404(announcement_id)

    if request.method == 'POST':
        ann.title = request.form.get('title', ann.title).strip()
        ann.content = request.form.get('content', ann.content).strip()
        ann.audience = request.form.get('audience', '').strip() or 'all'
        expires_str = request.form.get('expires_at', '')
        ann.expires_at = datetime.strptime(expires_str, '%Y-%m-%d') if expires_str else None
        ann.is_pinned = 'is_pinned' in request.form
        db.session.commit()
        flash(f'Announcement "{ann.title}" updated.', 'success')
        return redirect(url_for('admin.announcements'))

    departments = db.session.query(EmployeeProfile.department).filter(
        EmployeeProfile.department.isnot(None)).distinct().all()
    departments = sorted(set(d[0] for d in departments if d[0]))
    return render_template('admin/announcement_edit.html', ann=ann, departments=departments)


@admin_bp.route('/announcements/<int:announcement_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_announcement(announcement_id):
    ann = Announcement.query.get_or_404(announcement_id)
    title = ann.title
    db.session.delete(ann)
    db.session.commit()
    flash(f'Announcement "{title}" deleted.', 'success')
    return redirect(url_for('admin.announcements'))
