#!/usr/bin/env python3
"""Brilliance Engine — Pure Technology's HR Operating System."""

import os
import sys
from datetime import date, datetime, timezone

# Ensure instance directory exists for SQLite
os.makedirs(os.path.join(os.path.dirname(__file__), 'instance'), exist_ok=True)

from app import create_app, db
from app.models import (User, Position, Candidate, Document, NewHire, OnboardingTask,
                         FileAttachment, CandidateNote, EmployeeProfile, Policy,
                         AssessmentTemplate, TrainingCourse, TrainingModule,
                         PTOBalance, PTORequest, ReviewCycle, PerformanceReview)
import json


app = create_app(os.environ.get('FLASK_CONFIG', 'default'))


def seed_database():
    """Seed with demo data if database is empty."""
    if User.query.first():
        return  # Already seeded

    print("Seeding database...")

    # ── Admin Users ──
    admin = User(name='Mike Daser', email='mike@puretechnology.nyc', role='admin')
    admin.set_password('brilliance2026')
    db.session.add(admin)

    meridian = User(name='Meridian', email='meridian@puretechnology.nyc', role='admin')
    meridian.set_password('brilliance2026')
    db.session.add(meridian)

    # ── Hiring Managers ──
    jared = User(name='Jared Sanborn', email='jared@puretechnology.nyc', role='manager')
    jared.set_password('brilliance2026')
    db.session.add(jared)

    mireille = User(name='Mireille Dirary', email='mireille@puretechnology.nyc', role='manager')
    mireille.set_password('brilliance2026')
    db.session.add(mireille)

    db.session.flush()

    # ── Open Positions ──
    positions = [
        Position(
            title='Senior Software Engineer',
            department='Engineering',
            location='Toronto, ON (Hybrid)',
            employment_type='Full-Time',
            description='Build and scale PT\'s core technology platform. Work with cutting-edge AI/ML systems and data infrastructure.',
            requirements='5+ years experience, Python/TypeScript, cloud infrastructure, passion for innovation.',
            salary_range_low=120000, salary_range_high=160000,
            hiring_manager_id=jared.id,
            status='open',
        ),
        Position(
            title='HR Coordinator',
            department='Human Resources',
            location='Toronto, ON',
            employment_type='Full-Time',
            description='Support the HR function with hiring coordination, onboarding, and employee experience. Work directly with the SVP HR.',
            requirements='2+ years HR experience, excellent communication, detail-oriented, HRIS experience.',
            salary_range_low=55000, salary_range_high=70000,
            hiring_manager_id=admin.id,
            status='open',
        ),
        Position(
            title='Data Analyst',
            department='Analytics',
            location='Remote (Canada)',
            employment_type='Full-Time',
            description='Transform raw data into actionable insights. Support business decisions across all departments.',
            requirements='SQL, Python, visualization tools (Tableau/PowerBI), analytical mindset.',
            salary_range_low=75000, salary_range_high=95000,
            hiring_manager_id=jared.id,
            status='open',
        ),
        Position(
            title='Marketing Intern',
            department='Marketing',
            location='Toronto, ON',
            employment_type='Intern',
            description='Join our marketing team for a 4-month internship. Learn content creation, social media, and campaign management.',
            hiring_manager_id=mireille.id,
            status='open',
        ),
    ]
    for p in positions:
        db.session.add(p)

    db.session.flush()

    # ── Sample Candidates ──
    candidates_data = [
        ('Sarah Chen', 'sarah.chen@example.com', positions[0].id, 'role_specific', 'linkedin'),
        ('Marcus Johnson', 'marcus.j@example.com', positions[0].id, 'who_interview', 'referral'),
        ('Priya Patel', 'priya.p@example.com', positions[1].id, 'screening', 'website'),
        ('James Wilson', 'james.w@example.com', positions[1].id, 'final_screen', 'indeed'),
        ('Aisha Rahman', 'aisha.r@example.com', positions[2].id, 'criteria_gathering', 'linkedin'),
        ('David Kim', 'david.kim@example.com', positions[2].id, 'references_bar_raiser', 'referral'),
        ('Emma Thompson', 'emma.t@example.com', positions[3].id, 'screening', 'website'),
        ('Carlos Mendez', 'carlos.m@example.com', positions[0].id, 'screening', 'linkedin'),
    ]

    for name, email, pos_id, stage, source in candidates_data:
        user = User(name=name, email=email, role='candidate')
        user.set_password('candidate2026')
        db.session.add(user)
        db.session.flush()

        candidate = Candidate(
            user_id=user.id,
            position_id=pos_id,
            current_stage=stage,
            status='active' if stage == 'screening' else 'interviewing',
            source=source,
        )
        db.session.add(candidate)

    # ── Sample Documents (from PT inventory) ──
    docs = [
        ('Interview Process Master Sheet', 'hiring', 'pipeline', 'docx', 'ancestral', True, 'Complete 68-step hiring process guide'),
        ('Pure Method 2.0 — Hiring', 'hiring', 'pipeline', 'docx', 'meridian', True, '6-stage modern hiring pipeline'),
        ('Applicant Grading System', 'hiring', 'scorecard', 'xlsx', 'ancestral', True, '6-dimension scoring rubric (1-5 scale)'),
        ('Bar Raiser Interview Guide', 'hiring', 'interview', 'docx', 'ancestral', True, 'Amazon-style Bar Raiser with absolute veto'),
        ('Role-Specific Interview Guide', 'hiring', 'interview', 'docx', 'ancestral', True, 'Step 2 interview template'),
        ('The Who Interview Guide', 'hiring', 'interview', 'docx', 'ancestral', True, 'Deep-dive background interview'),
        ('Screening Interview — Initial Phone Contact', 'hiring', 'interview', 'docx', 'ancestral', True, 'First phone screen template'),
        ('Peer Review Format', 'hiring', 'interview', 'docx', 'ancestral', True, 'Peer interview with 1-10 scoring'),
        ('Onboarding Playbook v1', 'onboarding', 'onboarding', 'docx', 'ancestral', True, 'Full employee onboarding playbook'),
        ('Pure Start Onboarding Guide', 'onboarding', 'onboarding', 'docx', 'meridian', True, 'Modern onboarding system'),
        ('Pure Start 30/60/90 Day Plan', 'onboarding', 'onboarding', 'docx', 'meridian', True, '30/60/90 day milestone tracker'),
        ('Pure Start Culture Card', 'onboarding', 'onboarding', 'docx', 'meridian', True, 'Day 1 culture orientation card'),
        ('Employee Handbook 2025', 'compliance', 'knowledge', 'pdf', 'ancestral', False, 'PT Employee Handbook'),
        ('Company Culture Document', 'culture', 'knowledge', 'docx', 'ancestral', False, 'PT culture and values'),
        ('Identity Statement', 'culture', 'knowledge', 'docx', 'ancestral', False, 'PT identity and positioning'),
        ('Actualizing Brilliance', 'culture', 'knowledge', 'docx', 'ancestral', False, 'Core PT philosophy'),
        ('Pure Systems Mindset', 'culture', 'knowledge', 'docx', 'ancestral', False, 'Systems-first thinking framework'),
        ('Decision Making Guidelines', 'culture', 'knowledge', 'docx', 'ancestral', False, 'How PT makes decisions'),
        ('The Apple Experience', 'onboarding', 'onboarding', 'docx', 'ancestral', False, 'Apple-inspired onboarding philosophy'),
        ('Offer Letter Template', 'legal', 'knowledge', 'docx', 'ancestral', True, 'Standard offer letter'),
        ('Mutual NDA Template', 'legal', 'knowledge', 'docx', 'meridian', True, 'PureLegal mutual NDA'),
        ('Confidentiality/IP Agreement', 'legal', 'knowledge', 'docx', 'meridian', True, 'PureLegal IP agreement'),
        ('Performance Management Framework', 'performance', 'knowledge', 'docx', 'meridian', False, 'Performance review system'),
        ('Learning & Development Framework', 'performance', 'knowledge', 'docx', 'meridian', False, 'L&D program structure'),
        ('DISC Assessment Tool', 'assessment', 'assessment', 'html', 'ancestral', True, 'DISC personality assessment'),
        ('Big Five Assessment Tool', 'assessment', 'assessment', 'html', 'ancestral', True, 'Big Five personality assessment'),
        ('Personality Test Guide', 'assessment', 'assessment', 'docx', 'ancestral', True, 'Personality assessment framework'),
        ('Background Check Authorization', 'compliance', 'knowledge', 'docx', 'ancestral', True, 'Background check form'),
        ('Vision/Mission Word Map', 'culture', 'knowledge', 'pptx', 'ancestral', False, 'Visual vision/mission presentation'),
        ('Brand Identity & Usage Guidelines', 'culture', 'knowledge', 'docx', 'ancestral', False, 'PT brand guidelines'),
    ]

    for title, category, module, file_type, origin, is_template, desc in docs:
        doc = Document(
            title=title, category=category, module=module,
            file_type=file_type, origin=origin, is_template=is_template,
            description=desc,
        )
        db.session.add(doc)

    # ── Demo New Hire (to showcase onboarding portal) ──
    newhire_user = User(name='Alex Rivera', email='alex.rivera@puretechnology.nyc', role='newhire')
    newhire_user.set_password('brilliance2026')
    db.session.add(newhire_user)
    db.session.flush()

    newhire = NewHire(
        user_id=newhire_user.id,
        position_id=positions[0].id,
        start_date=date.today(),
        buddy_id=mireille.id,
        manager_id=jared.id,
        department='Engineering',
        onboarding_status='week_1',
    )
    db.session.add(newhire)
    db.session.commit()

    # Create onboarding tasks for demo new hire
    _seed_onboarding_tasks(newhire.id)

    # ── Employee Portal Seed Data ──
    _seed_employee_data(jared, mireille, admin, positions)

    db.session.commit()
    print(f"Seeded: {User.query.count()} users, {Position.query.count()} positions, "
          f"{Candidate.query.count()} candidates, {Document.query.count()} documents, "
          f"employee portal with policies, assessments, training, PTO, and reviews")


