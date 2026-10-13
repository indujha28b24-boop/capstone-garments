from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import db, Order, ProductionTracking, Worker, Attendance, Performance, Alert, ActivityLog, QualityInspection

worker_bp = Blueprint('worker', __name__)

def worker_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'worker':
            flash('Access Denied: Worker login required.', 'danger')
            return redirect(url_for('auth.login_stitching'))
        return f(*args, **kwargs)
    return decorated_function

def log_action(action):
    try:
        log = ActivityLog(user_id=current_user.id, action=action)
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


@worker_bp.route('/dashboard')
@worker_required
def dashboard():
    worker_rec = Worker.query.filter_by(user_id=current_user.id).first()
    
    if not worker_rec:
        worker_rec = Worker.query.filter(Worker.name.ilike(f"%{current_user.username}%")).first()

    if not worker_rec:
        dept = current_user.department if current_user.department != 'Executive' else 'Stitching'
        worker_rec = Worker(
            user_id=current_user.id,
            name=current_user.username.capitalize(),
            department=dept,
            skill=f'{dept} Operations Specialist',
            attendance='Present'
        )
        db.session.add(worker_rec)
        db.session.commit()
        
        perf = Performance(worker_id=worker_rec.id, productivity_score=94.0, completed_tasks=18)
        db.session.add(perf)
        db.session.commit()

    dept = worker_rec.department

    # Department-scoped tasks: match current stage with worker department
    assigned_orders = Order.query.join(ProductionTracking).filter(
        ProductionTracking.stage == dept,
        Order.status != 'Delivered'
    ).all()

    if not assigned_orders:
        # Fallback to active orders for demo continuity
        assigned_orders = Order.query.filter(Order.status != 'Delivered').limit(5).all()

    today = datetime.utcnow().date()
    today_attendance = Attendance.query.filter_by(worker_id=worker_rec.id, date=today).first()
    perf = Performance.query.filter_by(worker_id=worker_rec.id).first()

    # Calculate Quality Inspection metrics from actual database records only (Tasks 4, 5, 6, 9)
    # Deduplicate by primary key ID to ensure no record is counted more than once (Task 9)
    all_inspections = QualityInspection.query.order_by(QualityInspection.inspected_at.desc()).all()
    seen_ids = set()
    unique_inspections = []
    for insp in all_inspections:
        if insp.id not in seen_ids:
            seen_ids.add(insp.id)
            unique_inspections.append(insp)

    total_inspected = sum(i.inspected_qty for i in unique_inspections)
    total_passed = sum(i.passed_qty for i in unique_inspections)
    total_defective = sum(i.defective_qty for i in unique_inspections)
    total_rework = sum(1 for i in unique_inspections if i.result == 'Rework Required')
    total_rejected = sum(1 for i in unique_inspections if i.result == 'Rejected')

    # Safe pass rate calculation: total passed / total inspected * 100 (Task 4)
    pass_rate = round((total_passed / total_inspected * 100.0), 1) if total_inspected > 0 else 0.0

    today_inspected = sum(
        i.inspected_qty for i in unique_inspections
        if i.inspected_at and i.inspected_at.date() == today
    )

    # Worker Performance & Targets
    worker_daily_target = 100
    if dept == 'Quality Check':
        # Sync Performance record with actual database totals
        if perf:
            perf.productivity_score = pass_rate
            perf.completed_tasks = total_inspected
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        worker_completed_today = today_inspected if today_inspected > 0 else total_inspected
    else:
        worker_completed_today = perf.completed_tasks if perf else 0

    worker_remaining = max(0, worker_daily_target - worker_completed_today)

    # Important Announcements: Do not show "QC Rework Required" or "QC Rejected" for zero defective units (Task 7)
    active_alerts = Alert.query.filter_by(status='Active').order_by(Alert.priority.desc(), Alert.created_at.desc()).all()
    announcements = []
    for ann in active_alerts:
        if ("QC Rework Required" in ann.message or "QC Rejected" in ann.message) and "0 defective units" in ann.message:
            continue
        announcements.append(ann)
        if len(announcements) == 3:
            break

    # Leaderboard (Top performers)
    top_performers = db.session.query(Worker, Performance)\
        .join(Performance, Worker.id == Performance.worker_id)\
        .order_by(Performance.productivity_score.desc()).limit(5).all()

    return render_template('worker/dashboard.html',
                           worker=worker_rec,
                           department=dept,
                           assigned_orders=assigned_orders,
                           today_attendance=today_attendance,
                           performance=perf,
                           worker_daily_target=worker_daily_target,
                           worker_completed_today=worker_completed_today,
                           worker_remaining=worker_remaining,
                           announcements=announcements,
                           top_performers=top_performers,
                           total_inspected=total_inspected,
                           total_passed=total_passed,
                           total_defective=total_defective,
                           total_rework=total_rework,
                           total_rejected=total_rejected,
                           pass_rate=pass_rate)


