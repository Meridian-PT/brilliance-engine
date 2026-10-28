import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timezone
from app import db
from app.models import (User, Document, FileAttachment, EmployeeProfile, Policy,
                         PolicyAcknowledgment, ContentAccessLog, AssessmentTemplate,
                         AssessmentResult, TrainingCourse, TrainingModule,
                         TrainingCompletion, PTOBalance, PTORequest, ReviewCycle,
                         PerformanceReview, CompensationRecord, BonusRecord)

employee_bp = Blueprint('employee', __name__, template_folder='../templates/employee')


def employee_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('employee', 'admin'):
            flash('Access denied. Employee portal only.', 'error')
            return redirect(url_for('auth.landing'))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ────────────────────────────────────────────────────────────────

@employee_bp.route('/dashboard')
@login_required
@employee_required
def dashboard():
    profile = EmployeeProfile.query.filter_by(user_id=current_user.id).first()

    # Stats
    total_policies = Policy.query.filter_by(is_active=True, requires_acknowledgment=True).count()
    acked_policies = PolicyAcknowledgment.query.filter_by(user_id=current_user.id).count()

    completed_trainings = TrainingCompletion.query.filter_by(user_id=current_user.id) \
        .filter(TrainingCompletion.module_id.is_(None)).count()
    total_courses = TrainingCourse.query.filter_by(is_active=True).count()

    pto = PTOBalance.query.filter_by(user_id=current_user.id, year=date.today().year).first()
    pto_remaining = pto.total_remaining if pto else 0

    # Latest review
    latest_review = PerformanceReview.query.filter_by(employee_id=current_user.id) \
        .order_by(PerformanceReview.submitted_at.desc()).first()
    review_score = latest_review.self_rating if latest_review and latest_review.self_rating else None

    # Recent activity
    recent_acks = PolicyAcknowledgment.query.filter_by(user_id=current_user.id) \
        .order_by(PolicyAcknowledgment.acknowledged_at.desc()).limit(3).all()
    recent_completions = TrainingCompletion.query.filter_by(user_id=current_user.id) \
        .order_by(TrainingCompletion.completed_at.desc()).limit(3).all()

    # Pending items
    pending_pto = PTORequest.query.filter_by(user_id=current_user.id, status='pending').count()
    active_reviews = PerformanceReview.query.filter_by(
        employee_id=current_user.id, status='pending_self').count()

    return render_template('employee/dashboard.html',
                           profile=profile,
                           acked_policies=acked_policies,
                           total_policies=total_policies,
                           completed_trainings=completed_trainings,
                           total_courses=total_courses,
                           pto_remaining=pto_remaining,
                           review_score=review_score,
                           recent_acks=recent_acks,
                           recent_completions=recent_completions,
                           pending_pto=pending_pto,
                           active_reviews=active_reviews)


# ── Policies ─────────────────────────────────────────────────────────────────

@employee_bp.route('/policies')
@login_required
@employee_required
def policies():
    all_policies = Policy.query.filter_by(is_active=True).order_by(Policy.category, Policy.title).all()
    acked_ids = {a.policy_id for a in PolicyAcknowledgment.query.filter_by(user_id=current_user.id).all()}

    # Group by category
    grouped = {}
    for p in all_policies:
        cat = p.category or 'general'
        grouped.setdefault(cat, []).append(p)

    total_req = sum(1 for p in all_policies if p.requires_acknowledgment)
    total_acked = sum(1 for p in all_policies if p.requires_acknowledgment and p.id in acked_ids)

    return render_template('employee/policies.html',
                           grouped=grouped,
                           acked_ids=acked_ids,
                           total_req=total_req,
                           total_acked=total_acked)


@employee_bp.route('/policies/<int:policy_id>')
@login_required
@employee_required
def policy_detail(policy_id):
    policy = Policy.query.get_or_404(policy_id)
    acked = PolicyAcknowledgment.query.filter_by(
        policy_id=policy_id, user_id=current_user.id).first()
    return render_template('employee/policy_detail.html', policy=policy, acked=acked)


