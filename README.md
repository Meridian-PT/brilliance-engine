# Brilliance Engine

**Pure Technology's HR Operating System** — Where brilliance begins.

> "We don't hire people that are good enough to work here. We hire people we believe will actualize their brilliance!" — Jared Sanborn, Chairman & CEO

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Meridian-PT/brilliance-engine)

---

## What Is Brilliance Engine?

Brilliance Engine is the platform where Pure Technology's hiring process begins and onboarding journey unfolds. Built on the Pure Method 2.0, it brings PT's 7-stage hiring pipeline, scorecard system, and Pure Start onboarding program into one unified system.

### Four Portals

| Portal | For | What They Do |
|--------|-----|--------------|
| **Candidate** | Job applicants | Browse positions, apply, track progress through the pipeline |
| **New Hire** | Day-one employees | Onboarding dashboard, task checklist, culture immersion |
| **Hiring Manager** | Team leads | Pipeline view, scorecards, advance/reject candidates |
| **Admin / HR** | HR team | Full system control, user management, analytics |

### Built On

- **Pure Method 2.0** — PT's 7-stage hiring pipeline (Screening through Offer & Onboarding)
- **Applicant Grading System** — 6-dimension scorecard (Communication, Experience, Niche Skills, Thinking, Emotional, Leadership)
- **Bar Raiser Protocol** — Independent evaluator with absolute veto power
- **Pure Start** — 27-task onboarding system spanning pre-start through Day 90
- **PT Culture** — 7 Pillars: Integrity, Accountability, Transparency, Growth, Innovation, Persistence, Love

---

## Deploy

### One-Click Deploy (Recommended)

Click the **Deploy to Render** button above. Render will:
1. Create a free web service
2. Install dependencies
3. Start the app with Gunicorn

You'll get a permanent URL like `brilliance-engine.onrender.com`.

### Local Development

```bash
git clone https://github.com/Meridian-PT/brilliance-engine.git
cd brilliance-engine
pip install -r requirements.txt
python run.py
```

Visit `http://localhost:5000`

### Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Admin | mike@puretechnology.nyc | brilliance2026 |
| Manager | jared@puretechnology.nyc | brilliance2026 |
| Candidate | sarah.chen@email.com | candidate2026 |

---

## Tech Stack

- **Backend**: Python / Flask 3.x
- **Database**: SQLite (dev) / PostgreSQL (prod-ready)
- **Auth**: Flask-Login with role-based access
- **Frontend**: Bootstrap 5 + Inter font + PT brand colors
- **Deployment**: Render (render.yaml included)

---

## Vision

> "A brighter world where all people actualize their brilliance"

Brilliance Engine is Jared and Mireille's vision brought to life — a system where every candidate interaction reflects Pure Technology's belief that people are the foundation of everything worth building.

---

Built by Meridian, PT's HR Intelligence Platform.