@worker_bp.route('/attendance/mark', methods=['POST'])
@worker_required
def mark_attendance():
    worker_rec = Worker.query.filter_by(user_id=current_user.id).first()
    status = request.form.get('attendance_status', 'Present')
    today = datetime.utcnow().date()

    existing = Attendance.query.filter_by(worker_id=worker_rec.id, date=today).first()
    if existing:
        existing.status = status
    else:
        att = Attendance(worker_id=worker_rec.id, date=today, status=status)
        db.session.add(att)

    worker_rec.attendance = status
    db.session.commit()

    log_action(f"Worker {current_user.username} logged attendance: {status}")
    flash(f'Attendance recorded as {status} for today.', 'success')
    return redirect(url_for('worker.dashboard'))


@worker_bp.route('/task/update', methods=['POST'])
@worker_required
def update_task_progress():
    order_id = int(request.form.get('order_id'))
    progress = int(request.form.get('progress_percentage'))
    action_type = request.form.get('action_type', 'progress')  # progress, defect, dispatch

    order = Order.query.get_or_404(order_id)
    worker_rec = Worker.query.filter_by(user_id=current_user.id).first()

    if action_type == 'defect':
        # Quality Check Defect Reporting
        defect_msg = request.form.get('defect_details', 'Minor stitching alignment defect detected.')
        alert = Alert(
            alert_type='Quality Defect',
            message=f"Defect flagged on Order #{order.id} ({order.garment_type}) by QA inspector {current_user.username}: {defect_msg}",
            priority='High',
            status='Active'
        )
        db.session.add(alert)
        log_action(f"QA Defect flagged by {current_user.username} on Order #{order.id}")
        flash(f'Quality Defect reported for Order #{order.id}. Floor Alert issued.', 'danger')

    elif action_type == 'dispatch':
        # Packing & Dispatch Confirmation
        order.tracking.stage = 'Delivered'
        order.tracking.progress_percentage = 100
        order.status = 'Delivered'
        log_action(f"Order #{order.id} dispatched by Packing Inspector {current_user.username}")
        flash(f'Order #{order.id} successfully marked as PACKED & DISPATCHED!', 'success')

    else:
        # Standard Cutting / Stitching / Quality Progress Update
        if order.tracking:
            order.tracking.progress_percentage = progress
            order.tracking.updated_date = datetime.utcnow()

            if progress >= 100:
                stage_flow = ['Order Confirmed', 'Fabric Received', 'Cutting', 'Stitching', 'Quality Check', 'Packing', 'Delivered']
                current_idx = stage_flow.index(order.tracking.stage) if order.tracking.stage in stage_flow else 0
                if current_idx < len(stage_flow) - 1:
                    next_stage = stage_flow[current_idx + 1]
                    order.tracking.stage = next_stage
                    order.tracking.progress_percentage = 15
                    flash(f'Order #{order.id} reached 100% at {stage_flow[current_idx]}! Advanced to {next_stage}.', 'success')

        log_action(f"Worker {current_user.username} updated Order #{order.id} to {progress}%")
        flash(f'Order #{order.id} progress updated to {progress}%.', 'success')

    # Update worker metrics
    if worker_rec:
        perf = Performance.query.filter_by(worker_id=worker_rec.id).first()
        if perf:
            perf.completed_tasks += 1
            perf.productivity_score = min(100.0, perf.productivity_score + 0.5)

    db.session.commit()
    return redirect(url_for('worker.dashboard'))


