from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Candidate, Position, Interview, Scorecard, PIPELINE_STAGES, NewHire

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
    scorecards = Scorecard.query.filter_by(candidate_id=candidate_id).all()
    interviews = Interview.query.filter_by(candidate_id=candidate_id).order_by(Interview.scheduled_at).all()
    return render_template('manager/candidate_detail.html',
                           candidate=candidate,
                           scorecards=scorecards,
                           interviews=interviews,
                           stages=PIPELINE_STAGES)


@manager_bp.route('/candidate/<int:candidate_id>/advance', methods=['POST'])
@login_required
@manager_required
def advance_candidate(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    stage_keys = [s[0] for s in PIPELINE_STAGES]
    current_idx = stage_keys.index(candidate.current_stage) if candidate.current_stage in stage_keys else 0

    if current_idx < len(stage_keys) - 1:
        candidate.current_stage = stage_keys[current_idx + 1]
        candidate.status = 'interviewing'
        db.session.commit()
        flash(f'{candidate.user.name} advanced to {candidate.stage_display}.', 'success')
    else:
        candidate.status = 'hired'
        db.session.commit()
        flash(f'{candidate.user.name} has been hired!', 'success')

    return redirect(url_for('manager.candidate_detail', candidate_id=candidate_id))


@manager_bp.route('/candidate/<int:candidate_id>/reject', methods=['POST'])
@login_required
@manager_required
def reject_candidate(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    candidate.status = 'rejected'
    db.session.commit()
    flash(f'{candidate.user.name} has been marked as not advancing.', 'info')
    return redirect(url_for('manager.dashboard'))


@manager_bp.route('/candidate/<int:candidate_id>/scorecard', methods=['GET', 'POST'])
@login_required
@manager_required
def submit_scorecard(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)

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
