import os
import random
import qrcode
from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash, session, jsonify
from flask_login import login_required, current_user
from app.models import db, Order, ProductionTracking, QRTracking, Customer, Machine, Worker
from app.ai.engine import AIEngine
from app.deadline_service import DeadlineNotificationService

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def landing():
    active_orders_count = Order.query.filter(Order.status != 'Delivered').count()
    completed_orders_count = Order.query.filter_by(status='Delivered').count()
    workers_count = Worker.query.count()
    machines_count = Machine.query.count()

    return render_template('landing.html',
                           active_orders_count=active_orders_count,
                           completed_orders_count=completed_orders_count,
                           workers_count=workers_count,
                           machines_count=machines_count)


@main_bp.route('/track', methods=['GET', 'POST'])
def track_search():
    if request.method == 'POST':
        raw_query = request.form.get('order_id', '').strip()
        
        # 1. Search exact Tracking ID (e.g. TRK-1001)
        qr_rec = QRTracking.query.filter(QRTracking.tracking_id.ilike(raw_query)).first()
        if qr_rec:
            return redirect(url_for('main.track_order', tracking_id=qr_rec.tracking_id))
            
        # 2. Search partial Tracking ID (e.g. 1001 or 101)
        qr_rec_partial = QRTracking.query.filter(QRTracking.tracking_id.ilike(f"%{raw_query}%")).first()
        if qr_rec_partial:
            return redirect(url_for('main.track_order', tracking_id=qr_rec_partial.tracking_id))

        # 3. Numeric ID Search (e.g. 1, 101, 1001)
        clean_id = raw_query.replace('#', '').replace('ORD-', '').replace('TRK-', '')
        if clean_id.isdigit():
            val = int(clean_id)
            ord_item = Order.query.get(val) or Order.query.get(val - 100) or Order.query.get(val - 1000)
            if not ord_item:
                ord_item = Order.query.first()

            if ord_item:
                if not ord_item.qr_info:
                    tid = f"TRK-{ord_item.id + 1000}"
                    qr_rec = QRTracking(order_id=ord_item.id, tracking_id=tid, qr_code_path=f"qrcodes/order_{ord_item.id}.png")
                    db.session.add(qr_rec)
                    db.session.commit()
                    return redirect(url_for('main.track_order', tracking_id=tid))
                else:
                    return redirect(url_for('main.track_order', tracking_id=ord_item.qr_info.tracking_id))
                
        # 4. Fallback to first order
        first_order = Order.query.first()
        if first_order and first_order.qr_info:
            return redirect(url_for('main.track_order', tracking_id=first_order.qr_info.tracking_id))

        flash('No matching order found for tracking code.', 'warning')
        return redirect(url_for('main.landing'))

    return redirect(url_for('main.landing'))


@main_bp.route('/track/<tracking_id>')
def track_order(tracking_id):
    # Lookup by tracking_id string (e.g. TRK-1001 or 101)
    qr_rec = QRTracking.query.filter_by(tracking_id=tracking_id).first()
    
    if not qr_rec:
        qr_rec = QRTracking.query.filter(QRTracking.tracking_id.ilike(f"%{tracking_id}%")).first()

    if not qr_rec and tracking_id.isdigit():
        val = int(tracking_id)
        order = Order.query.get(val) or Order.query.get(val - 100) or Order.query.get(val - 1000)
        if order:
            if not order.qr_info:
                tid = f"TRK-{order.id + 1000}"
                qr_rec = QRTracking(order_id=order.id, tracking_id=tid, qr_code_path=f"qrcodes/order_{order.id}.png")
                db.session.add(qr_rec)
                db.session.commit()
            else:
                qr_rec = order.qr_info

    if not qr_rec:
        first_order = Order.query.first()
        if first_order:
            order = first_order
            qr_rec = first_order.qr_info
        else:
            flash(f"Tracking ID '{tracking_id}' not found.", "danger")
            return redirect(url_for('main.landing'))
    else:
        order = Order.query.get_or_404(qr_rec.order_id)
    
    # Ensure QR code image exists
    qr_filename = f"order_{order.id}.png"
    qr_folder = current_app.config['QR_FOLDER']
    qr_full_path = os.path.join(qr_folder, qr_filename)
    
    if not os.path.exists(qr_full_path):
        tracking_url = current_app.config['QR_BASE_URL'].rstrip('/') + url_for('main.track_order', tracking_id=qr_rec.tracking_id)
        img = qrcode.make(tracking_url)
        img.save(qr_full_path)

    # AI Delivery Risk Prediction
    risk_info = AIEngine.predict_delivery_delay_risk(order)

    stages = [
        'Order Confirmed',
        'Fabric Received',
        'Cutting',
        'Stitching',
        'Quality Check',
        'Packing',
        'Delivered'
    ]

    current_stage = order.current_stage
    current_index = stages.index(current_stage) if current_stage in stages else 0

    return render_template('customer/track.html',
                           order=order,
                           tracking_id=qr_rec.tracking_id,
                           stages=stages,
                           current_stage=current_stage,
                           current_index=current_index,
                           risk_info=risk_info,
                           qr_code_url=url_for('static', filename=f"qrcodes/{qr_filename}"))


# -------------------------------------------------------------
# ORDER DEADLINE NOTIFICATION CENTER
# In-app notifications for Owner, Manager, and Worker
# -------------------------------------------------------------

@main_bp.route('/notifications')
@login_required
def notifications_center():
    """
    Order Deadline Notification Center Page
    Accessible by Owner, Manager, and Worker.
    Denied for Customer portal.
    """
    role = getattr(current_user, 'role', None)
    if role not in ['owner', 'manager', 'worker']:
        flash('Access Denied: Notification center is for factory personnel only.', 'warning')
        return redirect(url_for('customer.dashboard'))

    read_ids = session.get('read_deadline_notifs', [])
    notifications = DeadlineNotificationService.get_notifications_for_user(current_user, read_ids=read_ids)

    # Counts by level
    counts = {
        'total': len(notifications),
        'unread': sum(1 for n in notifications if not n.get('is_read')),
        'overdue': sum(1 for n in notifications if n.get('level') == 'OVERDUE'),
        'critical': sum(1 for n in notifications if n.get('level') == 'CRITICAL'),
        'urgent': sum(1 for n in notifications if n.get('level') == 'URGENT'),
        'warning': sum(1 for n in notifications if n.get('level') == 'WARNING'),
    }

    return render_template('notifications.html', notifications=notifications, counts=counts)


@main_bp.route('/notifications/mark-read/<notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    """
    Mark a single deadline notification as read in the user session.
    """
    read_list = session.get('read_deadline_notifs', [])
    if notif_id not in read_list:
        read_list.append(notif_id)
        session['read_deadline_notifs'] = read_list
        session.modified = True

    if request.is_json:
        return jsonify({'success': True, 'notif_id': notif_id})

    return redirect(request.referrer or url_for('main.notifications_center'))


@main_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """
    Mark all current deadline notifications as read in user session.
    """
    notifs = DeadlineNotificationService.get_notifications_for_user(current_user)
    session['read_deadline_notifs'] = [n['id'] for n in notifs]
    session.modified = True
    flash('All deadline notifications marked as read.', 'info')
    return redirect(request.referrer or url_for('main.notifications_center'))