# ─── QUALITY INSPECTION FORM (Quality Check Workers) ───────────────────────
@worker_bp.route('/quality-inspect', methods=['GET', 'POST'])
@worker_required
def quality_inspect():
    """Quality Check worker inspection form."""
    # Ensure active orders are available for quality inspection, with Quality Check stage orders first (Task 6)
    qc_orders = Order.query.join(ProductionTracking).filter(
        ProductionTracking.stage == 'Quality Check',
        Order.status != 'Delivered'
    ).all()
    other_active = Order.query.filter(
        Order.status != 'Delivered',
        ~Order.id.in_([o.id for o in qc_orders])
    ).all()
    orders_in_qc = qc_orders + other_active
    if not orders_in_qc:
        orders_in_qc = Order.query.all()

    selected_order = None
    order_id_param = request.args.get('order_id') or request.form.get('order_id')
    if order_id_param:
        try:
            selected_order = Order.query.get(int(order_id_param))
        except (ValueError, TypeError):
            selected_order = None
    if not selected_order and orders_in_qc:
        selected_order = orders_in_qc[0]

    if request.method == 'POST' and request.form.get('submit_inspection'):
        try:
            order_id = int(request.form.get('order_id'))
            inspected_qty = int(request.form.get('inspected_qty', 0))
            passed_qty = int(request.form.get('passed_qty', 0))
            defective_qty = int(request.form.get('defective_qty', 0))
            defect_type = request.form.get('defect_type') or None
            remarks = request.form.get('remarks') or None
            result = request.form.get('result', 'Passed')

            # Validation tasks (Tasks 2, 3):
            # inspected_quantity >= 0, passed_quantity >= 0, defective_quantity >= 0
            # passed_quantity + defective_quantity <= inspected_quantity
            if inspected_qty < 0 or passed_qty < 0 or defective_qty < 0:
                flash('Quantities must be non-negative (>= 0).', 'danger')
                return redirect(url_for('worker.quality_inspect', order_id=order_id))

            if inspected_qty == 0:
                flash('Inspected quantity must be greater than zero to record an inspection.', 'warning')
                return redirect(url_for('worker.quality_inspect', order_id=order_id))

            if (passed_qty + defective_qty) > inspected_qty:
                flash(f'Passed quantity ({passed_qty}) + Defective quantity ({defective_qty}) cannot exceed Inspected quantity ({inspected_qty}).', 'danger')
                return redirect(url_for('worker.quality_inspect', order_id=order_id))

            insp = QualityInspection(
                order_id=order_id,
                inspector_id=current_user.id,
                inspector_name=current_user.username,
                inspected_qty=inspected_qty,
                passed_qty=passed_qty,
                defective_qty=defective_qty,
                defect_type=defect_type,
                remarks=remarks,
                result=result,
            )
            db.session.add(insp)

            # Announcement logic (Task 7):
            # Do not show "QC Rework Required" for zero defective units unless another valid rework condition exists
            if insp.result in ('Rework Required', 'Rejected'):
                if insp.result == 'Rework Required' and insp.defective_qty == 0:
                    # No alert generated for 0 defective units without valid defect reason
                    pass
                elif insp.defective_qty > 0:
                    alert = Alert(
                        alert_type='Quality Defect',
                        message=(f"QC {insp.result}: Order #{insp.order_id} — "
                                 f"{insp.defective_qty} defective units. "
                                 f"Defect: {insp.defect_type or 'N/A'}. "
                                 f"Inspector: {insp.inspector_name}"),
                        priority='High',
                        status='Active'
                    )
                    db.session.add(alert)
                elif insp.defect_type:
                    alert = Alert(
                        alert_type='Quality Defect',
                        message=(f"QC {insp.result}: Order #{insp.order_id} — "
                                 f"Defect: {insp.defect_type}. "
                                 f"Inspector: {insp.inspector_name}"),
                        priority='High',
                        status='Active'
                    )
                    db.session.add(alert)

            # Sync worker performance metrics immediately (Task 8)
            worker_rec = Worker.query.filter_by(user_id=current_user.id).first()
            if not worker_rec:
                worker_rec = Worker.query.filter(Worker.name.ilike(f"%{current_user.username}%")).first()
            if worker_rec:
                perf = Performance.query.filter_by(worker_id=worker_rec.id).first()
                if perf:
                    db.session.flush()
                    all_insp = QualityInspection.query.all()
                    tot_insp = sum(i.inspected_qty for i in all_insp)
                    tot_pass = sum(i.passed_qty for i in all_insp)
                    perf.completed_tasks = tot_insp
                    perf.productivity_score = round((tot_pass / tot_insp * 100.0), 1) if tot_insp > 0 else 0.0

            db.session.commit()
            log_action(f"Quality Inspection submitted for Order #{insp.order_id} — Result: {insp.result}")
            flash(f'Inspection recorded for Order #{insp.order_id}. Result: {insp.result}', 'success')
            return redirect(url_for('worker.quality_inspect', order_id=insp.order_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving inspection: {str(e)}', 'danger')

    # Calculate actual totals from database records only (Tasks 4, 5, 8, 9)
    all_inspections = QualityInspection.query.order_by(QualityInspection.inspected_at.desc()).all()
    seen_ids = set()
    unique_inspections = []
    for insp in all_inspections:
        if insp.id not in seen_ids:
            seen_ids.add(insp.id)
            unique_inspections.append(insp)

    total_inspected = sum(i.inspected_qty for i in unique_inspections)
    total_passed = sum(i.passed_qty for i in unique_inspections)
    total_defective = sum(i.defective_qty for i in unique_inspections)
    total_rework = sum(1 for i in unique_inspections if i.result == 'Rework Required')
    total_rejected = sum(1 for i in unique_inspections if i.result == 'Rejected')
    pass_rate = round((total_passed / total_inspected * 100.0), 1) if total_inspected > 0 else 0.0

    recent_inspections = unique_inspections[:15]

    return render_template('worker/quality_inspect.html',
                           orders_in_qc=orders_in_qc,
                           selected_order=selected_order,
                           recent_inspections=recent_inspections,
                           total_inspected=total_inspected,
                           total_passed=total_passed,
                           total_defective=total_defective,
                           total_rework=total_rework,
                           total_rejected=total_rejected,
                           pass_rate=pass_rate)