@employee_bp.route('/policies/<int:policy_id>/acknowledge', methods=['POST'])
@login_required
@employee_required
def acknowledge_policy(policy_id):
    policy = Policy.query.get_or_404(policy_id)
    existing = PolicyAcknowledgment.query.filter_by(
        policy_id=policy_id, user_id=current_user.id).first()
    if not existing:
        ack = PolicyAcknowledgment(policy_id=policy_id, user_id=current_user.id)
        db.session.add(ack)
        db.session.commit()
        flash(f'You have acknowledged "{policy.title}".', 'success')
    else:
        flash('Already acknowledged.', 'info')
    return redirect(url_for('employee.policies'))


# ── Content Library ──────────────────────────────────────────────────────────

@employee_bp.route('/content')
@login_required
@employee_required
def content_library():
    category = request.args.get('category', '')
    search = request.args.get('q', '').strip()

    query = Document.query.filter_by(is_active=True)
    if category:
        query = query.filter_by(category=category)
    if search:
        like = f'%{search}%'
        query = query.filter(db.or_(Document.title.ilike(like), Document.description.ilike(like)))

    docs = query.order_by(Document.category, Document.title).all()

    categories = db.session.query(Document.category).filter(
        Document.is_active == True, Document.category.isnot(None)
    ).distinct().all()
    categories = sorted(set(c[0] for c in categories if c[0]))

    return render_template('employee/content_library.html',
                           documents=docs, categories=categories,
                           current_category=category, search=search)


@employee_bp.route('/content/<int:doc_id>')
@login_required
@employee_required
def content_detail(doc_id):
    doc = Document.query.get_or_404(doc_id)
    attachment = FileAttachment.query.filter_by(
        attachment_type='document', attachment_id=doc.id).first()

    # Log access
    log = ContentAccessLog(document_id=doc.id, user_id=current_user.id)
    db.session.add(log)
    db.session.commit()

    return render_template('employee/content_detail.html', document=doc, attachment=attachment)


# ── Assessments ──────────────────────────────────────────────────────────────

@employee_bp.route('/assessments')
@login_required
@employee_required
def assessments():
    templates = AssessmentTemplate.query.filter_by(is_active=True).all()
    results = {r.template_id: r for r in
               AssessmentResult.query.filter_by(user_id=current_user.id)
               .order_by(AssessmentResult.completed_at.desc()).all()}
    return render_template('employee/assessments.html',
                           templates=templates, results=results)


@employee_bp.route('/assessments/<int:template_id>/take', methods=['GET', 'POST'])
@login_required
@employee_required
def take_assessment(template_id):
    template = AssessmentTemplate.query.get_or_404(template_id)
    questions = template.get_questions()

    if request.method == 'POST':
        answers = {}
        correct = 0
        total = len(questions)

        for i, q in enumerate(questions):
            answer = request.form.get(f'q_{i}', '')
            answers[str(i)] = answer
            if q.get('correct') and answer == q['correct']:
                correct += 1

        score = int(correct / total * 100) if total > 0 else 0
        passed = score >= template.passing_score

        # Count attempts
        attempt = AssessmentResult.query.filter_by(
            template_id=template_id, user_id=current_user.id).count() + 1

        result = AssessmentResult(
            template_id=template_id,
            user_id=current_user.id,
            answers=json.dumps(answers),
            score=score,
            passed=passed,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            attempt_number=attempt,
        )
        db.session.add(result)
        db.session.commit()

        flash(f'Assessment complete! Score: {score}% — {"Passed" if passed else "Not passed"}',
              'success' if passed else 'warning')
        return redirect(url_for('employee.assessment_result', result_id=result.id))

    return render_template('employee/take_assessment.html',
                           template=template, questions=questions)


@employee_bp.route('/assessments/result/<int:result_id>')
@login_required
@employee_required
def assessment_result(result_id):
    result = AssessmentResult.query.get_or_404(result_id)
    if result.user_id != current_user.id and current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('employee.assessments'))
    questions = result.template.get_questions()
    answers = json.loads(result.answers) if result.answers else {}
    return render_template('employee/assessment_result.html',
                           result=result, questions=questions, answers=answers)


# ── Training Studio ──────────────────────────────────────────────────────────

@employee_bp.route('/training')
@login_required
@employee_required
def training():
    courses = TrainingCourse.query.filter_by(is_active=True).order_by(
        TrainingCourse.is_required.desc(), TrainingCourse.title).all()

    # Get completion data for each course
    course_data = []
    for course in courses:
        progress = course.user_progress(current_user.id)
        course_completed = TrainingCompletion.query.filter_by(
            course_id=course.id, user_id=current_user.id, module_id=None).first()
        course_data.append({
            'course': course,
            'progress': progress,
            'completed': course_completed is not None,
            'modules_count': course.modules_count,
        })

    return render_template('employee/training.html', course_data=course_data)


