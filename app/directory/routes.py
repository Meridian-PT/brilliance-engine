from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, EmployeeProfile

directory_bp = Blueprint('directory', __name__, template_folder='../templates/directory')


def internal_required(f):
    """Any logged-in internal staff member (employee, manager, admin) — not candidates/newhires."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('employee', 'manager', 'admin'):
            flash('Access denied. Employee directory is for internal staff only.', 'error')
            return redirect(url_for('auth.landing'))
        return f(*args, **kwargs)
    return decorated


# ── Directory Listing ───────────────────────────────────────────────────────

@directory_bp.route('')
@login_required
@internal_required
def index():
    q = request.args.get('q', '').strip()
    department = request.args.get('department', '').strip()

    query = EmployeeProfile.query.join(User, EmployeeProfile.user_id == User.id) \
        .filter(User.is_active_user == True)

    if department:
        query = query.filter(EmployeeProfile.department == department)

    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(User.name.ilike(like), User.email.ilike(like),
                   EmployeeProfile.title.ilike(like))
        )

    profiles = query.order_by(User.name).all()

    departments = db.session.query(EmployeeProfile.department).filter(
        EmployeeProfile.department.isnot(None)
    ).distinct().all()
    departments = sorted(set(d[0] for d in departments if d[0]))

    return render_template('directory/index.html',
                           profiles=profiles,
                           departments=departments,
                           current_department=department,
                           search=q)


# ── Individual Profile Card ─────────────────────────────────────────────────

@directory_bp.route('/<int:user_id>')
@login_required
@internal_required
def profile_card(user_id):
    user = User.query.get_or_404(user_id)
    if user.role not in ('employee', 'manager', 'admin') or not user.is_active_user:
        flash('That person is not listed in the internal directory.', 'error')
        return redirect(url_for('directory.index'))

    # Managers/admins referenced in the org chart may not have their own
    # EmployeeProfile yet — show a minimal card instead of 404ing.
    profile = EmployeeProfile.query.filter_by(user_id=user_id).first()
    return render_template('directory/profile_card.html', user=user, profile=profile)


# ── Org Chart ────────────────────────────────────────────────────────────────

@directory_bp.route('/orgchart')
@login_required
@internal_required
def orgchart():
    all_profiles = EmployeeProfile.query.join(User, EmployeeProfile.user_id == User.id) \
        .filter(User.is_active_user == True).all()

    profile_by_user_id = {p.user_id: p for p in all_profiles}

    # Managers referenced by manager_id who don't have their own EmployeeProfile
    # (e.g. hiring managers / admins who aren't tracked as "employees" in this phase)
    referenced_manager_ids = {p.manager_id for p in all_profiles if p.manager_id}
    synthetic_ids = referenced_manager_ids - set(profile_by_user_id.keys())
    synthetic_users = {}
    if synthetic_ids:
        synthetic_users = {u.id: u for u in User.query.filter(User.id.in_(synthetic_ids)).all()}

    # Unified node map: user_id -> node dict
    nodes = {}
    for uid, p in profile_by_user_id.items():
        nodes[uid] = {
            'id': uid,
            'name': p.user.name,
            'title': p.title or p.user.role.title(),
            'department': p.department,
            'manager_id': p.manager_id,
            'synthetic': False,
            'profile_id': p.id,
        }
    for uid, u in synthetic_users.items():
        nodes[uid] = {
            'id': uid,
            'name': u.name,
            'title': u.role.title(),
            'department': None,
            'manager_id': None,  # unknown — treat as top-level
            'synthetic': True,
            'profile_id': None,
        }

    # Build children map (only link if the manager is a known node)
    children_map = {}
    for uid, node in nodes.items():
        mgr = node['manager_id']
        if mgr and mgr in nodes:
            children_map.setdefault(mgr, []).append(uid)

    for kids in children_map.values():
        kids.sort(key=lambda k: nodes[k]['name'])

    # Roots: no manager, or manager not in our node set (dangling reference)
    root_ids = sorted(
        [uid for uid, n in nodes.items() if not n['manager_id'] or n['manager_id'] not in nodes],
        key=lambda uid: nodes[uid]['name']
    )

    def build_tree(uid, path):
        node = nodes[uid]
        children = []
        for kid in children_map.get(uid, []):
            if kid in path:
                # Cycle detected — render as a terminal node, don't recurse further.
                children.append({**nodes[kid], 'children': [], 'is_cycle': True})
            else:
                children.append(build_tree(kid, path | {kid}))
        return {**node, 'children': children, 'is_cycle': False}

    trees = [build_tree(rid, {rid}) for rid in root_ids]

    # Any nodes not reachable from a root are part of a pure cycle (A manages B
    # manages A, with no node lacking a manager_id). Surface them as their own
    # root trees so nothing silently disappears from the chart.
    reached = set()

    def collect_ids(tree_node):
        reached.add(tree_node['id'])
        for c in tree_node['children']:
            if not c.get('is_cycle'):
                collect_ids(c)
            else:
                reached.add(c['id'])

    for t in trees:
        collect_ids(t)

    remaining = sorted(set(nodes.keys()) - reached, key=lambda uid: nodes[uid]['name'])
    while remaining:
        rid = remaining[0]
        trees.append(build_tree(rid, {rid}))
        collect_ids(trees[-1])
        remaining = sorted(set(nodes.keys()) - reached, key=lambda uid: nodes[uid]['name'])

    return render_template('directory/orgchart.html', trees=trees, has_nodes=bool(nodes))
