import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Candidate, Position, FileAttachment, PIPELINE_STAGES

candidate_bp = Blueprint('candidate', __name__, template_folder='../templates/candidate')


def candidate_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('candidate', 'admin'):
            flash('Access denied.', 'error')
            return redirect(url_for('auth.landing'))
        return f(*args, **kwargs)
    return decorated


@candidate_bp.route('/dashboard')
@login_required
@candidate_required
def dashboard():
    applications = Candidate.query.filter_by(user_id=current_user.id).all()
    open_positions = Position.query.filter_by(status='open').all()
    return render_template('candidate/dashboard.html',
                           applications=applications,
                           open_positions=open_positions,
                           stages=PIPELINE_STAGES)


@candidate_bp.route('/apply/<int:position_id>', methods=['GET', 'POST'])
@login_required
@candidate_required
def apply(position_id):
    position = Position.query.get_or_404(position_id)
    existing = Candidate.query.filter_by(user_id=current_user.id, position_id=position_id).first()
    if existing:
        flash('You have already applied for this position.', 'warning')
        return redirect(url_for('candidate.dashboard'))

    if request.method == 'GET':
        return render_template('candidate/apply.html', position=position)

    cover_letter = request.form.get('cover_letter', '').strip()
    candidate = Candidate(
        user_id=current_user.id,
        position_id=position_id,
        cover_letter=cover_letter or None,
        source='website',
    )
    db.session.add(candidate)
    db.session.flush()

    resume = request.files.get('resume')
    if resume and resume.filename:
        ext = resume.filename.rsplit('.', 1)[-1].lower() if '.' in resume.filename else ''
        stored_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
        attachment = FileAttachment(
            filename=stored_name,
            original_filename=resume.filename,
            mime_type=resume.content_type,
            file_size=0,
            file_data=resume.read(),
            uploaded_by=current_user.id,
            attachment_type='resume',
            attachment_id=candidate.id,
        )
        attachment.file_size = len(attachment.file_data)
        db.session.add(attachment)

    db.session.commit()
    flash(f'Application submitted for {position.title}!', 'success')
    return redirect(url_for('candidate.dashboard'))


@candidate_bp.route('/culture')
@login_required
@candidate_required
def culture():
    return render_template('candidate/culture.html')


@candidate_bp.route('/application/<int:app_id>')
@login_required
@candidate_required
def application_detail(app_id):
    application = Candidate.query.get_or_404(app_id)
    if application.user_id != current_user.id and current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('candidate.dashboard'))
    return render_template('candidate/application_detail.html',
                           application=application,
                           stages=PIPELINE_STAGES)
