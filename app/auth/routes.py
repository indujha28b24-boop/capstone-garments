from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User, ActivityLog

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login/owner', methods=['GET', 'POST'])
def login_owner():
    if current_user.is_authenticated:
        return redirect_user_dashboard(current_user)

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash('Invalid executive credentials. Access denied.', 'danger')
            return render_template('auth/login_owner.html')

        if user.role != 'owner':
            flash('Access Denied: You do not have Owner privileges.', 'warning')
            return render_template('auth/login_owner.html')

        login_user(user, remember=remember)
        log_activity(user.id, f"Owner executive logged in: {username}")
        flash('Welcome back to Executive ERP Portal!', 'success')
        return redirect(url_for('owner.dashboard'))

    return render_template('auth/login_owner.html')


@auth_bp.route('/login/manager', methods=['GET', 'POST'])
def login_manager():
    if current_user.is_authenticated:
        return redirect_user_dashboard(current_user)

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash('Invalid manager credentials.', 'danger')
            return render_template('auth/login_manager.html')

        if user.role not in ['manager', 'owner']:
            flash('Access Denied: You do not have Manager privileges.', 'warning')
            return render_template('auth/login_manager.html')

        login_user(user, remember=remember)
        log_activity(user.id, f"Production Manager logged in: {username}")
        flash('Production Floor Management Session Active.', 'success')
        return redirect(url_for('manager.dashboard'))

    return render_template('auth/login_manager.html')


@auth_bp.route('/login/worker')
def login_worker():
    return redirect(url_for('auth.login_stitching'))

@auth_bp.route('/login/cutting', methods=['GET', 'POST'])
def login_cutting():
    return handle_worker_login('Cutting', 'auth/login_cutting.html')

@auth_bp.route('/login/stitching', methods=['GET', 'POST'])
def login_stitching():
    return handle_worker_login('Stitching', 'auth/login_stitching.html')

@auth_bp.route('/login/quality', methods=['GET', 'POST'])
def login_quality():
    return handle_worker_login('Quality Check', 'auth/login_quality.html')

@auth_bp.route('/login/packing', methods=['GET', 'POST'])
def login_packing():
    return handle_worker_login('Packing', 'auth/login_packing.html')


def handle_worker_login(dept_name, template_file):
    if current_user.is_authenticated:
        return redirect_user_dashboard(current_user)

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash(f'Invalid {dept_name} Department credentials.', 'danger')
            return render_template(template_file)

        if user.role != 'worker':
            flash('Please use the appropriate Executive/Manager portal.', 'warning')
            return render_template(template_file)

        login_user(user, remember=remember)
        log_activity(user.id, f"Worker logged into {dept_name} department: {username}")
        flash(f'Welcome {user.username}! {dept_name} Station Active.', 'info')
        return redirect(url_for('worker.dashboard'))

    return render_template(template_file)


@auth_bp.route('/logout')
@login_required
def logout():
    log_activity(current_user.id, "User logged out")
    logout_user()
    flash('Safely logged out of StitchTech ERP.', 'info')
    return redirect(url_for('main.landing'))


def redirect_user_dashboard(user):
    if user.role == 'owner':
        return redirect(url_for('owner.dashboard'))
    elif user.role == 'manager':
        return redirect(url_for('manager.dashboard'))
    elif user.role == 'worker':
        return redirect(url_for('worker.dashboard'))
    return redirect(url_for('main.landing'))


def log_activity(user_id, action):
    try:
        log = ActivityLog(user_id=user_id, action=action)
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
