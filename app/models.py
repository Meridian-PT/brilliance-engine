from datetime import datetime, date, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # candidate, newhire, employee, manager, admin
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


class FileAttachment(db.Model):
    __tablename__ = 'file_attachments'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100))
    file_size = db.Column(db.Integer)
    file_data = db.Column(db.LargeBinary, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    attachment_type = db.Column(db.String(50))  # resume, cover_letter, document
    attachment_id = db.Column(db.Integer)  # FK to candidate_id or document_id
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    uploader = db.relationship('User', foreign_keys=[uploaded_by])

    def __repr__(self):
        return f'<FileAttachment {self.original_filename}>'


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
    def resume(self):
        return FileAttachment.query.filter_by(
            attachment_type='resume', attachment_id=self.id
        ).order_by(FileAttachment.uploaded_at.desc()).first()

    @property
    def cover_letter_file(self):
        return FileAttachment.query.filter_by(
            attachment_type='cover_letter', attachment_id=self.id
        ).order_by(FileAttachment.uploaded_at.desc()).first()

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


class CandidateNote(db.Model):
    __tablename__ = 'candidate_notes'

    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidates.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    content = db.Column(db.Text, nullable=False)
    note_type = db.Column(db.String(20), default='manual')  # manual, system
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    candidate = db.relationship('Candidate', backref=db.backref('candidate_notes', lazy='dynamic',
                                order_by='CandidateNote.created_at.desc()'))
    author = db.relationship('User', foreign_keys=[author_id])

    def __repr__(self):
        return f'<CandidateNote {self.id} for candidate {self.candidate_id}>'


# ── Employee Portal ──────────────────────────────────────────────────────────

class EmployeeProfile(db.Model):
    __tablename__ = 'employee_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    department = db.Column(db.String(100))
    title = db.Column(db.String(150))
    start_date = db.Column(db.Date)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    employee_number = db.Column(db.String(20))
    phone = db.Column(db.String(30))
    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_phone = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Phase 2: System-of-Record fields ──
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    province_state = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100))
    date_of_birth = db.Column(db.Date)
    employment_status = db.Column(db.String(20), default='active')  # active, on_leave, terminated, suspended
    employment_type = db.Column(db.String(20))  # full_time, part_time, contract, intern
    termination_date = db.Column(db.Date)
    termination_reason = db.Column(db.Text)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('employee_profile', uselist=False))
    manager = db.relationship('User', foreign_keys=[manager_id])

    def __repr__(self):
        return f'<EmployeeProfile {self.user_id}>'


class Policy(db.Model):
    __tablename__ = 'policies'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))  # handbook, compliance, safety, it
    content = db.Column(db.Text, nullable=False)
    version = db.Column(db.String(20), default='1.0')
    effective_date = db.Column(db.Date)
    requires_acknowledgment = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    acknowledgments = db.relationship('PolicyAcknowledgment', backref='policy', lazy='dynamic')

    def __repr__(self):
        return f'<Policy {self.title}>'


