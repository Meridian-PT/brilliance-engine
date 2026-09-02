from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timezone
from app import db
from app.models import NewHire, OnboardingTask

newhire_bp = Blueprint('newhire', __name__, template_folder='../templates/newhire')


def newhire_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('newhire', 'admin'):
            flash('Access denied.', 'error')
            return redirect(url_for('auth.landing'))
        return f(*args, **kwargs)
    return decorated


@newhire_bp.route('/dashboard')
@login_required
@newhire_required
def dashboard():
    profile = NewHire.query.filter_by(user_id=current_user.id).first()
    if not profile and current_user.role == 'admin':
        # Admin viewing — show overview
        all_newhires = NewHire.query.all()
        return render_template('newhire/dashboard.html', profile=None, all_newhires=all_newhires)
    return render_template('newhire/dashboard.html', profile=profile)


@newhire_bp.route('/task/<int:task_id>/toggle', methods=['POST'])
@login_required
@newhire_required
def toggle_task(task_id):
    task = OnboardingTask.query.get_or_404(task_id)
    # Verify ownership
    if task.new_hire.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    task.completed = not task.completed
    task.completed_at = datetime.now(timezone.utc) if task.completed else None
    db.session.commit()

    return jsonify({
        'completed': task.completed,
        'progress': task.new_hire.progress_pct,
    })
