"""Seed the real Pure Technology org into Brilliance Engine.

Idempotent: matches existing users by name (so the demo-seed users aren't
duplicated), derives emails for new people, and wires up the reporting chain so
the Directory + Org Chart render the real company. Advisors are intentionally
excluded (external, not staff). Runs at boot after the base seed; safe to run
on every boot (writes only when a record is missing).
"""
import os
import json
import secrets
from datetime import date
from werkzeug.security import generate_password_hash

from app import db
from app.models import User, EmployeeProfile

# (name, title, department, manager_name, role)
ORG = [
    ("Jared Sanborn", "Chairman & Chief Executive Officer", "Executive", None, "admin"),
    ("Melanie Salvador", "Vice Chairman & Deputy CEO", "Executive", "Jared Sanborn", "admin"),
    ("Nils Waschkau", "Chief Operations Officer", "Operations", "Jared Sanborn", "manager"),
    ("James Weinberg", "Chief Financial Officer", "Finance", "Jared Sanborn", "manager"),
    ("Mike Daser", "SVP Human Resources", "People & HR", "Jared Sanborn", "admin"),
    ("Eric Solomon", "Chief Brilliance Actualizer", "Executive", "Jared Sanborn", "manager"),
    ("Mike Schuman", "Chief Commercial Officer", "Commercial", "Jared Sanborn", "manager"),
    ("Roger Singh", "Chief of Staff, Technology", "Technology", "Jared Sanborn", "manager"),
    ("Timothy DeVore", "Chief Technology Officer", "Engineering", "Jared Sanborn", "manager"),
    ("Rimah Harb", "Chief Strategy Officer", "Strategy", "Jared Sanborn", "manager"),
    ("Zeena Tata", "Chief Impact Officer", "Executive", "Jared Sanborn", "manager"),
    ("Michael Hancock", "General Counsel", "Legal", "Jared Sanborn", "manager"),
    ("Mireille Dirary", "Executive Director, Office of the CEO", "Executive", "Jared Sanborn", "manager"),
    ("Linda Chaaya", "Executive Assistant", "Executive", "Mireille Dirary", "employee"),
    ("Faris Asmar", "Hardware Advisor, Technology", "Technology", "Jared Sanborn", "manager"),
    ("Edward Brosnan", "SVP Operations", "Operations", "Nils Waschkau", "manager"),
    ("Roger Besini", "VP Operations", "Operations", "Nils Waschkau", "employee"),
    ("Chris Isbit", "VP, Finance Operations", "Finance", "Nils Waschkau", "employee"),
    ("Paula Bou Chaaya", "VP Finance", "Finance", "Nils Waschkau", "employee"),
    ("Cara Salvador", "CFO, PT Canada", "Finance", "Nils Waschkau", "employee"),
    ("Micheline Akel", "HR & Office Support Manager", "People & HR", "Mike Daser", "employee"),
    ("Alexander Logie", "EVP Corporate Development", "Corporate Development", "Mike Daser", "manager"),
    ("Marcie Mcgovern", "VP Strategic Relations", "Strategic Relations", "Mike Daser", "employee"),
    ("John Smith", "VP Sales", "Sales", "Mike Daser", "employee"),
    ("Jesse Cruz", "VP Revenue (Franchise)", "Revenue", "Mike Daser", "employee"),
    ("Mohammad El Madhoun", "EVP Revenue & Operations", "Revenue", "Mike Daser", "manager"),
    ("Philip Bliss", "Chief Marketing Officer", "Marketing", "Mike Schuman", "manager"),
    ("Robert Oriowski", "SVP Marketing & Communications", "Marketing", "Philip Bliss", "employee"),
    ("John Paris", "SVP Digital Strategy", "Marketing", "Philip Bliss", "employee"),
    ("Nathan Olson", "President, Pure Marketing Group", "Marketing", "Philip Bliss", "manager"),
    ("Natasha Green", "VP of Operations", "Marketing (PMG)", "Nathan Olson", "manager"),
    ("Baruch Santana", "Team Director of Operations", "Marketing (PMG)", "Nathan Olson", "employee"),
    ("Moises Guerra", "Social Media Strategist", "Marketing (PMG)", "Nathan Olson", "employee"),
    ("Dylan Diaz", "Team Director of Commercial", "Marketing (PMG)", "Nathan Olson", "employee"),
    ("Ashley Tann", "Service Operations Manager", "Marketing (PMG)", "Nathan Olson", "employee"),
    ("Max Osborne", "Data Specialist", "Marketing (PMG)", "Nathan Olson", "employee"),
    ("Frank Thomas", "SVP Product", "Product", "Jared Sanborn", "manager"),
    ("Desiree Vazquez", "Director, Design", "Product", "Frank Thomas", "employee"),
    ("Alonso Awan", "Director, Product Manager", "Product", "Frank Thomas", "employee"),
    ("Waqas Nasir", "Product Owner & Software Developer", "Product", "Frank Thomas", "employee"),
    ("Emmanuel Mark Quinton", "Project Manager", "Product", "Frank Thomas", "employee"),
    ("Christie Mallari", "Project Manager", "Product", "Frank Thomas", "employee"),
    ("Angelica Hadep", "Project Manager", "Product", "Frank Thomas", "employee"),
    ("Bill Myers", "Program Manager", "Product", "Frank Thomas", "employee"),
    ("Russell Korus", "Chief Digital Assets Officer", "Product", "Jared Sanborn", "manager"),
    ("Alex Seant", "Senior Software Engineer", "Engineering", "Timothy DeVore", "employee"),
    ("Ethan Devore", "Full Stack Developer", "Engineering", "Timothy DeVore", "employee"),
    ("Zaheer Hassan", "Sr. Software Developer", "Engineering", "Timothy DeVore", "employee"),
    ("Shabaz Ali", "Manager, IT and DevOps", "Engineering", "Timothy DeVore", "manager"),
    ("Adeeb Doyle", "Software Developer", "Engineering", "Shabaz Ali", "employee"),
    ("Samuel Saleh", "Junior Developer", "Engineering", "Shabaz Ali", "employee"),
    ("Zachary Skotek", "Junior Developer", "Engineering", "Shabaz Ali", "employee"),
    ("Emmanuel Akinleye", "Junior Developer", "Engineering", "Shabaz Ali", "employee"),
    ("Michael Malconte", "Sr. Full Stack Developer", "Engineering", "Timothy DeVore", "employee"),
    ("Juvel Pateno", "Sr. Full Stack Developer", "Engineering", "Timothy DeVore", "employee"),
    ("Jenel Pateno", "Sr. Full Stack Developer", "Engineering", "Timothy DeVore", "employee"),
    ("Johna Bagg-od", "Sr. Full Stack Developer", "Engineering", "Timothy DeVore", "employee"),
    ("Serg Casquejo", "Sr. Full Stack Developer", "Engineering", "Timothy DeVore", "employee"),
    ("Green Bayetta", "Sr. Full Stack Developer", "Engineering", "Timothy DeVore", "employee"),
    ("PJ Cordero", "Sr. Full Stack Developer", "Engineering", "Timothy DeVore", "employee"),
    ("Joseph Esperon", "Sr. Full Stack Developer", "Engineering", "Timothy DeVore", "employee"),
]