class PolicyAcknowledgment(db.Model):
    __tablename__ = 'policy_acknowledgments'

    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey('policies.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    acknowledged_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<PolicyAck policy={self.policy_id} user={self.user_id}>'


class ContentAccessLog(db.Model):
    __tablename__ = 'content_access_logs'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    accessed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    document = db.relationship('Document', foreign_keys=[document_id])
    user = db.relationship('User', foreign_keys=[user_id])


class AssessmentTemplate(db.Model):
    __tablename__ = 'assessment_templates'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # competency, personality, skills, compliance
    questions = db.Column(db.Text)  # JSON string
    time_limit_minutes = db.Column(db.Integer, default=30)
    passing_score = db.Column(db.Integer, default=70)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    results = db.relationship('AssessmentResult', backref='template', lazy='dynamic')

    def __repr__(self):
        return f'<AssessmentTemplate {self.title}>'

    def get_questions(self):
        import json
        return json.loads(self.questions) if self.questions else []


class AssessmentResult(db.Model):
    __tablename__ = 'assessment_results'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('assessment_templates.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    answers = db.Column(db.Text)  # JSON string
    score = db.Column(db.Float)
    passed = db.Column(db.Boolean)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    attempt_number = db.Column(db.Integer, default=1)

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<AssessmentResult template={self.template_id} user={self.user_id} score={self.score}>'


class TrainingCourse(db.Model):
    __tablename__ = 'training_courses'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # onboarding, compliance, skills, leadership
    estimated_hours = db.Column(db.Float, default=1.0)
    is_required = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    modules = db.relationship('TrainingModule', backref='course', lazy='dynamic',
                              order_by='TrainingModule.order')
    completions = db.relationship('TrainingCompletion', backref='course', lazy='dynamic')

    def __repr__(self):
        return f'<TrainingCourse {self.title}>'

    @property
    def modules_count(self):
        return self.modules.count()

    def user_progress(self, user_id):
        total = self.modules.count()
        if total == 0:
            return 0
        done = TrainingCompletion.query.filter_by(
            course_id=self.id, user_id=user_id
        ).filter(TrainingCompletion.module_id.isnot(None)).count()
        return int(done / total * 100)


class TrainingModule(db.Model):
    __tablename__ = 'training_modules'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('training_courses.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    order = db.Column(db.Integer, default=0)
    content_type = db.Column(db.String(30))  # text, video, interactive, quiz
    content = db.Column(db.Text)  # HTML content
    duration_minutes = db.Column(db.Integer, default=15)

    def __repr__(self):
        return f'<TrainingModule {self.title}>'


class TrainingCompletion(db.Model):
    __tablename__ = 'training_completions'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('training_courses.id'), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey('training_modules.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    completed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    score = db.Column(db.Float)

    user = db.relationship('User', foreign_keys=[user_id])
    module = db.relationship('TrainingModule', foreign_keys=[module_id])


class PTOBalance(db.Model):
    __tablename__ = 'pto_balances'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    vacation_total = db.Column(db.Float, default=15)
    vacation_used = db.Column(db.Float, default=0)
    sick_total = db.Column(db.Float, default=10)
    sick_used = db.Column(db.Float, default=0)
    personal_total = db.Column(db.Float, default=3)
    personal_used = db.Column(db.Float, default=0)

    user = db.relationship('User', foreign_keys=[user_id])

    @property
    def vacation_remaining(self):
        return self.vacation_total - self.vacation_used

    @property
    def sick_remaining(self):
        return self.sick_total - self.sick_used

    @property
    def personal_remaining(self):
        return self.personal_total - self.personal_used

    @property
    def total_remaining(self):
        return self.vacation_remaining + self.sick_remaining + self.personal_remaining


class PTORequest(db.Model):
    __tablename__ = 'pto_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type = db.Column(db.String(30))  # vacation, sick, personal, bereavement, other
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    days_requested = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, approved, denied
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', foreign_keys=[user_id])
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def __repr__(self):
        return f'<PTORequest {self.leave_type} {self.start_date} - {self.end_date}>'


class ReviewCycle(db.Model):
    __tablename__ = 'review_cycles'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    cycle_type = db.Column(db.String(30))  # annual, mid_year, quarterly
    status = db.Column(db.String(20), default='active')  # draft, active, closed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    reviews = db.relationship('PerformanceReview', backref='cycle', lazy='dynamic')

    def __repr__(self):
        return f'<ReviewCycle {self.title}>'


class PerformanceReview(db.Model):
    __tablename__ = 'performance_reviews'

    id = db.Column(db.Integer, primary_key=True)
    cycle_id = db.Column(db.Integer, db.ForeignKey('review_cycles.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    self_rating = db.Column(db.Integer)  # 1-5
    self_comments = db.Column(db.Text)
    manager_rating = db.Column(db.Integer)  # 1-5
    manager_comments = db.Column(db.Text)
    goals_next_period = db.Column(db.Text)
    status = db.Column(db.String(30), default='pending_self')  # pending_self, pending_manager, complete
    submitted_at = db.Column(db.DateTime)

    employee = db.relationship('User', foreign_keys=[employee_id])
    reviewer = db.relationship('User', foreign_keys=[reviewer_id])


# ── Compensation (Phase 2 — SENSITIVE, access-gated) ──────────────────────────

class CompensationRecord(db.Model):
    """Base salary history. Admin-only write; employee read-only on own current record."""
    __tablename__ = 'compensation_records'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    base_salary = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(10), default='CAD')
    pay_frequency = db.Column(db.String(20))  # annual, monthly, bi_weekly, weekly, hourly
    effective_date = db.Column(db.Date, nullable=False)
    change_reason = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', foreign_keys=[user_id])
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<CompensationRecord user={self.user_id} {self.base_salary} {self.currency} eff={self.effective_date}>'


class BonusRecord(db.Model):
    """Bonus/award history. Admin-only write; employee read-only on own records."""
    __tablename__ = 'bonus_records'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(10), default='CAD')
    bonus_type = db.Column(db.String(50))  # performance, signing, retention, spot, referral, other
    award_date = db.Column(db.Date, nullable=False)
    note = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', foreign_keys=[user_id])
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<BonusRecord user={self.user_id} {self.amount} {self.currency} type={self.bonus_type}>'


class SalaryBand(db.Model):
    """Admin-only reference table for compensation benchmarking by level/department."""
    __tablename__ = 'salary_bands'

    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(50), nullable=False)
    department = db.Column(db.String(100))
    currency = db.Column(db.String(10), default='CAD')
    salary_min = db.Column(db.Numeric(12, 2))
    salary_mid = db.Column(db.Numeric(12, 2))
    salary_max = db.Column(db.Numeric(12, 2))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<SalaryBand {self.level} / {self.department}>'


# ── Audit Trail (Phase 2) ─────────────────────────────────────────────────────

class AuditLog(db.Model):
    """Immutable log of sensitive changes (compensation, employment status, roles)."""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50), nullable=False)  # create, update, delete
    entity_type = db.Column(db.String(50), nullable=False)  # CompensationRecord, BonusRecord, EmployeeProfile, User
    entity_id = db.Column(db.Integer)
    field_name = db.Column(db.String(100))
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    actor = db.relationship('User', foreign_keys=[actor_id])

    def __repr__(self):
        return f'<AuditLog {self.action} {self.entity_type}#{self.entity_id}.{self.field_name}>'


# ── Benefits Administration (Phase 3) ─────────────────────────────────────────

class BenefitPlan(db.Model):
    """Admin-managed benefit plan offering (health, dental, vision, life, RRSP, etc)."""
    __tablename__ = 'benefit_plans'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    plan_type = db.Column(db.String(30), nullable=False)  # health, dental, vision, life, rrsp, other
    provider = db.Column(db.String(150))
    tier = db.Column(db.String(50))  # e.g. Standard, Premium, Executive
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    enrollments = db.relationship('BenefitEnrollment', backref='plan', lazy='dynamic')

    def __repr__(self):
        return f'<BenefitPlan {self.name} ({self.plan_type})>'


class BenefitEnrollment(db.Model):
    """An employee's enrollment in a benefit plan."""
    __tablename__ = 'benefit_enrollments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('benefit_plans.id'), nullable=False)
    coverage_level = db.Column(db.String(30), default='employee')  # employee, employee_spouse, family
    dependents_count = db.Column(db.Integer, default=0)
    effective_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='active')  # active, pending, ended
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<BenefitEnrollment user={self.user_id} plan={self.plan_id} status={self.status}>'


