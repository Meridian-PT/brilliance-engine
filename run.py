#!/usr/bin/env python3
"""Brilliance Engine — Pure Technology's HR Operating System."""

import os
import sys

# Ensure instance directory exists for SQLite
os.makedirs(os.path.join(os.path.dirname(__file__), 'instance'), exist_ok=True)

from app import create_app, db
from app.models import User, Position, Candidate, Document, NewHire, OnboardingTask


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

    db.session.commit()
    print(f"Seeded: {User.query.count()} users, {Position.query.count()} positions, "
          f"{Candidate.query.count()} candidates, {Document.query.count()} documents")


with app.app_context():
    db.create_all()
    seed_database()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