def _seed_onboarding_tasks(new_hire_id):
    """Create Pure Start onboarding tasks for demo new hire."""
    tasks = [
        ('Sign offer letter and employment agreement', 'pre_start', -5, 'newhire'),
        ('Complete background check authorization', 'pre_start', -5, 'newhire'),
        ('Set up IT accounts (email, Slack, tools)', 'pre_start', -2, 'it'),
        ('Prepare welcome package and swag', 'pre_start', -1, 'hr'),
        ('Assign onboarding buddy', 'pre_start', -1, 'hr'),
        ('Welcome meeting with manager', 'day_1', 0, 'manager'),
        ('Read the Culture Card', 'day_1', 0, 'newhire'),
        ('Watch the Welcome Video', 'day_1', 0, 'newhire'),
        ('Meet your onboarding buddy', 'day_1', 0, 'buddy'),
        ('Complete IT setup and tool access', 'day_1', 0, 'newhire'),
        ('Read the Employee Handbook', 'day_1', 0, 'newhire'),
        ('Team introductions (all departments)', 'week_1', 3, 'manager'),
        ('Review role expectations and KPIs', 'week_1', 3, 'manager'),
        ('Complete mandatory compliance training', 'week_1', 5, 'newhire'),
        ('Shadow key team members', 'week_1', 5, 'newhire'),
        ('End-of-week check-in with manager', 'week_1', 5, 'manager'),
        ('30-day check-in with manager', 'day_30', 30, 'manager'),
        ('Self-assessment: How am I doing?', 'day_30', 30, 'newhire'),
        ('Buddy check-in', 'day_30', 30, 'buddy'),
        ('Complete all initial training modules', 'day_30', 30, 'newhire'),
        ('60-day performance check-in', 'day_60', 60, 'manager'),
        ('Begin independent project work', 'day_60', 60, 'newhire'),
        ('Feedback session: What can we improve?', 'day_60', 60, 'newhire'),
        ('90-day formal review', 'day_90', 90, 'manager'),
        ('Probation review (if applicable)', 'day_90', 90, 'hr'),
        ('Set goals for next quarter', 'day_90', 90, 'manager'),
        ('Onboarding complete celebration', 'day_90', 90, 'hr'),
    ]
    # Mark pre-start tasks as completed for demo
    for title, category, due_day, assigned_to in tasks:
        task = OnboardingTask(
            new_hire_id=new_hire_id, title=title, category=category,
            due_day=due_day, assigned_to=assigned_to,
            completed=(category == 'pre_start'),
            completed_at=datetime.now(timezone.utc) if category == 'pre_start' else None,
        )
        db.session.add(task)


