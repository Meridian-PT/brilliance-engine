from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timezone
from app import db
from app.models import (Candidate, Position, Interview, Scorecard, User,
                         CandidateNote, PIPELINE_STAGES, NewHire)

manager_bp = Blueprint('manager', __name__, template_folder='../templates/manager')


def manager_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('manager', 'admin'):
            flash('Access denied.', 'error')
            return redirect(url_for('auth.landing'))
        return f(*args, **kwargs)
    return decorated


def can_access_candidate(candidate):
    """Check if current user can access this candidate."""
    if current_user.role == 'admin':
        return True
    return candidate.position.hiring_manager_id == current_user.id


@manager_bp.route('/dashboard')
@login_required
@manager_required
def dashboard():
    # Get positions managed by this user (or all if admin)
    if current_user.role == 'admin':
        positions = Position.query.all()
        candidates = Candidate.query.all()
    else:
        positions = Position.query.filter_by(hiring_manager_id=current_user.id).all()
        pos_ids = [p.id for p in positions]
        candidates = Candidate.query.filter(Candidate.position_id.in_(pos_ids)).all() if pos_ids else []

    active = [c for c in candidates if c.status in ('active', 'interviewing')]
    by_stage = {}
    for c in active:
        stage = c.current_stage
        by_stage.setdefault(stage, []).append(c)

    return render_template('manager/dashboard.html',
                           positions=positions,
                           candidates=candidates,
                           active_candidates=active,
                           by_stage=by_stage,
                           stages=PIPELINE_STAGES)