class OpenEnrollmentWindow(db.Model):
    """A named period during which employees may enroll in / change benefits."""
    __tablename__ = 'open_enrollment_windows'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def is_open_now(self):
        today = date.today()
        return bool(self.is_active and self.start_date <= today <= self.end_date)

    def __repr__(self):
        return f'<OpenEnrollmentWindow {self.name} {self.start_date} - {self.end_date}>'


def get_open_enrollment_window():
    """Return the first currently-open OpenEnrollmentWindow, or None if enrollment is closed."""
    today = date.today()
    return OpenEnrollmentWindow.query.filter(
        OpenEnrollmentWindow.is_active == True,
        OpenEnrollmentWindow.start_date <= today,
        OpenEnrollmentWindow.end_date >= today,
    ).first()


# ── Leave Management — Accrual Policies (Phase 3) ─────────────────────────────

class AccrualPolicy(db.Model):
    """Admin-defined accrual rule for a leave type (e.g. 1.25 vacation days/month)."""
    __tablename__ = 'accrual_policies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    leave_type = db.Column(db.String(30), nullable=False)  # vacation, sick, personal
    rate_per_period = db.Column(db.Float, nullable=False)
    period = db.Column(db.String(20), default='monthly')  # monthly, per_pay, annual
    annual_cap = db.Column(db.Float)
    carryover_max = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<AccrualPolicy {self.name} {self.rate_per_period}/{self.period}>'