def _seed_employee_data(jared, mireille, admin, positions):
    """Seed all employee portal data: employees, policies, assessments, training, PTO, reviews."""
    from datetime import timedelta

    # ── Demo Employees ──
    emp1_user = User(name='Jordan Blake', email='jordan.blake@puretechnology.nyc', role='employee')
    emp1_user.set_password('brilliance2026')
    db.session.add(emp1_user)

    emp2_user = User(name='Sam Torres', email='sam.torres@puretechnology.nyc', role='employee')
    emp2_user.set_password('brilliance2026')
    db.session.add(emp2_user)
    db.session.flush()

    emp1_profile = EmployeeProfile(
        user_id=emp1_user.id, department='Engineering',
        title='Software Developer', start_date=date(2025, 3, 15),
        manager_id=jared.id, employee_number='PT-1001',
        phone='(416) 555-0101',
    )
    emp2_profile = EmployeeProfile(
        user_id=emp2_user.id, department='Marketing',
        title='Content Specialist', start_date=date(2025, 6, 1),
        manager_id=mireille.id, employee_number='PT-1002',
        phone='(416) 555-0202',
    )
    db.session.add(emp1_profile)
    db.session.add(emp2_profile)

    # ── Policies ──
    policies_data = [
        ('Employee Handbook', 'handbook',
         '<h4>Pure Technology Employee Handbook</h4>'
         '<p>Welcome to Pure Technology. This handbook outlines our policies, procedures, and expectations '
         'for all team members. Our mission is to create a brighter world where all people actualize their brilliance.</p>'
         '<h5>Employment Basics</h5>'
         '<ul><li>Standard work hours: 9 AM - 5 PM, Monday through Friday</li>'
         '<li>Hybrid work: 3 days in office, 2 days remote</li>'
         '<li>Probation period: 90 days for all new hires</li></ul>'
         '<h5>Compensation & Benefits</h5>'
         '<ul><li>Bi-weekly pay schedule</li><li>Health, dental, and vision coverage</li>'
         '<li>RRSP matching up to 4%</li><li>15 vacation days, 10 sick days, 3 personal days per year</li></ul>'),
        ('Code of Conduct', 'compliance',
         '<h4>Code of Conduct</h4>'
         '<p>At Pure Technology, we hold ourselves to the highest ethical standards. Our 7 pillars guide every interaction.</p>'
         '<h5>Core Expectations</h5>'
         '<ul><li><strong>Integrity:</strong> Be honest in all dealings, internally and externally</li>'
         '<li><strong>Accountability:</strong> Own your work and outcomes</li>'
         '<li><strong>Transparency:</strong> Communicate openly and share information freely</li>'
         '<li><strong>Respect:</strong> Treat all colleagues, clients, and partners with dignity</li></ul>'
         '<h5>Prohibited Conduct</h5>'
         '<ul><li>Harassment, discrimination, or bullying of any kind</li>'
         '<li>Misuse of company resources or confidential information</li>'
         '<li>Conflicts of interest without disclosure</li></ul>'),
        ('IT Acceptable Use Policy', 'it',
         '<h4>IT Acceptable Use Policy</h4>'
         '<p>Company technology resources are provided for business purposes. This policy covers acceptable use of all IT systems.</p>'
         '<h5>Covered Systems</h5>'
         '<ul><li>Company-issued laptops and mobile devices</li>'
         '<li>Email, Slack, and collaboration platforms</li>'
         '<li>Cloud services and development environments</li></ul>'
         '<h5>Security Requirements</h5>'
         '<ul><li>Use strong, unique passwords (minimum 12 characters)</li>'
         '<li>Enable multi-factor authentication on all accounts</li>'
         '<li>Lock your workstation when stepping away</li>'
         '<li>Report suspected phishing or security incidents immediately to IT</li></ul>'),
        ('Workplace Safety Policy', 'safety',
         '<h4>Workplace Health & Safety</h4>'
         '<p>Pure Technology is committed to providing a safe and healthy work environment for all team members.</p>'
         '<h5>General Safety</h5>'
         '<ul><li>Report all injuries, illnesses, and hazards immediately</li>'
         '<li>Know the location of fire exits, first aid kits, and AED</li>'
         '<li>Follow ergonomic guidelines for workstation setup</li></ul>'
         '<h5>Emergency Procedures</h5>'
         '<ul><li>Fire: Evacuate via nearest exit, meet at designated assembly point</li>'
         '<li>Medical emergency: Call 911, then notify office management</li>'
         '<li>Severe weather: Move to interior rooms away from windows</li></ul>'),
        ('Remote Work Policy', 'handbook',
         '<h4>Remote Work Policy</h4>'
         '<p>Pure Technology supports flexible work arrangements. This policy outlines expectations for remote work days.</p>'
         '<h5>Eligibility</h5>'
         '<ul><li>All full-time employees after completing probation</li>'
         '<li>Hybrid schedule: minimum 3 days in office per week</li>'
         '<li>Manager approval required for schedule changes</li></ul>'
         '<h5>Remote Work Requirements</h5>'
         '<ul><li>Reliable internet connection (minimum 25 Mbps)</li>'
         '<li>Dedicated workspace free from distractions</li>'
         '<li>Available during core hours (10 AM - 3 PM)</li>'
         '<li>Use company VPN for all work-related activities</li></ul>'),
        ('Anti-Harassment & Discrimination Policy', 'compliance',
         '<h4>Anti-Harassment & Discrimination Policy</h4>'
         '<p>Pure Technology has zero tolerance for harassment, discrimination, or retaliation of any kind.</p>'
         '<h5>Protected Grounds</h5>'
         '<p>This policy prohibits discrimination based on race, colour, ancestry, place of origin, religion, '
         'sex, gender identity, sexual orientation, age, disability, marital status, family status, or any other '
         'ground protected by applicable human rights legislation.</p>'
         '<h5>Reporting</h5>'
         '<ul><li>Report incidents to your manager, HR, or use the anonymous reporting channel</li>'
         '<li>All complaints will be investigated promptly and confidentially</li>'
         '<li>Retaliation against anyone making a good-faith report is strictly prohibited</li></ul>'),
    ]

    for title, category, content in policies_data:
        policy = Policy(
            title=title, category=category, content=content,
            version='1.0', effective_date=date(2025, 1, 1),
            requires_acknowledgment=True,
        )
        db.session.add(policy)
    db.session.flush()

    # ── Assessments ──
    assessments = [
        AssessmentTemplate(
            title='Core Competency Assessment',
            description='Evaluate your understanding of PT\'s core competencies, values, and operational standards.',
            category='competency',
            time_limit_minutes=20,
            passing_score=70,
            questions=json.dumps([
                {'question': 'What is Pure Technology\'s mission?', 'type': 'multiple_choice',
                 'options': ['To maximize shareholder value', 'Reimagining data innovation to redefine relationships between brands and consumers', 'To build the best software', 'To disrupt the HR industry'],
                 'correct': 'Reimagining data innovation to redefine relationships between brands and consumers'},
                {'question': 'How many pillars does Pure Technology have?', 'type': 'multiple_choice',
                 'options': ['5', '6', '7', '8'], 'correct': '7'},
                {'question': 'Which of these is NOT a PT pillar?', 'type': 'multiple_choice',
                 'options': ['Integrity', 'Innovation', 'Efficiency', 'Love'], 'correct': 'Efficiency'},
                {'question': 'The probation period at PT is 90 days.', 'type': 'true_false', 'correct': 'True'},
                {'question': 'What is PT\'s vision?', 'type': 'multiple_choice',
                 'options': ['A brighter world where all people actualize their brilliance', 'To be the #1 technology company', 'Data-driven decisions for all', 'Building better workplaces'],
                 'correct': 'A brighter world where all people actualize their brilliance'},
                {'question': 'Employees can work fully remote without manager approval.', 'type': 'true_false', 'correct': 'False'},
                {'question': 'What does "Actualizing Brilliance" mean at PT?', 'type': 'multiple_choice',
                 'options': ['Getting perfect performance scores', 'Helping every person reach their full potential', 'Working overtime', 'Following processes exactly'],
                 'correct': 'Helping every person reach their full potential'},
                {'question': 'Who said "We hire people we believe will actualize their brilliance"?', 'type': 'multiple_choice',
                 'options': ['Mike Daser', 'Jared Sanborn', 'Mireille Dirary', 'Meridian'],
                 'correct': 'Jared Sanborn'},
                {'question': 'Multi-factor authentication is optional at PT.', 'type': 'true_false', 'correct': 'False'},
                {'question': 'How many vacation days do employees receive per year?', 'type': 'multiple_choice',
                 'options': ['10', '12', '15', '20'], 'correct': '15'},
            ]),
        ),
        AssessmentTemplate(
            title='Culture Alignment Check',
            description='Assess your alignment with PT\'s culture, values, and team expectations.',
            category='personality',
            time_limit_minutes=15,
            passing_score=60,
            questions=json.dumps([
                {'question': 'Love is one of PT\'s 7 pillars.', 'type': 'true_false', 'correct': 'True'},
                {'question': 'Which best describes PT\'s identity?', 'type': 'multiple_choice',
                 'options': ['A technology company that serves people', 'A people company that empowers through technology', 'A data analytics firm', 'A consulting company'],
                 'correct': 'A people company that empowers through technology'},
                {'question': 'How should conflicts at PT be handled?', 'type': 'multiple_choice',
                 'options': ['Escalate to CEO immediately', 'Ignore them', 'Address directly with transparency and respect', 'Discuss only in team meetings'],
                 'correct': 'Address directly with transparency and respect'},
                {'question': 'PT believes diversity makes us all better.', 'type': 'true_false', 'correct': 'True'},
                {'question': 'What hiring philosophy does PT follow?', 'type': 'multiple_choice',
                 'options': ['Hire fast, fire fast', 'Hire for skills only', 'Hire people we believe will actualize their brilliance', 'Hire the cheapest talent available'],
                 'correct': 'Hire people we believe will actualize their brilliance'},
                {'question': 'Innovation at PT means always using the newest technology.', 'type': 'true_false', 'correct': 'False'},
                {'question': 'Accountability at PT means:', 'type': 'multiple_choice',
                 'options': ['Blaming others for failures', 'Owning your work and outcomes', 'Tracking hours meticulously', 'Reporting to multiple managers'],
                 'correct': 'Owning your work and outcomes'},
                {'question': 'Persistence is one of PT\'s 7 pillars.', 'type': 'true_false', 'correct': 'True'},
            ]),
        ),
        AssessmentTemplate(
            title='Compliance Essentials',
            description='Test your knowledge of workplace compliance, safety, and reporting procedures.',
            category='compliance',
            time_limit_minutes=15,
            passing_score=80,
            questions=json.dumps([
                {'question': 'Harassment complaints should be reported to:', 'type': 'multiple_choice',
                 'options': ['Social media', 'Your manager, HR, or anonymous channel', 'Only the CEO', 'External authorities first'],
                 'correct': 'Your manager, HR, or anonymous channel'},
                {'question': 'Retaliation against someone making a harassment report is acceptable if the report is false.', 'type': 'true_false', 'correct': 'False'},
                {'question': 'What is the minimum password length required?', 'type': 'multiple_choice',
                 'options': ['6 characters', '8 characters', '12 characters', '16 characters'],
                 'correct': '12 characters'},
                {'question': 'You should report suspected phishing emails to:', 'type': 'multiple_choice',
                 'options': ['Delete and ignore', 'Forward to friends', 'Report immediately to IT', 'Reply to confirm'],
                 'correct': 'Report immediately to IT'},
                {'question': 'In case of fire, you should use the elevator to evacuate quickly.', 'type': 'true_false', 'correct': 'False'},
                {'question': 'Company VPN should be used for all remote work activities.', 'type': 'true_false', 'correct': 'True'},
                {'question': 'Workplace injuries should be reported:', 'type': 'multiple_choice',
                 'options': ['At the end of the week', 'Immediately', 'Only if severe', 'During performance reviews'],
                 'correct': 'Immediately'},
                {'question': 'Sharing your login credentials with a trusted colleague is acceptable.', 'type': 'true_false', 'correct': 'False'},
                {'question': 'The assembly point after fire evacuation is:', 'type': 'multiple_choice',
                 'options': ['The parking lot entrance', 'The designated assembly point', 'Your car', 'Back inside the building'],
                 'correct': 'The designated assembly point'},
                {'question': 'All employees must complete safety training during their first week.', 'type': 'true_false', 'correct': 'True'},
            ]),
        ),
    ]
    for a in assessments:
        db.session.add(a)

    # ── Training Courses ──
    course1 = TrainingCourse(
        title='PT Culture Onboarding', description='Deep dive into Pure Technology\'s culture, values, and what it means to actualize brilliance. Every team member should complete this course.',
        category='onboarding', estimated_hours=2.0, is_required=True,
    )
    course2 = TrainingCourse(
        title='Compliance Essentials', description='Mandatory compliance training covering workplace safety, IT security, harassment prevention, and reporting procedures.',
        category='compliance', estimated_hours=1.5, is_required=True,
    )
    course3 = TrainingCourse(
        title='Leadership Foundations', description='Build your leadership toolkit — communication, delegation, feedback, and team development.',
        category='leadership', estimated_hours=3.0, is_required=False,
    )
    course4 = TrainingCourse(
        title='Data Privacy & Security', description='Learn how to handle sensitive data, understand privacy regulations, and protect company information.',
        category='skills', estimated_hours=1.0, is_required=False,
    )
    db.session.add_all([course1, course2, course3, course4])
    db.session.flush()

    # Culture Onboarding modules
    culture_modules = [
        ('Our Vision & Mission', 1, 'text', 20,
         '<h4>Pure Technology\'s Vision</h4>'
         '<p><em>"A brighter world where all people actualize their brilliance."</em></p>'
         '<p>This vision drives everything we do. It\'s not just words on a wall — it\'s the lens through which we make decisions, hire talent, and build technology.</p>'
         '<h5>What "Actualizing Brilliance" Means</h5>'
         '<p>Everyone has unique strengths, perspectives, and potential. Our job as a company is to create the conditions where that potential can flourish. We don\'t just hire people who are "good enough." We hire people we believe will actualize their brilliance.</p>'),
        ('The 7 Pillars', 2, 'text', 25,
         '<h4>PT\'s 7 Pillars</h4>'
         '<p>These pillars aren\'t just values — they\'re behavioral commitments that guide how we work every day.</p>'
         '<ol><li><strong>Integrity</strong> — Be honest, even when it\'s hard</li>'
         '<li><strong>Accountability</strong> — Own your outcomes, good and bad</li>'
         '<li><strong>Transparency</strong> — Share openly, hide nothing</li>'
         '<li><strong>Growth</strong> — Always be learning, always improving</li>'
         '<li><strong>Innovation</strong> — Question assumptions, try new approaches</li>'
         '<li><strong>Persistence</strong> — Don\'t give up when things get tough</li>'
         '<li><strong>Love</strong> — Care genuinely about the people around you</li></ol>'
         '<p>Love is our most important pillar. Not because it sounds nice — because building a great company requires genuinely caring about the humans who make it happen.</p>'),
        ('How We Work', 3, 'interactive', 20,
         '<h4>Pure Technology\'s Way of Working</h4>'
         '<h5>Hybrid Work Model</h5>'
         '<p>We believe in the power of in-person collaboration AND the flexibility of remote work. Our hybrid model (3 days in, 2 days remote) gives you both.</p>'
         '<h5>Communication</h5>'
         '<ul><li><strong>Slack</strong> for quick questions and daily collaboration</li>'
         '<li><strong>Email</strong> for external communication and formal matters</li>'
         '<li><strong>Meetings</strong> should have agendas, be time-boxed, and end with action items</li></ul>'
         '<h5>Decision Making</h5>'
         '<p>We use a "disagree and commit" framework. Voice your perspective, listen to others, and once a decision is made, commit fully — even if you initially disagreed.</p>'),
        ('Our People Philosophy', 4, 'text', 15,
         '<h4>People First, Always</h4>'
         '<p><em>"Pure isn\'t a technology company that serves people. It\'s a people company that empowers through technology."</em></p>'
         '<h5>What This Means for You</h5>'
         '<ul><li>You\'re not a "resource" — you\'re a person with unique gifts</li>'
         '<li>Your growth matters as much as your output</li>'
         '<li>Feedback is a gift, both giving and receiving</li>'
         '<li>We invest in your development because your brilliance benefits everyone</li></ul>'),
        ('Culture Check Quiz', 5, 'quiz', 10,
         '<h4>Quick Culture Check</h4>'
         '<p>Reflect on what you\'ve learned:</p>'
         '<ul><li>Can you name all 7 pillars from memory?</li>'
         '<li>What does "actualizing brilliance" mean to you personally?</li>'
         '<li>How would you describe PT\'s identity to a friend?</li>'
         '<li>Which pillar resonates most with you, and why?</li></ul>'
         '<p>There are no wrong answers here — this is about reflection, not testing. Take a moment to think about these questions before marking this module complete.</p>'),
    ]
    for title, order, content_type, duration, content in culture_modules:
        m = TrainingModule(course_id=course1.id, title=title, order=order,
                          content_type=content_type, duration_minutes=duration, content=content)
        db.session.add(m)

    # Compliance modules
    compliance_modules = [
        ('Workplace Safety', 1, 'text', 20,
         '<h4>Workplace Health & Safety</h4>'
         '<p>Every team member has the right to a safe workplace and the responsibility to maintain it.</p>'
         '<h5>Your Responsibilities</h5>'
         '<ul><li>Report all hazards, injuries, and near-misses immediately</li>'
         '<li>Follow ergonomic guidelines for your workstation</li>'
         '<li>Know your emergency exits and assembly point</li>'
         '<li>Complete all required safety training on time</li></ul>'
         '<h5>Emergency Contacts</h5>'
         '<ul><li>Fire/Medical: 911</li><li>Building Security: ext. 100</li><li>HR Emergency: ext. 205</li></ul>'),
        ('IT Security Essentials', 2, 'text', 20,
         '<h4>IT Security</h4>'
         '<p>Cybersecurity is everyone\'s responsibility. One weak link can compromise the entire organization.</p>'
         '<h5>Password Policy</h5>'
         '<ul><li>Minimum 12 characters with mixed case, numbers, and symbols</li>'
         '<li>Never reuse passwords across services</li>'
         '<li>Use a password manager (company provides 1Password)</li></ul>'
         '<h5>Phishing Awareness</h5>'
         '<ul><li>Check sender email addresses carefully</li>'
         '<li>Hover over links before clicking</li>'
         '<li>Never provide credentials via email</li>'
         '<li>When in doubt, forward to security@puretechnology.nyc</li></ul>'),
        ('Harassment Prevention', 3, 'text', 25,
         '<h4>Harassment Prevention Training</h4>'
         '<p>Pure Technology has zero tolerance for harassment, discrimination, and bullying.</p>'
         '<h5>What Constitutes Harassment</h5>'
         '<ul><li>Unwelcome verbal, physical, or visual conduct</li>'
         '<li>Creating an intimidating, hostile, or offensive environment</li>'
         '<li>Conduct based on protected characteristics (race, gender, orientation, etc.)</li></ul>'
         '<h5>Bystander Intervention</h5>'
         '<p>If you witness harassment, you have a responsibility to act:</p>'
         '<ol><li><strong>Direct:</strong> Address the behavior if safe to do so</li>'
         '<li><strong>Distract:</strong> Redirect the conversation or situation</li>'
         '<li><strong>Delegate:</strong> Report to management or HR</li>'
         '<li><strong>Document:</strong> Record what you observed</li></ol>'),
        ('Compliance Quiz', 4, 'quiz', 15,
         '<h4>Compliance Knowledge Check</h4>'
         '<p>Review these scenarios and consider the correct response:</p>'
         '<ol><li>A colleague shares their password with you "just in case." What do you do?</li>'
         '<li>You receive a suspicious email asking you to verify your credentials. Next steps?</li>'
         '<li>You notice a wet floor in the hallway with no warning sign. Your action?</li>'
         '<li>A team member makes inappropriate jokes about a colleague\'s background. What should you do?</li></ol>'
         '<p>Think through each scenario before marking this module complete. If you\'re unsure about any, reach out to HR.</p>'),
    ]
    for title, order, content_type, duration, content in compliance_modules:
        m = TrainingModule(course_id=course2.id, title=title, order=order,
                          content_type=content_type, duration_minutes=duration, content=content)
        db.session.add(m)

    # Leadership modules
    leadership_modules = [
        ('Communication Skills', 1, 'text', 30, '<h4>Effective Communication</h4><p>Great leaders communicate clearly, listen actively, and adapt their style to their audience.</p><h5>Key Principles</h5><ul><li>Lead with context, not commands</li><li>Ask questions before giving answers</li><li>Match your medium to your message</li></ul>'),
        ('Giving Feedback', 2, 'interactive', 25, '<h4>The Art of Feedback</h4><p>Feedback is a gift — both giving and receiving. Master these frameworks:</p><h5>SBI Model</h5><ul><li><strong>Situation:</strong> When/where did this happen?</li><li><strong>Behavior:</strong> What specifically did the person do?</li><li><strong>Impact:</strong> What was the result?</li></ul>'),
        ('Delegation', 3, 'text', 20, '<h4>Effective Delegation</h4><p>Delegation is not about offloading work — it\'s about developing your team.</p><ul><li>Delegate the outcome, not the method</li><li>Match tasks to development goals</li><li>Provide the authority, not just the responsibility</li></ul>'),
    ]
    for title, order, content_type, duration, content in leadership_modules:
        m = TrainingModule(course_id=course3.id, title=title, order=order,
                          content_type=content_type, duration_minutes=duration, content=content)
        db.session.add(m)

    # Data Privacy modules
    privacy_modules = [
        ('Data Classification', 1, 'text', 15, '<h4>Data Classification at PT</h4><ul><li><strong>Public:</strong> Press releases, marketing materials</li><li><strong>Internal:</strong> Strategy docs, meeting notes</li><li><strong>Confidential:</strong> Employee data, financial reports</li><li><strong>Restricted:</strong> Credentials, PII, legal documents</li></ul>'),
        ('Privacy Regulations', 2, 'text', 20, '<h4>Privacy Regulations Overview</h4><p>Depending on where we operate, different privacy laws apply.</p><ul><li><strong>PIPEDA</strong> (Canada) — Personal Information Protection</li><li><strong>CCPA/CPRA</strong> (California) — Consumer Privacy</li><li><strong>GDPR</strong> (EU) — General Data Protection Regulation</li></ul><p>When in doubt, treat all personal data as confidential and follow the principle of least privilege.</p>'),
    ]
    for title, order, content_type, duration, content in privacy_modules:
        m = TrainingModule(course_id=course4.id, title=title, order=order,
                          content_type=content_type, duration_minutes=duration, content=content)
        db.session.add(m)

    # ── PTO Balances ──
    current_year = date.today().year
    pto1 = PTOBalance(user_id=emp1_user.id, year=current_year,
                      vacation_total=15, vacation_used=4,
                      sick_total=10, sick_used=1,
                      personal_total=3, personal_used=0)
    pto2 = PTOBalance(user_id=emp2_user.id, year=current_year,
                      vacation_total=15, vacation_used=7,
                      sick_total=10, sick_used=2,
                      personal_total=3, personal_used=1)
    db.session.add_all([pto1, pto2])

    # Demo PTO request (pending)
    pto_req = PTORequest(
        user_id=emp1_user.id, leave_type='vacation',
        start_date=date.today() + timedelta(days=14),
        end_date=date.today() + timedelta(days=18),
        days_requested=5, reason='Family vacation',
    )
    db.session.add(pto_req)

    # ── Review Cycle ──
    cycle = ReviewCycle(
        title='2026 Mid-Year Review', year=current_year,
        cycle_type='mid_year', status='active',
    )
    db.session.add(cycle)
    db.session.flush()

    # Reviews for employees
    review1 = PerformanceReview(
        cycle_id=cycle.id, employee_id=emp1_user.id,
        reviewer_id=jared.id, status='pending_self',
    )
    review2 = PerformanceReview(
        cycle_id=cycle.id, employee_id=emp2_user.id,
        reviewer_id=mireille.id, status='pending_self',
    )
    db.session.add_all([review1, review2])

    db.session.commit()