@manager_bp.route('/candidate/<int:candidate_id>')
@login_required
@manager_required
def candidate_detail(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    if not can_access_candidate(candidate):
        flash('Access denied.', 'error')
        return redirect(url_for('manager.dashboard'))
    scorecards = Scorecard.query.filter_by(candidate_id=candidate_id).all()
    interviews = Interview.query.filter_by(candidate_id=candidate_id).order_by(Interview.scheduled_at).all()
    notes = CandidateNote.query.filter_by(candidate_id=candidate_id).order_by(CandidateNote.created_at.desc()).all()
    managers = User.query.filter(User.role.in_(['manager', 'admin'])).all()
    return render_template('manager/candidate_detail.html',
                           candidate=candidate,
                           scorecards=scorecards,
                           interviews=interviews,
                           notes=notes,
                           managers=managers,
                           stages=PIPELINE_STAGES)


@manager_bp.route('/candidate/<int:candidate_id>/advance', methods=['POST'])
@login_required
@manager_required
def advance_candidate(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    if not can_access_candidate(candidate):
        flash('Access denied.', 'error')
        return redirect(url_for('manager.dashboard'))
    stage_keys = [s[0] for s in PIPELINE_STAGES]
    current_idx = stage_keys.index(candidate.current_stage) if candidate.current_stage in stage_keys else 0
    old_stage = candidate.stage_display

    if current_idx < len(stage_keys) - 1:
        candidate.current_stage = stage_keys[current_idx + 1]
        candidate.status = 'interviewing'
        db.session.flush()
        # System note
        note = CandidateNote(
            candidate_id=candidate_id,
            author_id=current_user.id,
            content=f'Advanced from {old_stage} to {candidate.stage_display}',
            note_type='system',
        )
        db.session.add(note)
        db.session.commit()
        flash(f'{candidate.user.name} advanced to {candidate.stage_display}.', 'success')
    else:
        candidate.status = 'hired'
        note = CandidateNote(
            candidate_id=candidate_id,
            author_id=current_user.id,
            content='Candidate hired!',
            note_type='system',
        )
        db.session.add(note)
        db.session.commit()
        flash(f'{candidate.user.name} has been hired!', 'success')

    return redirect(url_for('manager.candidate_detail', candidate_id=candidate_id))


@manager_bp.route('/candidate/<int:candidate_id>/reject', methods=['POST'])
@login_required
@manager_required
def reject_candidate(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    if not can_access_candidate(candidate):
        flash('Access denied.', 'error')
        return redirect(url_for('manager.dashboard'))
    candidate.status = 'rejected'
    note = CandidateNote(
        candidate_id=candidate_id,
        author_id=current_user.id,
        content=f'Candidate rejected at {candidate.stage_display} stage',
        note_type='system',
    )
    db.session.add(note)
    db.session.commit()
    flash(f'{candidate.user.name} has been marked as not advancing.', 'info')
    return redirect(url_for('manager.dashboard'))


@manager_bp.route('/candidate/<int:candidate_id>/scorecard', methods=['GET', 'POST'])
@login_required
@manager_required
def submit_scorecard(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    if not can_access_candidate(candidate):
        flash('Access denied.', 'error')
        return redirect(url_for('manager.dashboard'))

    if request.method == 'POST':
        scorecard = Scorecard(
            candidate_id=candidate_id,
            evaluator_id=current_user.id,
            stage=candidate.current_stage,
            communication=int(request.form.get('communication', 0)),
            experience=int(request.form.get('experience', 0)),
            niche_skills=int(request.form.get('niche_skills', 0)),
            thinking=int(request.form.get('thinking', 0)),
            emotional=int(request.form.get('emotional', 0)),
            leadership=int(request.form.get('leadership', 0)),
            recommendation=request.form.get('recommendation', 'neutral'),
            comments=request.form.get('comments', ''),
            is_bar_raiser='bar_raiser' in request.form,
            bar_raiser_veto='bar_raiser_veto' in request.form,
        )
        scorecard.calculate_total()
        db.session.add(scorecard)
        db.session.commit()
        flash('Scorecard submitted.', 'success')
        return redirect(url_for('manager.candidate_detail', candidate_id=candidate_id))

    return render_template('manager/scorecard_form.html',
                           candidate=candidate,
                           stages=PIPELINE_STAGES)


@manager_bp.route('/positions')
@login_required
@manager_required
def positions():
    if current_user.role == 'admin':
        positions = Position.query.all()
    else:
        positions = Position.query.filter_by(hiring_manager_id=current_user.id).all()
    return render_template('manager/positions.html', positions=positions)


# ── Interview Scheduling ─────────────────────────────────────────────────────

@manager_bp.route('/candidate/<int:candidate_id>/interview/create', methods=['GET', 'POST'])
@login_required
@manager_required
def create_interview(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    if not can_access_candidate(candidate):
        flash('Access denied.', 'error')
        return redirect(url_for('manager.dashboard'))

    if request.method == 'POST':
        scheduled_str = request.form.get('scheduled_at', '')
        scheduled_at = datetime.strptime(scheduled_str, '%Y-%m-%dT%H:%M') if scheduled_str else None

        interview = Interview(
            candidate_id=candidate_id,
            stage=request.form.get('stage', candidate.current_stage),
            interviewer_id=int(request.form.get('interviewer_id', 0)) or None,
            scheduled_at=scheduled_at,
            interview_type=request.form.get('interview_type', 'video'),
            notes=request.form.get('notes', '').strip() or None,
            status='scheduled',
        )
        db.session.add(interview)
        db.session.commit()
        flash('Interview scheduled.', 'success')
        return redirect(url_for('manager.candidate_detail', candidate_id=candidate_id))

    managers = User.query.filter(User.role.in_(['manager', 'admin'])).all()
    return render_template('manager/create_interview.html',
                           candidate=candidate, managers=managers, stages=PIPELINE_STAGES)


@manager_bp.route('/interview/<int:interview_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def edit_interview(interview_id):
    interview = Interview.query.get_or_404(interview_id)
    candidate = Candidate.query.get_or_404(interview.candidate_id)
    if not can_access_candidate(candidate):
        flash('Access denied.', 'error')
        return redirect(url_for('manager.dashboard'))

    if request.method == 'POST':
        scheduled_str = request.form.get('scheduled_at', '')
        interview.scheduled_at = datetime.strptime(scheduled_str, '%Y-%m-%dT%H:%M') if scheduled_str else None
        interview.stage = request.form.get('stage', interview.stage)
        interview.interviewer_id = int(request.form.get('interviewer_id', 0)) or None
        interview.interview_type = request.form.get('interview_type', 'video')
        interview.status = request.form.get('status', interview.status)
        interview.notes = request.form.get('notes', '').strip() or None
        db.session.commit()
        flash('Interview updated.', 'success')
        return redirect(url_for('manager.candidate_detail', candidate_id=candidate.id))

    managers = User.query.filter(User.role.in_(['manager', 'admin'])).all()
    return render_template('manager/edit_interview.html',
                           interview=interview, candidate=candidate,
                           managers=managers, stages=PIPELINE_STAGES)


@manager_bp.route('/interview/<int:interview_id>/cancel', methods=['POST'])
@login_required
@manager_required
def cancel_interview(interview_id):
    interview = Interview.query.get_or_404(interview_id)
    candidate = Candidate.query.get_or_404(interview.candidate_id)
    if not can_access_candidate(candidate):
        flash('Access denied.', 'error')
        return redirect(url_for('manager.dashboard'))

    interview.status = 'cancelled'
    db.session.commit()
    flash('Interview cancelled.', 'info')
    return redirect(url_for('manager.candidate_detail', candidate_id=candidate.id))


# ── Candidate Notes ──────────────────────────────────────────────────────────

@manager_bp.route('/candidate/<int:candidate_id>/note', methods=['POST'])
@login_required
@manager_required
def add_note(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    if not can_access_candidate(candidate):
        flash('Access denied.', 'error')
        return redirect(url_for('manager.dashboard'))

    content = request.form.get('content', '').strip()
    if content:
        note = CandidateNote(
            candidate_id=candidate_id,
            author_id=current_user.id,
            content=content,
            note_type='manual',
        )
        db.session.add(note)
        db.session.commit()
        flash('Note added.', 'success')

    return redirect(url_for('manager.candidate_detail', candidate_id=candidate_id))


# ── Manager Search ───────────────────────────────────────────────────────────

@manager_bp.route('/search')
@login_required
@manager_required
def search():
    q = request.args.get('q', '').strip()
    results = []

    if q:
        like = f'%{q}%'
        if current_user.role == 'admin':
            results = Candidate.query.join(User).join(Position).filter(
                db.or_(User.name.ilike(like), User.email.ilike(like), Position.title.ilike(like))
            ).limit(30).all()
        else:
            pos_ids = [p.id for p in Position.query.filter_by(hiring_manager_id=current_user.id).all()]
            if pos_ids:
                results = Candidate.query.join(User).join(Position).filter(
                    Candidate.position_id.in_(pos_ids),
                    db.or_(User.name.ilike(like), User.email.ilike(like), Position.title.ilike(like))
                ).limit(30).all()

    return render_template('manager/search.html', q=q, results=results)
