from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # candidate, newhire, manager, admin
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active_user = db.Column(db.Boolean, default=True)

    # Relationships
    candidate_profile = db.relationship('Candidate', backref='user', uselist=False,
                                        foreign_keys='Candidate.user_id')
    newhire_profile = db.relationship('NewHire', backref='user', uselist=False,
                                      foreign_keys='NewHire.user_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.is_active_user

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'


# ── Pipeline Stages ──────────────────────────────────────────────────────────
PIPELINE_STAGES = [
    ('screening', 'Screening'),
    ('criteria_gathering', 'Criteria Gathering'),
    ('who_interview', 'The Who Interview'),
    ('role_specific', 'Role-Specific Interview'),
    ('final_screen', 'Final Screen'),
    ('references_bar_raiser', 'References & Bar Raiser'),
    ('offer_onboarding', 'Offer & Onboarding'),
]


class Position(db.Model):
    __tablename__ = 'positions'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100))
    location = db.Column(db.String(100))
    employment_type = db.Column(db.String(50), default='Full-Time')  # Full-Time, Part-Time, Contract, Intern
    description = db.Column(db.Text)
    requirements = db.Column(db.Text)
    salary_range_low = db.Column(db.Integer)
    salary_range_high = db.Column(db.Integer)
    status = db.Column(db.String(20), default='open')  # open, paused, closed, filled
    hiring_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    hiring_manager = db.relationship('User', foreign_keys=[hiring_manager_id])
    candidates = db.relationship('Candidate', backref='position', lazy='dynamic')

    def __repr__(self):
        return f'<Position {self.title}>'

    @property
    def active_candidates(self):
        return self.candidates.filter(Candidate.status.in_(['active', 'interviewing'])).count()


class Candidate(db.Model):
    __tablename__ = 'candidates'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'), nullable=False)
    current_stage = db.Column(db.String(30), default='screening')
    status = db.Column(db.String(20), default='active')  # active, interviewing, offered, hired, rejected, withdrawn
    applied_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    resume_path = db.Column(db.String(300))
    cover_letter = db.Column(db.Text)
    notes = db.Column(db.Text)
    source = db.Column(db.String(50))  # website, referral, linkedin, indeed, etc.

    interviews = db.relationship('Interview', backref='candidate', lazy='dynamic',
                                 order_by='Interview.scheduled_at')
    scorecards = db.relationship('Scorecard', backref='candidate', lazy='dynamic')

    def __repr__(self):
        return f'<Candidate {self.user.name} for {self.position.title}>'

    @property
    def stage_display(self):
        return dict(PIPELINE_STAGES).get(self.current_stage, self.current_stage)

    @property
    def stage_index(self):
        stages = [s[0] for s in PIPELINE_STAGES]
        return stages.index(self.current_stage) if self.current_stage in stages else 0

    @property
    def stage_progress(self):
        return int((self.stage_index + 1) / len(PIPELINE_STAGES) * 100)


class Interview(db.Model):
    __tablename__ = 'interviews'

    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidates.id'), nullable=False)
    stage = db.Column(db.String(30), nullable=False)
    interviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    scheduled_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, completed, cancelled, no_show
    interview_type = db.Column(db.String(30))  # phone, video, in_person, panel
    notes = db.Column(db.Text)

    interviewer = db.relationship('User', foreign_keys=[interviewer_id])

    def __repr__(self):
        return f'<Interview {self.stage} for candidate {self.candidate_id}>'


class Scorecard(db.Model):
    __tablename__ = 'scorecards'

    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidates.id'), nullable=False)
    interview_id = db.Column(db.Integer, db.ForeignKey('interviews.id'))
    evaluator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stage = db.Column(db.String(30), nullable=False)

    # Six scoring dimensions (1-5 scale, from PT's Applicant Grading System)
    communication = db.Column(db.Integer)
    experience = db.Column(db.Integer)
    niche_skills = db.Column(db.Integer)
    thinking = db.Column(db.Integer)
    emotional = db.Column(db.Integer)
    leadership = db.Column(db.Integer)

    total_score = db.Column(db.Float)
    recommendation = db.Column(db.String(20))  # strong_yes, yes, neutral, no, strong_no
    comments = db.Column(db.Text)
    is_bar_raiser = db.Column(db.Boolean, default=False)
    bar_raiser_veto = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    evaluator = db.relationship('User', foreign_keys=[evaluator_id])
    interview = db.relationship('Interview', foreign_keys=[interview_id])

    def calculate_total(self):
        scores = [s for s in [self.communication, self.experience, self.niche_skills,
                               self.thinking, self.emotional, self.leadership] if s is not None]
        self.total_score = sum(scores) / len(scores) if scores else 0
        return self.total_score

    def __repr__(self):
        return f'<Scorecard {self.stage} by {self.evaluator_id}>'


# ── Onboarding ───────────────────────────────────────────────────────────────

class NewHire(db.Model):
    __tablename__ = 'new_hires'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey('positions.id'))
    start_date = db.Column(db.Date)
    buddy_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    department = db.Column(db.String(100))
    onboarding_status = db.Column(db.String(20), default='pre_start')  # pre_start, week_1, day_30, day_60, day_90, complete
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    buddy = db.relationship('User', foreign_keys=[buddy_id])
    manager = db.relationship('User', foreign_keys=[manager_id])
    position = db.relationship('Position', foreign_keys=[position_id])
    tasks = db.relationship('OnboardingTask', backref='new_hire', lazy='dynamic',
                            order_by='OnboardingTask.due_day')

    @property
    def progress_pct(self):
        total = self.tasks.count()
        if total == 0:
            return 0
        done = self.tasks.filter_by(completed=True).count()
        return int(done / total * 100)

    @property
    def tasks_due_today(self):
        if not self.start_date:
            return []
        from datetime import date
        days_since_start = (date.today() - self.start_date).days
        return self.tasks.filter(
            OnboardingTask.due_day <= days_since_start,
            OnboardingTask.completed == False
        ).all()


class OnboardingTask(db.Model):
    __tablename__ = 'onboarding_tasks'

    id = db.Column(db.Integer, primary_key=True)
    new_hire_id = db.Column(db.Integer, db.ForeignKey('new_hires.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # pre_start, day_1, week_1, day_30, day_60, day_90
    due_day = db.Column(db.Integer, default=0)  # days after start_date
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    assigned_to = db.Column(db.String(20))  # newhire, manager, hr, buddy, it

    def __repr__(self):
        return f'<OnboardingTask {self.title}>'


# ── Knowledge Base ────────────────────────────────────────────────────────────

class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # hiring, culture, onboarding, legal, performance, assessment
    module = db.Column(db.String(50))  # pipeline, scorecard, interview, assessment, onboarding, knowledge
    file_path = db.Column(db.String(300))
    file_type = db.Column(db.String(10))  # docx, pdf, xlsx, pptx
    origin = db.Column(db.String(20))  # ancestral, meridian, sharepoint
    date_created = db.Column(db.String(20))
    is_template = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Document {self.title}>'