def _reconcile_schema():
    """Add Phase 2 employee_profiles columns that create_all() cannot add to a
    table that already exists (e.g. a Render Postgres predating Phase 2).
    Idempotent and non-destructive; a no-op on a fresh DB where create_all()
    already built the columns."""
    from sqlalchemy import inspect as _inspect, text as _text
    insp = _inspect(db.engine)
    if 'employee_profiles' not in insp.get_table_names():
        return
    existing = {c['name'] for c in insp.get_columns('employee_profiles')}
    coldefs = [
        ('address_line1', 'VARCHAR(200)'), ('address_line2', 'VARCHAR(200)'),
        ('city', 'VARCHAR(100)'), ('province_state', 'VARCHAR(100)'),
        ('postal_code', 'VARCHAR(20)'), ('country', 'VARCHAR(100)'),
        ('date_of_birth', 'DATE'), ('employment_status', 'VARCHAR(20)'),
        ('employment_type', 'VARCHAR(20)'), ('termination_date', 'DATE'),
        ('termination_reason', 'TEXT'),
    ]
    added = []
    for name, ddl in coldefs:
        if name not in existing:
            db.session.execute(_text(f'ALTER TABLE employee_profiles ADD COLUMN {name} {ddl}'))
            added.append(name)
    if added:
        db.session.commit()
        print(f'[schema] reconciled employee_profiles columns: {added}', flush=True)


with app.app_context():
    # ── Migration strategy (Phase 2, Alembic adopted 2026-10-28) ──
    # db.create_all() only CREATEs tables that don't exist yet; it never ALTERs
    # an existing table. That makes it safe to run on every boot:
    #   - Fresh deploy (no DB yet): create_all() builds every table — including
    #     brand-new Phase 2 tables (compensation_records, bonus_records,
    #     salary_bands, audit_logs) — with the full current schema in one shot.
    #     No `flask db upgrade` is required for a fresh DB.
    #   - Existing deployed DB (e.g. a Render Postgres that predates Phase 2):
    #     create_all() will add the new tables above (they don't exist yet) but
    #     CANNOT add new columns to tables that already exist, like the Phase 2
    #     columns added to employee_profiles (address, employment_status, etc).
    #     Those column additions live in migrations/versions/ and must be
    #     applied once via `flask db upgrade` against that database.
    # The dev SQLite DB (instance/brilliance.db) has already had `flask db
    # upgrade` run against it as part of this change, and is fully migrated.
    db.create_all()
    _reconcile_schema()
    seed_database()
    from app.pt_seed import seed_pt_team, provision_admins
    seed_pt_team()
    provision_admins()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