@employee_bp.route('/training/<int:course_id>')
@login_required
@employee_required
def course_detail(course_id):
    course = TrainingCourse.query.get_or_404(course_id)
    modules = course.modules.all()

    completed_ids = {c.module_id for c in TrainingCompletion.query.filter_by(
        course_id=course_id, user_id=current_user.id
    ).filter(TrainingCompletion.module_id.isnot(None)).all()}

    progress = course.user_progress(current_user.id)
    course_completed = TrainingCompletion.query.filter_by(
        course_id=course_id, user_id=current_user.id, module_id=None).first()

    return render_template('employee/course_detail.html',
                           course=course, modules=modules,
                           completed_ids=completed_ids, progress=progress,
                           course_completed=course_completed)


@employee_bp.route('/training/<int:course_id>/module/<int:module_id>', methods=['GET', 'POST'])
@login_required
@employee_required
def module_viewer(course_id, module_id):
    course = TrainingCourse.query.get_or_404(course_id)
    module = TrainingModule.query.get_or_404(module_id)
    modules = course.modules.all()

    is_completed = TrainingCompletion.query.filter_by(
        course_id=course_id, module_id=module_id, user_id=current_user.id).first()

    if request.method == 'POST':
        if not is_completed:
            completion = TrainingCompletion(
                course_id=course_id, module_id=module_id, user_id=current_user.id)
            db.session.add(completion)

            # Check if all modules done → mark course complete
            all_modules = course.modules.all()
            completed_ids = {c.module_id for c in TrainingCompletion.query.filter_by(
                course_id=course_id, user_id=current_user.id
            ).filter(TrainingCompletion.module_id.isnot(None)).all()}
            completed_ids.add(module_id)

            if len(completed_ids) >= len(all_modules):
                existing_course_completion = TrainingCompletion.query.filter_by(
                    course_id=course_id, user_id=current_user.id, module_id=None).first()
                if not existing_course_completion:
                    course_completion = TrainingCompletion(
                        course_id=course_id, user_id=current_user.id, module_id=None)
                    db.session.add(course_completion)
                    flash(f'Congratulations! You completed "{course.title}"!', 'success')

            db.session.commit()
            flash('Module marked complete.', 'success')

        # Navigate to next module
        current_idx = next((i for i, m in enumerate(modules) if m.id == module_id), 0)
        if current_idx < len(modules) - 1:
            next_mod = modules[current_idx + 1]
            return redirect(url_for('employee.module_viewer',
                                    course_id=course_id, module_id=next_mod.id))
        return redirect(url_for('employee.course_detail', course_id=course_id))

    # Get prev/next
    current_idx = next((i for i, m in enumerate(modules) if m.id == module_id), 0)
    prev_module = modules[current_idx - 1] if current_idx > 0 else None
    next_module = modules[current_idx + 1] if current_idx < len(modules) - 1 else None

    return render_template('employee/module_viewer.html',
                           course=course, module=module,
                           prev_module=prev_module, next_module=next_module,
                           is_completed=is_completed,
                           current_num=current_idx + 1, total_modules=len(modules))


# ── Time Off ─────────────────────────────────────────────────────────────────

@employee_bp.route('/time-off')
@login_required
@employee_required
def time_off():
    pto = PTOBalance.query.filter_by(user_id=current_user.id, year=date.today().year).first()
    requests = PTORequest.query.filter_by(user_id=current_user.id) \
        .order_by(PTORequest.created_at.desc()).all()
    return render_template('employee/time_off.html', pto=pto, requests=requests)