# Leave types that are statutory/categorical rather than drawn from the standard
# vacation/sick/personal PTOBalance pools. PTORequest.leave_type already accepts
# any string (see models.py PTORequest comment), so no schema change is needed —
# these are simply additional accepted values with no balance cap, surfaced in
# the employee request form and left alone by any balance-deduction logic.
STATUTORY_LEAVE_TYPES = ['bereavement', 'parental', 'jury_duty']


# ── Company Announcements (Phase 3) ───────────────────────────────────────────

class Announcement(db.Model):
    """Company news item shown on employee/manager/admin dashboards."""
    __tablename__ = 'announcements'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    audience = db.Column(db.String(100), default='all')  # 'all' or a department value
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    published_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime)
    is_pinned = db.Column(db.Boolean, default=False)

    author = db.relationship('User', foreign_keys=[author_id])

    @property
    def is_active_now(self):
        # SQLite's DateTime columns round-trip as timezone-naive, but
        # `default=` on this model (like every other model in this app)
        # produces a timezone-aware value at creation time, before the first
        # flush/commit. Normalize both sides to naive UTC before comparing
        # so this works whether the instance is freshly-created-in-session
        # or freshly-queried-from-the-database.
        now = _naive_utc(datetime.now(timezone.utc))
        published = _naive_utc(self.published_at)
        expires = _naive_utc(self.expires_at)
        if published and published > now:
            return False
        if expires and expires < now:
            return False
        return True

    def __repr__(self):
        return f'<Announcement {self.title} audience={self.audience}>'


def _naive_utc(dt):
    """Strip tzinfo from an aware datetime (converting to UTC first), or
    pass through a naive datetime / None unchanged. See Announcement.is_active_now."""
    if dt is not None and dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def get_active_announcements_for(user, limit=5):
    """Active (published, not expired) announcements visible to this user,
    matching audience 'all' or the user's EmployeeProfile department. Pinned
    items are returned first."""
    now = _naive_utc(datetime.now(timezone.utc))
    department = None
    profile = EmployeeProfile.query.filter_by(user_id=user.id).first()
    if profile:
        department = profile.department

    audiences = ['all']
    if department:
        audiences.append(department)

    query = Announcement.query.filter(
        db.or_(Announcement.published_at.is_(None), Announcement.published_at <= now),
        db.or_(Announcement.expires_at.is_(None), Announcement.expires_at >= now),
        Announcement.audience.in_(audiences),
    )
    return query.order_by(Announcement.is_pinned.desc(),
                           Announcement.published_at.desc()).limit(limit).all()
