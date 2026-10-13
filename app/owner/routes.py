import os
import qrcode
from io import BytesIO
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from app.models import db, User, Customer, Order, ProductionTracking, Worker, Manager, Inventory, Machine, Attendance, Performance, Alert, AIPrediction, QRTracking, ActivityLog, OrderSizeQuantity, ProductionDelay, QualityInspection, OnlineOrderRequest, ProductionCost, SampleMonthlyFinancial
from app.ai.engine import AIEngine
from app.reports.generator import ReportGenerator

owner_bp = Blueprint('owner', __name__)

def owner_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'owner':
            flash('Unauthorized access: Owner administrative privileges required.', 'danger')
            return redirect(url_for('auth.login_owner'))
        return f(*args, **kwargs)
    return decorated_function

def log_activity(activity):
    try:
        log = ActivityLog(user_id=current_user.id, action=activity)
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


# -------------------------------------------------------------
# DASHBOARD
# -------------------------------------------------------------
@owner_bp.route('/dashboard')
@owner_required
def dashboard():
    total_orders = Order.query.count()
    active_orders = Order.query.filter(Order.status != 'Delivered').count()
    completed_orders = Order.query.filter_by(status='Delivered').count()
    
    # Calculate delayed orders
    now = datetime.utcnow()
    delayed_orders = Order.query.filter(Order.status != 'Delivered', Order.deadline < now).count()

    # Revenue calculation (assuming avg unit price ₹25)
    total_revenue = sum(o.quantity * 25 for o in Order.query.all())
    
    available_workers = Worker.query.filter_by(status='Available').count()
    total_workers = Worker.query.count()
    
    running_machines = Machine.query.filter_by(status='Running').count()
    total_machines = Machine.query.count()
    
    low_inventory_count = Inventory.query.filter(Inventory.quantity <= Inventory.minimum_stock).count()
    active_alerts = Alert.query.filter_by(status='Active').order_by(Alert.id.desc()).limit(5).all()

    # Additional Owner Overview Metrics
    pending_orders = Order.query.filter_by(status='Order Confirmed').count()
    
    # Production Overview
    # For a simple representation, calculate based on delivered orders or progress
    # Here we mock today and monthly based on Delivered status for simplicity
    today_dt = datetime.utcnow().date()
    today_production = sum(o.quantity for o in Order.query.filter_by(status='Delivered').all() if o.tracking and o.tracking.updated_date.date() == today_dt)
    monthly_production = sum(o.quantity for o in Order.query.filter_by(status='Delivered').all() if o.tracking and o.tracking.updated_date.month == today_dt.month)
    production_target = 10000  # Default monthly target

    # Attendance Overview
    present_workers = Attendance.query.filter_by(date=today_dt, status='Present').count()
    absent_workers = Attendance.query.filter_by(date=today_dt, status='Absent').count()
    leave_workers = Attendance.query.filter_by(date=today_dt, status='Leave').count()
    
    # Fallback to total workers if no attendance marked yet
    total_att = present_workers + absent_workers + leave_workers
    if total_att == 0:
        attendance_percent = 100
        present_workers = Worker.query.count()
    else:
        attendance_percent = int((present_workers / max(1, total_workers)) * 100)

    # Department Performance (Active orders in each stage)
    dept_cutting = ProductionTracking.query.filter_by(stage='Cutting').count()
    dept_stitching = ProductionTracking.query.filter_by(stage='Stitching').count()
    dept_quality = ProductionTracking.query.filter_by(stage='Quality Check').count()
    dept_packing = ProductionTracking.query.filter_by(stage='Packing').count()

    # AI Recommendations
    ai_recommendations = AIEngine.generate_ai_assistant_recommendations()

    # Dynamic Owner Critical Alerts
    owner_critical_alerts = []
    
    # 1. Urgent Order / Approaching Delivery Deadline
    active_orders_list = Order.query.filter(Order.status != 'Delivered').all()
    for o in active_orders_list:
        if o.smart_priority == 'URGENT':
            owner_critical_alerts.append({
                'level': 'Critical',
                'icon': '🔴',
                'message': f"Order #{o.id} ({o.garment_type}) delivery deadline approaching (Deadline: {o.deadline.strftime('%Y-%m-%d')})"
            })
            
    # 2. Low Inventory
    low_stock_items = Inventory.query.filter(Inventory.quantity <= Inventory.minimum_stock).all()
    for item in low_stock_items:
        owner_critical_alerts.append({
            'level': 'Warning',
            'icon': '🟠',
            'message': f"{item.item_name} ({item.category}) stock is low ({item.quantity} {item.unit} remaining)"
        })
        
    # 3. Machine Maintenance / Machine Issue
    maintenance_machines = Machine.query.filter_by(status='Maintenance').all()
    for m in maintenance_machines:
        owner_critical_alerts.append({
            'level': 'Attention',
            'icon': '🟡',
            'message': f"Machine {m.machine_name} ({m.machine_type}) requires maintenance / not running"
        })
        
    # 4. Production Delay
    delayed_orders_list = Order.query.filter_by(status='Delayed').all()
    for o in delayed_orders_list:
        owner_critical_alerts.append({
            'level': 'Critical',
            'icon': '🔴',
            'message': f"Production for Order #{o.id} is delayed"
        })

    # Owner Costs (N/A fallback according to prompt rule)
    owner_costs = {
        'today_cost': 'N/A',
        'material_cost': 'N/A',
        'labour_cost': 'N/A',
        'machine_cost': 'N/A',
        'estimated_order_cost': 'N/A'
    }

    # Recent Orders
    recent_orders = Order.query.order_by(Order.id.desc()).limit(6).all()

    return render_template('owner/dashboard.html',
                           total_orders=total_orders,
                           active_orders=active_orders,
                           completed_orders=completed_orders,
                           delayed_orders=delayed_orders,
                           total_revenue=total_revenue,
                           available_workers=available_workers,
                           total_workers=total_workers,
                           running_machines=running_machines,
                           total_machines=total_machines,
                           low_inventory_count=low_inventory_count,
                           active_alerts=active_alerts,
                           pending_orders=pending_orders,
                           today_production=today_production,
                           monthly_production=monthly_production,
                           production_target=production_target,
                           present_workers=present_workers,
                           absent_workers=absent_workers,
                           leave_workers=leave_workers,
                           attendance_percent=attendance_percent,
                           dept_cutting=dept_cutting,
                           dept_stitching=dept_stitching,
                           dept_quality=dept_quality,
                           dept_packing=dept_packing,
                           ai_recommendations=ai_recommendations,
                           owner_critical_alerts=owner_critical_alerts,
                           owner_costs=owner_costs,
                           recent_orders=recent_orders)