KNOWN_EMAIL = {
    "Jared Sanborn": "jared@puretechnology.nyc",
    "Mireille Dirary": "mireille@puretechnology.nyc",
    "Melanie Salvador": "melanie@puretechnology.nyc",
    "Natasha Green": "natasha@puretechnology.nyc",
    "Mike Daser": "mdaser@puretechnology.nyc",
    "Alex Seant": "alex.seant@puretechnology.nyc",
    "Nathan Olson": "nathan@puremarketing.ai",
    "Waqas Nasir": "waqas@puretechnology.nyc",
    "Faris Asmar": "faris@puretechnology.nyc",
}

RANK = {"candidate": 0, "newhire": 1, "employee": 2, "manager": 3, "admin": 4}


def _derive_email(name, used):
    base = KNOWN_EMAIL.get(name)
    if base and base.lower() not in used:
        return base
    parts = name.lower().replace("'", "").split()
    local = (parts[0] + "." + parts[-1]) if len(parts) > 1 else parts[0]
    local = "".join(c for c in local if c.isalnum() or c == ".")
    email = f"{local}@puretechnology.nyc"
    n = 2
    while email.lower() in used:
        email = f"{local}{n}@puretechnology.nyc"
        n += 1
    return email


def seed_pt_team():
    existing = User.query.all()
    by_name = {u.name.strip().lower(): u for u in existing}
    used = {u.email.lower() for u in existing}

    name_to_user, created_u = {}, 0
    for name, title, dept, mgr, role in ORG:
        u = by_name.get(name.strip().lower())
        if u is None:
            email = _derive_email(name, used)
            used.add(email.lower())
            u = User(email=email, name=name,
                     password_hash=generate_password_hash("Seed!" + secrets.token_hex(8)),
                     role=role, is_active_user=True)
            db.session.add(u)
            created_u += 1
        elif RANK.get(role, 2) > RANK.get(u.role, 2):
            u.role = role
        name_to_user[name] = u
    db.session.flush()

    created_p, empno = 0, 1001
    for name, title, dept, mgr, role in ORG:
        u = name_to_user[name]
        prof = EmployeeProfile.query.filter_by(user_id=u.id).first()
        if prof is None:
            prof = EmployeeProfile(user_id=u.id, department=dept, title=title,
                                   start_date=date(2024, 1, 15),
                                   employee_number=f"PT-{empno}", employment_status="active")
            db.session.add(prof)
            created_p += 1
        else:
            prof.department, prof.title = dept, title
            if not prof.employment_status:
                prof.employment_status = "active"
            if not prof.employee_number:
                prof.employee_number = f"PT-{empno}"
        empno += 1
    db.session.flush()

    for name, title, dept, mgr, role in ORG:
        if mgr and mgr in name_to_user:
            prof = EmployeeProfile.query.filter_by(user_id=name_to_user[name].id).first()
            if prof:
                prof.manager_id = name_to_user[mgr].id
    db.session.commit()
    if created_u or created_p:
        print(f"[pt_seed] created {created_u} users, {created_p} profiles", flush=True)


def provision_admins():
    """Grant admin + set a password for users listed in the PROVISION_ADMINS env
    var (JSON: [{"email","password"}, ...]). Lets us hand out working admin logins
    without putting passwords in the repo. Idempotent; a no-op if the var is unset.
    Clear the env var once the people have changed their passwords."""
    raw = os.environ.get("PROVISION_ADMINS")
    if not raw:
        return
    try:
        entries = json.loads(raw)
    except (ValueError, TypeError):
        print("[provision_admins] PROVISION_ADMINS is not valid JSON; skipping", flush=True)
        return
    done = 0
    for e in entries:
        email = (e.get("email") or "").strip()
        pw = e.get("password")
        if not email or not pw:
            continue
        u = User.query.filter((User.email.ilike(email))).first()
        if u is None:
            continue
        u.role = "admin"
        u.is_active_user = True
        u.password_hash = generate_password_hash(pw)
        done += 1
    if done:
        db.session.commit()
        print(f"[provision_admins] provisioned {done} admin login(s)", flush=True)