@employee_bp.route('/time-off/request', methods=['GET', 'POST'])
@login_required
@employee_required
def request_time_off():
    if request.method == 'POST':
        leave_type = request.form.get('leave_type', 'vacation')
        start_str = request.form.get('start_date', '')
        end_str = request.form.get('end_date', '')
        reason = request.form.get('reason', '').strip()

        if not start_str or not end_str:
            flash('Start and end dates are required.', 'error')
            return redirect(url_for('employee.request_time_off'))

        start = datetime.strptime(start_str, '%Y-%m-%d').date()
        end = datetime.strptime(end_str, '%Y-%m-%d').date()

        if end < start:
            flash('End date must be on or after start date.', 'error')
            return redirect(url_for('employee.request_time_off'))

        days = (end - start).days + 1
        # Exclude weekends (rough calc)
        import math
        weeks = days // 7
        remaining = days % 7
        business_days = weeks * 5 + min(remaining, 5)

        pto_req = PTORequest(
            user_id=current_user.id,
            leave_type=leave_type,
            start_date=start,
            end_date=end,
            days_requested=business_days,
            reason=reason,
        )
        db.session.add(pto_req)
        db.session.commit()
        flash(f'Time off request submitted ({business_days} day{"s" if business_days != 1 else ""}).', 'success')
        return redirect(url_for('employee.time_off'))

    return render_template('employee/request_time_off.html')


# ── Performance ──────────────────────────────────────────────────────────────

@employee_bp.route('/performance')
@login_required
@employee_required
def performance():
    reviews = PerformanceReview.query.filter_by(employee_id=current_user.id) \
        .order_by(PerformanceReview.submitted_at.desc()).all()
    active_cycles = ReviewCycle.query.filter_by(status='active').all()

    # Find reviews pending self-assessment
    pending_reviews = PerformanceReview.query.filter_by(
        employee_id=current_user.id, status='pending_self').all()

    return render_template('employee/performance.html',
                           reviews=reviews, active_cycles=active_cycles,
                           pending_reviews=pending_reviews)


@employee_bp.route('/performance/self-review/<int:review_id>', methods=['GET', 'POST'])
@login_required
@employee_required
def self_review(review_id):
    review = PerformanceReview.query.get_or_404(review_id)
    if review.employee_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('employee.performance'))

    if request.method == 'POST':
        review.self_rating = int(request.form.get('self_rating', 3))
        review.self_comments = request.form.get('self_comments', '').strip()
        review.goals_next_period = request.form.get('goals_next_period', '').strip()
        review.status = 'pending_manager'
        review.submitted_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('Self-review submitted successfully.', 'success')
        return redirect(url_for('employee.performance'))

    return render_template('employee/self_review.html', review=review)


# ── Profile ──────────────────────────────────────────────────────────────────

@employee_bp.route('/profile')
@login_required
@employee_required
def my_profile():
    profile = EmployeeProfile.query.filter_by(user_id=current_user.id).first()

    # Read-only compensation: own CURRENT record only (most recent effective_date).
    # No manager visibility in this phase, and never shown to anyone but the
    # employee themselves or an admin.
    current_comp = CompensationRecord.query.filter_by(user_id=current_user.id) \
        .order_by(CompensationRecord.effective_date.desc()).first()
    bonus_history = BonusRecord.query.filter_by(user_id=current_user.id) \
        .order_by(BonusRecord.award_date.desc()).all()

    return render_template('employee/my_profile.html', profile=profile,
                           current_comp=current_comp, bonus_history=bonus_history)


@employee_bp.route('/profile/edit', methods=['POST'])
@login_required
@employee_required
def edit_profile():
    profile = EmployeeProfile.query.filter_by(user_id=current_user.id).first()
    if profile:
        # Non-sensitive self-service fields only. employment_status,
        # employment_type, and termination fields are admin-managed (see
        # admin.edit_employee_profile) and intentionally not editable here.
        profile.phone = request.form.get('phone', '').strip() or profile.phone
        profile.emergency_contact_name = request.form.get('emergency_contact_name', '').strip() or profile.emergency_contact_name
        profile.emergency_contact_phone = request.form.get('emergency_contact_phone', '').strip() or profile.emergency_contact_phone
        profile.address_line1 = request.form.get('address_line1', '').strip() or None
        profile.address_line2 = request.form.get('address_line2', '').strip() or None
        profile.city = request.form.get('city', '').strip() or None
        profile.province_state = request.form.get('province_state', '').strip() or None
        profile.postal_code = request.form.get('postal_code', '').strip() or None
        profile.country = request.form.get('country', '').strip() or None

        dob_str = request.form.get('date_of_birth', '').strip()
        if dob_str:
            try:
                profile.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date of birth format.', 'error')
                return redirect(url_for('employee.my_profile'))

        db.session.commit()
        flash('Profile updated.', 'success')
    return redirect(url_for('employee.my_profile'))