# -------------------------------------------------------------
# USER MANAGEMENT (MANAGERS & WORKERS)
# -------------------------------------------------------------
@owner_bp.route('/users')
@owner_required
def users_manage():
    managers = Manager.query.all()
    workers = Worker.query.all()
    users_list = User.query.order_by(User.id.desc()).all()
    return render_template('owner/users_manage.html', managers=managers, workers=workers, users=users_list)

@owner_bp.route('/users/add', methods=['POST'])
@owner_required
def user_add():
    username = request.form.get('username').strip()
    password = request.form.get('password')
    role = request.form.get('role')
    name = request.form.get('name').strip()
    department = request.form.get('department')
    contact = request.form.get('contact')
    skill = request.form.get('skill', 'General Sewing')

    if User.query.filter_by(username=username).first():
        flash(f'Username "{username}" is already taken.', 'danger')
        return redirect(url_for('owner.users_manage'))

    user = User(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    if role == 'manager':
        mgr = Manager(user_id=user.id, name=name, department=department, contact=contact)
        db.session.add(mgr)
    elif role == 'worker':
        wrk = Worker(user_id=user.id, name=name, department=department, skill=skill, contact=contact, status='Available')
        db.session.add(wrk)
        # Create initial performance record
        perf = Performance(worker_id=wrk.id, productivity_score=88.5, completed_tasks=12)
        db.session.add(perf)

    db.session.commit()
    log_activity(f"Created new {role} user account: {username} ({name})")
    flash(f'User {name} ({role}) successfully added.', 'success')
    return redirect(url_for('owner.users_manage'))


# -------------------------------------------------------------
# ORDER MANAGEMENT
# -------------------------------------------------------------
@owner_bp.route('/orders')
@owner_required
def orders_manage():
    orders = Order.query.order_by(Order.id.desc()).all()
    customers = Customer.query.all()
    return render_template('owner/orders_manage.html', orders=orders, customers=customers)

@owner_bp.route('/orders/add', methods=['POST'])
@owner_required
def order_add():
    customer_id = request.form.get('customer_id')
    garment_type = request.form.get('garment_type')
    quantity = int(request.form.get('quantity'))
    deadline_str = request.form.get('deadline')
    deadline = datetime.strptime(deadline_str, '%Y-%m-%d')

    qty_s = request.form.get('qty_s')
    qty_m = request.form.get('qty_m')
    qty_l = request.form.get('qty_l')
    qty_xl = request.form.get('qty_xl')

    if qty_s or qty_m or qty_l or qty_xl:
        s_val = int(qty_s) if qty_s else 0
        m_val = int(qty_m) if qty_m else 0
        l_val = int(qty_l) if qty_l else 0
        xl_val = int(qty_xl) if qty_xl else 0

        if s_val < 0 or m_val < 0 or l_val < 0 or xl_val < 0:
            flash("Size quantities cannot be negative.", "danger")
            return redirect(url_for('owner.orders_manage'))

        if (s_val + m_val + l_val + xl_val) != quantity:
            flash(f"Sum of size quantities ({s_val + m_val + l_val + xl_val}) must equal total order quantity ({quantity}).", "danger")
            return redirect(url_for('owner.orders_manage'))
    else:
        s_val = quantity // 4
        m_val = quantity // 4
        l_val = quantity // 4
        xl_val = quantity - (s_val + m_val + l_val)

    order = Order(
        customer_id=customer_id,
        garment_type=garment_type,
        quantity=quantity,
        deadline=deadline,
        status='In Production'
    )
    db.session.add(order)
    db.session.commit()

    # Create OrderSizeQuantity records
    db.session.add(OrderSizeQuantity(order_id=order.id, size='S', planned_quantity=s_val, completed_quantity=0))
    db.session.add(OrderSizeQuantity(order_id=order.id, size='M', planned_quantity=m_val, completed_quantity=0))
    db.session.add(OrderSizeQuantity(order_id=order.id, size='L', planned_quantity=l_val, completed_quantity=0))
    db.session.add(OrderSizeQuantity(order_id=order.id, size='XL', planned_quantity=xl_val, completed_quantity=0))
    db.session.commit()

    # Production Tracking initial stage
    tracking = ProductionTracking(order_id=order.id, stage='Order Confirmed', progress_percentage=10)
    db.session.add(tracking)
    db.session.commit()

    # Generate QR Code image
    tracking_id = f"TRK-{1000 + order.id}"
    qr_filename = f"order_{order.id}.png"
    qr_folder = current_app.config['QR_FOLDER']
    os.makedirs(qr_folder, exist_ok=True)
    qr_full_path = os.path.join(qr_folder, qr_filename)
    
    tracking_url = current_app.config['QR_BASE_URL'].rstrip('/') + url_for('main.track_order', tracking_id=tracking_id)
    img = qrcode.make(tracking_url)
    img.save(qr_full_path)

    qr_rec = QRTracking(order_id=order.id, tracking_id=tracking_id, qr_code_path=f"qrcodes/{qr_filename}")
    db.session.add(qr_rec)
    db.session.commit()

    log_activity(f"Created Order #{order.id} for {quantity} {garment_type}")
    flash(f'Order #{order.id} created successfully with active QR Tracking.', 'success')
    return redirect(url_for('owner.orders_manage'))

@owner_bp.route('/orders/stage/update', methods=['POST'])
@owner_required
def order_stage_update():
    order_id = int(request.form.get('order_id'))
    stage = request.form.get('stage')
    progress = int(request.form.get('progress_percentage'))

    order = Order.query.get_or_404(order_id)
    if not order.tracking:
        order.tracking = ProductionTracking(order_id=order.id)

    order.tracking.stage = stage
    order.tracking.progress_percentage = progress
    order.tracking.updated_date = datetime.utcnow()

    if stage == 'Delivered' or progress == 100:
        order.status = 'Delivered'
    else:
        order.status = 'In Production'

    db.session.commit()
    log_activity(f"Updated Order #{order.id} stage to {stage} ({progress}%)")
    flash(f'Order #{order.id} stage updated to {stage}.', 'info')
    return redirect(url_for('owner.orders_manage'))

@owner_bp.route('/orders/delete/<int:order_id>', methods=['POST'])
@owner_required
def order_delete(order_id):
    order = Order.query.get_or_404(order_id)
    db.session.delete(order)
    db.session.commit()
    log_activity(f"Deleted Order #{order_id}")
    flash(f'Order #{order_id} deleted.', 'warning')
    return redirect(url_for('owner.orders_manage'))


# -------------------------------------------------------------
# INVENTORY MANAGEMENT
# -------------------------------------------------------------
@owner_bp.route('/inventory')
@owner_required
def inventory_manage():
    inventory_items = Inventory.query.order_by(Inventory.category).all()
    return render_template('owner/inventory_manage.html', inventory=inventory_items)

@owner_bp.route('/inventory/add', methods=['POST'])
@owner_required
def inventory_add():
    item_name = request.form.get('item_name').strip()
    category = request.form.get('category')
    quantity = float(request.form.get('quantity'))
    unit = request.form.get('unit')
    minimum_stock = float(request.form.get('minimum_stock'))

    item = Inventory(
        item_name=item_name,
        category=category,
        quantity=quantity,
        unit=unit,
        minimum_stock=minimum_stock
    )
    db.session.add(item)
    db.session.commit()
    log_activity(f"Added inventory item: {item_name} ({quantity} {unit})")
    flash(f'Inventory item "{item_name}" added.', 'success')
    return redirect(url_for('owner.inventory_manage'))

@owner_bp.route('/inventory/update', methods=['POST'])
@owner_required
def inventory_update():
    item_id = int(request.form.get('item_id'))
    add_qty = float(request.form.get('additional_quantity'))

    item = Inventory.query.get_or_404(item_id)
    item.quantity += add_qty
    db.session.commit()

    log_activity(f"Restocked {item.item_name} by +{add_qty} {item.unit}. New total: {item.quantity}")
    flash(f'Restocked {item.item_name} by +{add_qty} {item.unit}.', 'success')
    return redirect(url_for('owner.inventory_manage'))


# -------------------------------------------------------------
# MACHINE MANAGEMENT
# -------------------------------------------------------------
@owner_bp.route('/machines')
@owner_required
def machines_manage():
    machines = Machine.query.all()
    return render_template('owner/machines_manage.html', machines=machines)

@owner_bp.route('/machines/add', methods=['POST'])
@owner_required
def machine_add():
    machine_name = request.form.get('machine_name').strip()
    machine_type = request.form.get('machine_type')
    status = request.form.get('status')
    
    m = Machine(machine_name=machine_name, machine_type=machine_type, status=status, maintenance_date=datetime.utcnow() + timedelta(days=30))
    db.session.add(m)
    db.session.commit()
    log_activity(f"Added new machine: {machine_name} ({machine_type})")
    flash(f'Machine "{machine_name}" registered.', 'success')
    return redirect(url_for('owner.machines_manage'))

@owner_bp.route('/machines/status', methods=['POST'])
@owner_required
def machine_status_update():
    machine_id = int(request.form.get('machine_id'))
    status = request.form.get('status')
    
    m = Machine.query.get_or_404(machine_id)
    m.status = status
    if status == 'Maintenance':
        m.maintenance_date = datetime.utcnow()
    db.session.commit()
    log_activity(f"Updated status for machine {m.machine_name} to {status}")
    flash(f'Machine status for {m.machine_name} updated to {status}.', 'info')
    return redirect(url_for('owner.machines_manage'))


# -------------------------------------------------------------
# ANALYTICS & CHART.JS DATA
# -------------------------------------------------------------
@owner_bp.route('/analytics')
@owner_required
def analytics():
    return render_template('owner/analytics.html')

@owner_bp.route('/api/analytics-data')
@owner_required
def api_analytics_data():
    # Monthly orders breakdown (last 6 months demo)
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul']
    monthly_orders = [45, 52, 68, 74, 85, 92, Order.query.count()]
    monthly_revenue = [val * 1250 for val in monthly_orders]
    
    # Stage breakdown
    stages = ['Order Confirmed', 'Fabric Received', 'Cutting', 'Stitching', 'Quality Check', 'Packing', 'Delivered']
    stage_counts = []
    for stg in stages:
        count = ProductionTracking.query.filter_by(stage=stg).count()
        stage_counts.append(count)

    # Machine status count
    machine_statuses = ['Running', 'Idle', 'Maintenance']
    machine_counts = [Machine.query.filter_by(status=st).count() for st in machine_statuses]

    # Delay reasons breakdown
    delay_reasons = [
        'Machine Breakdown',
        'Material/Fabric Shortage',
        'Worker Shortage',
        'Quality/Rework Issue',
        'Power/Infrastructure Issue',
        'Customer Order Modification',
        'Other'
    ]
    delay_counts = [ProductionDelay.query.filter_by(reason=r).count() for r in delay_reasons]

    return jsonify({
        'months': months,
        'monthly_orders': monthly_orders,
        'monthly_revenue': monthly_revenue,
        'stages': stages,
        'stage_counts': stage_counts,
        'machine_statuses': machine_statuses,
        'machine_counts': machine_counts,
        'delay_reasons': delay_reasons,
        'delay_counts': delay_counts
    })


# -------------------------------------------------------------
# REPORTS EXPORT
# -------------------------------------------------------------
@owner_bp.route('/reports')
@owner_required
def reports():
    return render_template('owner/reports.html')

@owner_bp.route('/reports/download/<report_type>/<fmt>')
@owner_required
def report_download(report_type, fmt):
    if report_type == 'production':
        if fmt == 'pdf':
            pdf_bytes = ReportGenerator.generate_production_pdf()
            return send_file(
                BytesIO(pdf_bytes),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'production_report_{datetime.utcnow().strftime("%Y%m%d")}.pdf'
            )
        elif fmt == 'excel':
            excel_bytes = ReportGenerator.generate_production_excel()
            return send_file(
                BytesIO(excel_bytes),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'production_report_{datetime.utcnow().strftime("%Y%m%d")}.xlsx'
            )
    elif report_type == 'inventory':
        if fmt == 'pdf':
            pdf_bytes = ReportGenerator.generate_inventory_pdf()
            return send_file(
                BytesIO(pdf_bytes),
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'inventory_report_{datetime.utcnow().strftime("%Y%m%d")}.pdf'
            )
        elif fmt == 'excel':
            excel_bytes = ReportGenerator.generate_inventory_excel()
            return send_file(
                BytesIO(excel_bytes),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'inventory_report_{datetime.utcnow().strftime("%Y%m%d")}.xlsx'
            )
            
    flash('Invalid report parameters.', 'danger')
    return redirect(url_for('owner.reports'))


# -------------------------------------------------------------
# ACTIVITY LOGS
# -------------------------------------------------------------
@owner_bp.route('/activity-logs')
@owner_required
def activity_logs():
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(100).all()
    return render_template('owner/activity_logs.html', logs=logs)


# -------------------------------------------------------------
# AI ESTIMATOR APIS FOR DYNAMIC MODAL CALCULATORS
# -------------------------------------------------------------
@owner_bp.route('/api/ai/fabric', methods=['POST'])
@owner_required
def api_ai_fabric():
    data = request.json or {}
    garment_type = data.get('garment_type', 'Shirts')
    quantity = int(data.get('quantity', 500))
    res = AIEngine.predict_fabric_requirement(garment_type, quantity)
    return jsonify(res)

@owner_bp.route('/api/ai/workforce', methods=['POST'])
@owner_required
def api_ai_workforce():
    data = request.json or {}
    garment_type = data.get('garment_type', 'Shirts')
    quantity = int(data.get('quantity', 500))
    deadline_days = int(data.get('deadline_days', 7))
    res = AIEngine.predict_workforce_requirement(garment_type, quantity, deadline_days)
    return jsonify(res)


@owner_bp.route('/fashion-trend-intelligence')
@owner_required
def fashion_trend_intelligence():
    trend_data = AIEngine.get_fashion_trend_intelligence()
    return render_template('owner/fashion_trend_intelligence.html', trend_data=trend_data)

# -------------------------------------------------------------
# BILLING & INVOICES
# -------------------------------------------------------------
from app.models import Invoice

@owner_bp.route('/billing')
@owner_required
def billing_manage():
    invoices = Invoice.query.order_by(Invoice.created_at.desc()).all()
    orders = Order.query.filter(~Order.id.in_([i.order_id for i in invoices])).all()
    total_invoices = len(invoices)
    total_billed = sum(i.total_amount for i in invoices)
    paid_amount = sum(i.total_amount for i in invoices if i.payment_status == 'Paid')
    pending_amount = total_billed - paid_amount
    return render_template('billing/billing_manage.html', invoices=invoices, orders=orders, total_invoices=total_invoices, total_billed=total_billed, paid_amount=paid_amount, pending_amount=pending_amount)

@owner_bp.route('/billing/create', methods=['POST'])
@owner_required
def billing_create():
    order_id = request.form.get('order_id')
    subtotal = float(request.form.get('subtotal', 0))
    additional_charges = float(request.form.get('additional_charges', 0))
    discount = float(request.form.get('discount', 0))
    tax_percentage = float(request.form.get('tax_percentage', 0))
    
    order = Order.query.get_or_404(order_id)
    if Invoice.query.filter_by(order_id=order.id).first():
        flash('An invoice already exists for this order.', 'danger')
        return redirect(url_for('owner.billing_manage'))
    
    taxable = subtotal + additional_charges - discount
    tax_amount = taxable * (tax_percentage / 100.0)
    grand_total = taxable + tax_amount
    
    year = datetime.utcnow().year
    count = Invoice.query.count() + 1
    invoice_number = f"INV-{year}-{count:04d}"
    
    invoice = Invoice(
        invoice_number=invoice_number,
        order_id=order.id,
        customer_id=order.customer_id,
        subtotal=subtotal,
        additional_charges=additional_charges,
        discount=discount,
        tax_percentage=tax_percentage,
        tax_amount=tax_amount,
        total_amount=grand_total
    )
    db.session.add(invoice)
    db.session.commit()
    log_activity(f"Created Invoice {invoice_number} for Order #{order.id}")
    flash('Invoice created successfully.', 'success')
    return redirect(url_for('owner.billing_manage'))

@owner_bp.route('/billing/update/<int:invoice_id>', methods=['POST'])
@owner_required
def billing_update_status(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    new_status = request.form.get('payment_status')
    if new_status in ['Pending', 'Paid', 'Partially Paid']:
        invoice.payment_status = new_status
        db.session.commit()
        log_activity(f"Updated Payment Status for {invoice.invoice_number} to {new_status}")
        flash('Payment status updated.', 'success')
    return redirect(url_for('owner.billing_manage'))

@owner_bp.route('/billing/<int:invoice_id>')
@owner_required
def billing_view(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('billing/billing_view.html', invoice=invoice)

@owner_bp.route('/billing/<int:invoice_id>/pdf')
@owner_required
def billing_pdf(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    from app.billing_pdf import generate_invoice_pdf
    from flask import send_file
    buffer = generate_invoice_pdf(invoice)
    return send_file(buffer, as_attachment=True, download_name=f"{invoice.invoice_number}.pdf", mimetype='application/pdf')



# ─── QUALITY INSPECTION DASHBOARD ────────────────────────────────────────────
@owner_bp.route('/quality-inspection')
@owner_required
def quality_inspection():
    """Owner read-only Quality Control Dashboard."""
    all_inspections = QualityInspection.query.order_by(QualityInspection.inspected_at.desc()).all()

    total_inspected = sum(i.inspected_qty for i in all_inspections)
    total_passed    = sum(i.passed_qty    for i in all_inspections)
    total_rework    = sum(1 for i in all_inspections if i.result == 'Rework Required')
    total_rejected  = sum(1 for i in all_inspections if i.result == 'Rejected')

    pass_rate = round((total_passed / total_inspected * 100) if total_inspected > 0 else 0, 1)

    defect_types = [
        'Stitching Defect', 'Fabric Defect', 'Measurement/Size Issue',
        'Color Issue', 'Button/Zipper Issue', 'Other'
    ]
    defect_breakdown = {}
    for dt in defect_types:
        defect_breakdown[dt] = sum(
            i.defective_qty for i in all_inspections
            if i.defect_type == dt and i.defective_qty
        )
    max_defect = max(defect_breakdown.values()) if any(defect_breakdown.values()) else 1

    orders_in_qc = Order.query.join(ProductionTracking).filter(
        ProductionTracking.stage == 'Quality Check'
    ).all()

    return render_template('owner/quality_inspection.html',
                           inspections=all_inspections[:20],
                           total_inspected=total_inspected,
                           total_passed=total_passed,
                           total_rework=total_rework,
                           total_rejected=total_rejected,
                           pass_rate=pass_rate,
                           defect_breakdown=defect_breakdown,
                           max_defect=max_defect,
                           orders_in_qc=orders_in_qc)



# =============================================================
# ONLINE ORDER REQUESTS -- Owner routes
# =============================================================

@owner_bp.route('/online-orders')
@owner_required
def online_orders():
    """Owner: view dashboard of all online order requests."""
    all_requests = OnlineOrderRequest.query.order_by(OnlineOrderRequest.submitted_at.desc()).all()
    total = len(all_requests)
    pending = sum(1 for r in all_requests if r.status == 'PENDING')
    accepted = sum(1 for r in all_requests if r.status in ['ACCEPTED', 'APPROVED'])
    rejected = sum(1 for r in all_requests if r.status == 'REJECTED')
    return render_template('owner/online_orders.html',
                           requests=all_requests,
                           total=total, pending=pending,
                           accepted=accepted, approved=accepted,
                           rejected=rejected)


@owner_bp.route('/online-orders/<int:req_id>')
@owner_required
def online_order_detail(req_id):
    """Owner: view detail of a single online order request."""
    req = OnlineOrderRequest.query.get_or_404(req_id)
    return render_template('owner/online_order_detail.html', req=req)


@owner_bp.route('/online-orders/<int:req_id>/accept', methods=['POST'])
@owner_bp.route('/online-orders/<int:req_id>/approve', methods=['POST'])
@owner_required
def online_order_accept(req_id):
    """Owner: accept a pending customer order and create a production order atomically."""
    req = OnlineOrderRequest.query.get_or_404(req_id)

    if req.status != 'PENDING':
        flash('Cannot accept: Request is already ' + req.display_status + '.', 'danger')
        return redirect(url_for('owner.online_order_detail', req_id=req_id))
    if req.converted_order_id:
        flash('Cannot accept: A production order already exists for this request.', 'danger')
        return redirect(url_for('owner.online_order_detail', req_id=req_id))

    try:
        from datetime import datetime as _dt
        deadline = _dt.combine(req.required_delivery_date, _dt.min.time())
        order = Order(
            customer_id=req.customer_id,
            garment_type=req.garment_type,
            quantity=req.quantity,
            deadline=deadline,
            status='Order Confirmed'
        )
        db.session.add(order)
        db.session.flush()

        db.session.add(OrderSizeQuantity(order_id=order.id, size='S', planned_quantity=req.size_s, completed_quantity=0))
        db.session.add(OrderSizeQuantity(order_id=order.id, size='M', planned_quantity=req.size_m, completed_quantity=0))
        db.session.add(OrderSizeQuantity(order_id=order.id, size='L', planned_quantity=req.size_l, completed_quantity=0))
        db.session.add(OrderSizeQuantity(order_id=order.id, size='XL', planned_quantity=req.size_xl, completed_quantity=0))

        tracking = ProductionTracking(order_id=order.id, stage='Order Confirmed', progress_percentage=10)
        db.session.add(tracking)

        tid = 1000 + order.id
        tracking_id = 'TRK-' + str(tid)
        qr_filename = 'order_' + str(order.id) + '.png'
        qr_folder = current_app.config['QR_FOLDER']
        os.makedirs(qr_folder, exist_ok=True)
        qr_full_path = os.path.join(qr_folder, qr_filename)
        tracking_url = current_app.config['QR_BASE_URL'].rstrip('/') + url_for('main.track_order', tracking_id=tracking_id)
        img = qrcode.make(tracking_url)
        img.save(qr_full_path)
        qr_rec = QRTracking(order_id=order.id, tracking_id=tracking_id, qr_code_path='qrcodes/' + qr_filename)
        db.session.add(qr_rec)

        req.status = 'ACCEPTED'
        req.reviewed_at = datetime.utcnow()
        req.reviewed_by = current_user.id
        req.converted_order_id = order.id
        db.session.commit()

        log_activity('Accepted Customer Order ' + req.request_number + ' -> Production Order #' + str(order.id))
        flash('Customer order accepted successfully and added to Garment Orders.', 'success')

    except Exception as e:
        db.session.rollback()
        flash('Accept failed: ' + str(e), 'danger')

    return redirect(url_for('owner.online_order_detail', req_id=req_id))

# Backward compatible alias
online_order_approve = online_order_accept


@owner_bp.route('/online-orders/<int:req_id>/reject', methods=['POST'])
@owner_required
def online_order_reject(req_id):
    """Owner: reject a pending online order request."""
    req = OnlineOrderRequest.query.get_or_404(req_id)

    if req.status != 'PENDING':
        flash('Cannot reject: Request is already ' + req.display_status + '.', 'danger')
        return redirect(url_for('owner.online_order_detail', req_id=req_id))

    rejection_reason = request.form.get('rejection_reason', '').strip()
    req.status = 'REJECTED'
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by = current_user.id
    req.rejection_reason = rejection_reason or None
    db.session.commit()

    log_activity('Rejected Customer Order ' + req.request_number)
    flash('Customer order rejected.', 'warning')
    return redirect(url_for('owner.online_orders'))


# =====================================================================
# FINANCIAL ANALYTICS — OWNER ONLY
# Revenue, Production Cost, Profit & Loss Analysis
# =====================================================================

from app.billing_pdf import format_inr as _fmt_inr
from calendar import month_abbr

SAMPLE_HISTORICAL_FINANCIALS = [
    # (year, month, revenue, fabric_cost, labour_cost, machine_cost, other_cost)
    # 2025: 12 months
    (2025, 1, 450000.0, 195000.0, 110000.0, 50000.0, 25000.0),   # Total Cost: 380,000 -> Profit: 70,000
    (2025, 2, 420000.0, 230000.0, 130000.0, 55000.0, 30000.0),   # Total Cost: 445,000 -> Loss: 25,000 (Loss 1)
    (2025, 3, 510000.0, 210000.0, 120000.0, 60000.0, 30000.0),   # Total Cost: 420,000 -> Profit: 90,000
    (2025, 4, 480000.0, 205000.0, 115000.0, 50000.0, 25000.0),   # Total Cost: 395,000 -> Profit: 85,000
    (2025, 5, 560000.0, 240000.0, 135000.0, 60000.0, 30000.0),   # Total Cost: 465,000 -> Profit: 95,000
    (2025, 6, 490000.0, 260000.0, 145000.0, 65000.0, 35000.0),   # Total Cost: 505,000 -> Loss: 15,000 (Loss 2)
    (2025, 7, 590000.0, 255000.0, 140000.0, 60000.0, 30000.0),   # Total Cost: 485,000 -> Profit: 105,000
    (2025, 8, 620000.0, 270000.0, 150000.0, 65000.0, 35000.0),   # Total Cost: 520,000 -> Profit: 100,000
    (2025, 9, 580000.0, 250000.0, 140000.0, 60000.0, 30000.0),   # Total Cost: 480,000 -> Profit: 100,000
    (2025, 10, 680000.0, 290000.0, 160000.0, 70000.0, 40000.0),  # Total Cost: 560,000 -> Profit: 120,000
    (2025, 11, 720000.0, 310000.0, 170000.0, 75000.0, 40000.0),  # Total Cost: 595,000 -> Profit: 125,000
    (2025, 12, 650000.0, 280000.0, 155000.0, 70000.0, 35000.0),  # Total Cost: 540,000 -> Profit: 110,000
    # 2026: Jan - Oct (10 months)
    (2026, 1, 520000.0, 230000.0, 125000.0, 55000.0, 30000.0),   # Total Cost: 440,000 -> Profit: 80,000
    (2026, 2, 460000.0, 250000.0, 135000.0, 60000.0, 35000.0),   # Total Cost: 480,000 -> Loss: 20,000 (Loss 3)
    (2026, 3, 580000.0, 245000.0, 135000.0, 60000.0, 30000.0),   # Total Cost: 470,000 -> Profit: 110,000
    (2026, 4, 610000.0, 260000.0, 145000.0, 65000.0, 30000.0),   # Total Cost: 500,000 -> Profit: 110,000
    (2026, 5, 540000.0, 285000.0, 155000.0, 70000.0, 40000.0),   # Total Cost: 550,000 -> Loss: 10,000 (Loss 4)
    (2026, 6, 640000.0, 270000.0, 150000.0, 65000.0, 35000.0),   # Total Cost: 520,000 -> Profit: 120,000
    (2026, 7, 690000.0, 295000.0, 160000.0, 70000.0, 35000.0),   # Total Cost: 560,000 -> Profit: 130,000
    (2026, 8, 710000.0, 300000.0, 165000.0, 75000.0, 40000.0),   # Total Cost: 580,000 -> Profit: 130,000
    (2026, 9, 670000.0, 285000.0, 155000.0, 70000.0, 35000.0),   # Total Cost: 545,000 -> Profit: 125,000
    (2026, 10, 750000.0, 315000.0, 175000.0, 80000.0, 40000.0),  # Total Cost: 610,000 -> Profit: 140,000
]

def _init_sample_financial_data():
    """
    Idempotent seeding of sample monthly financial records for academic prototype demo.
    Guarantees exactly one record per month from Jan 2025 to Oct 2026.
    Uses unique constraint (year, month).
    """
    try:
        existing_count = SampleMonthlyFinancial.query.count()
        if existing_count >= len(SAMPLE_HISTORICAL_FINANCIALS):
            return
        
        for y, m, rev, fab, lab, mac, oth in SAMPLE_HISTORICAL_FINANCIALS:
            rec = SampleMonthlyFinancial.query.filter_by(year=y, month=m).first()
            if not rec:
                rec = SampleMonthlyFinancial(
                    year=y,
                    month=m,
                    revenue=rev,
                    fabric_cost=fab,
                    labour_cost=lab,
                    machine_cost=mac,
                    other_cost=oth,
                    is_demo=True,
                )
                db.session.add(rec)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _financial_summary(year, month=None, view_type='yearly'):
    """
    Core server-side calculation engine for Financial Analytics.
    
    Supports:
    - view_type='monthly': Selected month & year.
    - view_type='yearly': Selected year. If year == current_year, displays Jan up to current_month.
                          If year < current_year (previous year), displays all 12 months (Jan-Dec).
    - view_type='last_2_years': Previous calendar year (Jan-Dec) + current calendar year up to current_month.
    
    Integrates sample historical dataset (SampleMonthlyFinancial) for prototype demonstration
    while preserving actual live invoice records.
    """
    from sqlalchemy import extract, func
    
    _init_sample_financial_data()
    MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    now = datetime.utcnow()
    current_year = now.year
    current_month = now.month

    if view_type == 'monthly' and month:
        # --- MONTHLY VIEW ---
        # 1. Live invoices
        inv_q = Invoice.query.filter(
            extract('year', Invoice.invoice_date) == year,
            extract('month', Invoice.invoice_date) == month
        ).all()

        live_revenue = round(sum(i.total_amount for i in inv_q), 2)
        invoice_order_ids = [i.order_id for i in inv_q]
        live_costs = ProductionCost.query.filter(ProductionCost.order_id.in_(invoice_order_ids)).all() if invoice_order_ids else []

        live_fabric = round(sum(c.fabric_cost or 0 for c in live_costs), 2)
        live_labour = round(sum(c.labour_cost or 0 for c in live_costs), 2)
        live_machine = round(sum(c.machine_cost or 0 for c in live_costs), 2)
        live_other = round(sum(c.other_cost or 0 for c in live_costs), 2)
        live_cost = round(live_fabric + live_labour + live_machine + live_other, 2)

        # 2. Sample historical record for this month
        sample_rec = SampleMonthlyFinancial.query.filter_by(year=year, month=month).first()
        if sample_rec:
            # Base on sample benchmark + any incremental live billed revenue/cost
            total_revenue = round(sample_rec.revenue + live_revenue, 2)
            fabric = round(sample_rec.fabric_cost + live_fabric, 2)
            labour = round(sample_rec.labour_cost + live_labour, 2)
            machine = round(sample_rec.machine_cost + live_machine, 2)
            other = round(sample_rec.other_cost + live_other, 2)
            total_cost = round(sample_rec.total_cost + live_cost, 2)
        else:
            total_revenue = live_revenue
            fabric = live_fabric
            labour = live_labour
            machine = live_machine
            other = live_other
            total_cost = live_cost

        # Profit / Loss
        if total_revenue > total_cost:
            profit = round(total_revenue - total_cost, 2)
            loss = 0.0
        elif total_cost > total_revenue:
            profit = 0.0
            loss = round(total_cost - total_revenue, 2)
        else:
            profit = 0.0
            loss = 0.0

        margin = round((profit / total_revenue) * 100, 2) if total_revenue > 0 else 0.0

        order_rows = []
        if sample_rec:
            order_rows.append({
                'label': f"Monthly Sample Allocation ({MONTH_NAMES[month - 1]} {year})",
                'revenue': sample_rec.revenue,
                'cost': sample_rec.total_cost,
                'profit': sample_rec.profit,
                'loss': sample_rec.loss,
                'margin': sample_rec.profit_margin,
            })
        for inv in inv_q:
            c = ProductionCost.query.filter_by(order_id=inv.order_id).first()
            order_cost = c.total_cost if c else 0.0
            rev = round(inv.total_amount, 2)
            p = round(rev - order_cost, 2) if rev > order_cost else 0.0
            l = round(order_cost - rev, 2) if order_cost > rev else 0.0
            m = round((p / rev) * 100, 2) if rev > 0 else 0.0
            order_rows.append({
                'label': f"Order #{inv.order_id} / {inv.invoice_number}",
                'revenue': rev,
                'cost': round(order_cost, 2),
                'profit': p,
                'loss': l,
                'margin': m,
            })

        bar_labels = [MONTH_NAMES[month - 1]]
        bar_revenue = [total_revenue]
        bar_cost = [total_cost]
        line_labels = [MONTH_NAMES[month - 1]]
        line_values = [profit if profit > 0 else -loss]

        return {
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'total_fabric': fabric,
            'total_labour': labour,
            'total_machine': machine,
            'total_other': other,
            'net_profit': profit,
            'net_loss': loss,
            'profit_margin': margin,
            'summary_rows': order_rows,
            'bar_labels': bar_labels,
            'bar_revenue': bar_revenue,
            'bar_cost': bar_cost,
            'line_labels': line_labels,
            'line_values': line_values,
            'view': 'monthly',
        }

    else:
        # Determine (year, month) sequence
        if view_type == 'last_2_years':
            # Previous calendar year (all 12 months) + current calendar year up to current_month
            periods = [(current_year - 1, m) for m in range(1, 13)]
            periods.extend([(current_year, m) for m in range(1, current_month + 1)])
            is_two_year = True
        else:
            # Yearly view
            max_m = current_month if year == current_year else 12
            periods = [(year, m) for m in range(1, max_m + 1)]
            is_two_year = False

        bar_labels = []
        monthly_revenue = []
        monthly_cost = []
        monthly_profit = []
        monthly_loss = []
        monthly_fabric = []
        monthly_labour = []
        monthly_machine = []
        monthly_other = []
        summary_rows = []

        total_revenue = 0.0
        total_cost = 0.0
        total_fabric = 0.0
        total_labour = 0.0
        total_machine = 0.0
        total_other = 0.0

        for (y, m) in periods:
            # 1. Live Invoices in this month
            inv_q = Invoice.query.filter(
                extract('year', Invoice.invoice_date) == y,
                extract('month', Invoice.invoice_date) == m
            ).all()

            live_rev = round(sum(i.total_amount for i in inv_q), 2)
            invoice_order_ids = [i.order_id for i in inv_q]
            live_costs = ProductionCost.query.filter(ProductionCost.order_id.in_(invoice_order_ids)).all() if invoice_order_ids else []

            live_fab = round(sum(c.fabric_cost or 0 for c in live_costs), 2)
            live_lab = round(sum(c.labour_cost or 0 for c in live_costs), 2)
            live_mac = round(sum(c.machine_cost or 0 for c in live_costs), 2)
            live_oth = round(sum(c.other_cost or 0 for c in live_costs), 2)

            # 2. Sample Historical Data for this month
            sample_rec = SampleMonthlyFinancial.query.filter_by(year=y, month=m).first()
            if sample_rec:
                rev = round(sample_rec.revenue + live_rev, 2)
                fab = round(sample_rec.fabric_cost + live_fab, 2)
                lab = round(sample_rec.labour_cost + live_lab, 2)
                mac = round(sample_rec.machine_cost + live_mac, 2)
                oth = round(sample_rec.other_cost + live_oth, 2)
                cost = round(sample_rec.total_cost + (live_fab + live_lab + live_mac + live_oth), 2)
            else:
                rev = live_rev
                fab = live_fab
                lab = live_lab
                mac = live_mac
                oth = live_oth
                cost = round(fab + lab + mac + oth, 2)

            if rev > cost:
                pft = round(rev - cost, 2)
                lss = 0.0
            elif cost > rev:
                pft = 0.0
                lss = round(cost - rev, 2)
            else:
                pft = 0.0
                lss = 0.0

            margin_m = round((pft / rev) * 100, 2) if rev > 0 else 0.0

            monthly_revenue.append(rev)
            monthly_cost.append(cost)
            monthly_profit.append(pft)
            monthly_loss.append(lss)
            monthly_fabric.append(fab)
            monthly_labour.append(lab)
            monthly_machine.append(mac)
            monthly_other.append(oth)

            total_revenue += rev
            total_cost += cost
            total_fabric += fab
            total_labour += lab
            total_machine += mac
            total_other += oth

            # Label formatting
            m_name = MONTH_NAMES[m - 1]
            if is_two_year:
                chart_lbl = f"{m_name} '{str(y)[-2:]}"
                row_lbl = f"{m_name} {y}"
            else:
                chart_lbl = m_name
                row_lbl = m_name

            bar_labels.append(chart_lbl)
            summary_rows.append({
                'label': row_lbl,
                'revenue': rev,
                'cost': cost,
                'profit': pft,
                'loss': lss,
                'margin': margin_m,
            })

        total_revenue = round(total_revenue, 2)
        total_cost = round(total_cost, 2)
        total_fabric = round(total_fabric, 2)
        total_labour = round(total_labour, 2)
        total_machine = round(total_machine, 2)
        total_other = round(total_other, 2)

        if total_revenue > total_cost:
            net_profit = round(total_revenue - total_cost, 2)
            net_loss = 0.0
        elif total_cost > total_revenue:
            net_profit = 0.0
            net_loss = round(total_cost - total_revenue, 2)
        else:
            net_profit = 0.0
            net_loss = 0.0

        profit_margin = round((net_profit / total_revenue) * 100, 2) if total_revenue > 0 else 0.0
        line_values = [p if p > 0 else -l for p, l in zip(monthly_profit, monthly_loss)]

        return {
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'total_fabric': total_fabric,
            'total_labour': total_labour,
            'total_machine': total_machine,
            'total_other': total_other,
            'net_profit': net_profit,
            'net_loss': net_loss,
            'profit_margin': profit_margin,
            'summary_rows': summary_rows,
            'bar_labels': bar_labels,
            'bar_revenue': monthly_revenue,
            'bar_cost': monthly_cost,
            'line_labels': bar_labels,
            'line_values': line_values,
            'view': view_type,
        }


def _available_years():
    """Return sorted list of years present in invoice data + current and previous calendar year."""
    from sqlalchemy import extract, distinct
    raw_years = [r[0] for r in db.session.query(extract('year', Invoice.invoice_date)).distinct().order_by(extract('year', Invoice.invoice_date).desc()).all() if r[0] is not None]
    current_y = datetime.utcnow().year
    prev_y = current_y - 1
    
    # Ensure current and previous years are always included
    year_set = set(int(y) for y in raw_years)
    year_set.add(current_y)
    year_set.add(prev_y)
    return sorted(list(year_set), reverse=True)


@owner_bp.route('/financial-analytics')
@owner_required
def financial_analytics():
    """Financial Analytics – owner-only main view."""
    current_year = datetime.utcnow().year
    current_month = datetime.utcnow().month

    view_type = request.args.get('view', 'yearly')
    try:
        sel_year = int(request.args.get('year', current_year))
    except (ValueError, TypeError):
        sel_year = current_year
    try:
        sel_month = int(request.args.get('month', current_month))
    except (ValueError, TypeError):
        sel_month = current_month

    if view_type not in ('monthly', 'yearly', 'last_2_years'):
        view_type = 'yearly'

    month_arg = sel_month if view_type == 'monthly' else None
    data = _financial_summary(sel_year, month_arg, view_type=view_type)
    available_years = _available_years()

    MONTH_NAMES_FULL = ['January','February','March','April','May','June',
                        'July','August','September','October','November','December']

    # Orders list for cost-entry section (orders with invoices for quick context)
    orders_for_cost = (
        db.session.query(Order, Invoice, ProductionCost)
        .join(Invoice, Invoice.order_id == Order.id)
        .outerjoin(ProductionCost, ProductionCost.order_id == Order.id)
        .order_by(Invoice.invoice_date.desc())
        .all()
    )

    return render_template(
        'owner/financial_analytics.html',
        data=data,
        view_type=view_type,
        sel_year=sel_year,
        sel_month=sel_month,
        available_years=available_years,
        month_names_full=MONTH_NAMES_FULL,
        orders_for_cost=orders_for_cost,
        current_year=current_year,
        current_month=current_month,
        format_inr=_fmt_inr,
    )


@owner_bp.route('/financial-analytics/save-cost/<int:order_id>', methods=['POST'])
@owner_required
def financial_save_cost(order_id):
    """Owner: save or update ProductionCost for an existing order."""
    order = Order.query.get_or_404(order_id)

    def _safe_float(key):
        val = request.form.get(key, '0').strip()
        try:
            v = float(val)
            if v < 0:
                raise ValueError("Negative")
            return round(v, 2)
        except (ValueError, TypeError):
            return 0.0

    fabric = _safe_float('fabric_cost')
    labour = _safe_float('labour_cost')
    machine = _safe_float('machine_cost')
    other = _safe_float('other_cost')

    cost_rec = ProductionCost.query.filter_by(order_id=order.id).first()
    if cost_rec:
        cost_rec.fabric_cost = fabric
        cost_rec.labour_cost = labour
        cost_rec.machine_cost = machine
        cost_rec.other_cost = other
        cost_rec.updated_at = datetime.utcnow()
        action = 'Updated'
    else:
        cost_rec = ProductionCost(
            order_id=order.id,
            fabric_cost=fabric,
            labour_cost=labour,
            machine_cost=machine,
            other_cost=other,
        )
        db.session.add(cost_rec)
        action = 'Created'

    db.session.commit()
    log_activity(f"{action} Production Cost for Order #{order.id}: Total ₹{cost_rec.total_cost}")
    flash(f'Production cost {action.lower()} successfully for Order #{order.id}.', 'success')

    # Redirect back to financial analytics preserving filters
    return redirect(url_for('owner.financial_analytics',
                            view=request.form.get('view', 'yearly'),
                            year=request.form.get('year', datetime.utcnow().year),
                            month=request.form.get('month', datetime.utcnow().month)))
