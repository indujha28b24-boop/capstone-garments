import os
import random
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, current_app
from flask_login import login_user, logout_user, login_required, current_user
from io import BytesIO
from app.models import db, Customer, CustomerUser, Order, ProductionTracking, SupportTicket, CustomerFeedback, QRTracking, Invoice, OnlineOrderRequest
from app.ai.engine import AIEngine

customer_bp = Blueprint('customer', __name__)

def customer_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        user_id = current_user.get_id()
        if not user_id or not user_id.startswith('cust_'):
            flash('Access Denied: Customer login required.', 'danger')
            return redirect(url_for('customer.login'))
        return f(*args, **kwargs)
    return decorated_function

@customer_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.get_id().startswith('cust_'):
            return redirect(url_for('customer.dashboard'))
        else:
            logout_user() # Log out staff if they try to access customer portal
            
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        remember = True if request.form.get('remember') else False

        user = CustomerUser.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f'Welcome back to StitchTech Customer Portal!', 'success')
            return redirect(url_for('customer.dashboard'))
        else:
            flash('Invalid Email or Password. Please try again.', 'danger')
            
    return render_template('customer/login.html')

@customer_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out of the Customer Portal.', 'info')
    return redirect(url_for('customer.login'))

@customer_bp.route('/dashboard')
@customer_required
def dashboard():
    customer = current_user.customer
    orders = Order.query.filter_by(customer_id=customer.id).all()
    
    total_orders = len(orders)
    active_orders = sum(1 for o in orders if o.status not in ['Delivered', 'Cancelled'])
    completed_orders = sum(1 for o in orders if o.status == 'Delivered')
    pending_orders = sum(1 for o in orders if o.status == 'Order Confirmed')
    
    # AI Delivery confidence average
    confidence_avg = 95
    if active_orders > 0:
        conf_sum = 0
        active_count = 0
        for o in orders:
            if o.status not in ['Delivered', 'Cancelled']:
                risk = AIEngine.predict_delivery_delay_risk(o)
                conf_sum += (100 - risk.get('probability', 10))
                active_count += 1
        if active_count > 0:
            confidence_avg = round(conf_sum / active_count)

    # Simulated notifications
    notifications = [
        {'title': 'Order Confirmed', 'desc': 'Order batch #1001 fabric check cleared.', 'time': '1 hour ago'},
        {'title': 'Fabric Cutting Completed', 'desc': 'Order batch #1002 cutting lines complete.', 'time': '3 hours ago'},
        {'title': 'Stitching Started', 'desc': 'Precision Juki stitch line active for order #1002.', 'time': '4 hours ago'}
    ]

    # Customer online order requests
    online_requests = OnlineOrderRequest.query.filter_by(
        customer_id=customer.id
    ).order_by(OnlineOrderRequest.submitted_at.desc()).limit(5).all()
    pending_online_requests_count = OnlineOrderRequest.query.filter_by(
        customer_id=customer.id, status='PENDING'
    ).count()

    return render_template('customer/dashboard.html',
                           customer=customer,
                           current_date=datetime.utcnow().strftime('%A, %B %d, %Y'),
                           orders=orders,
                           total_orders=total_orders,
                           active_orders=active_orders,
                           completed_orders=completed_orders,
                           pending_orders=pending_orders,
                           confidence_avg=confidence_avg,
                           notifications=notifications,
                           online_requests=online_requests,
                           pending_online_requests_count=pending_online_requests_count)

@customer_bp.route('/order/<int:order_id>')
@customer_required
def order_detail(order_id):
    customer = current_user.customer
    order = Order.query.filter_by(id=order_id, customer_id=customer.id).first_or_404()

    # stages sequence for tracking
    stages = [
        'Order Confirmed',
        'Fabric Allocated',
        'Fabric Cutting',
        'Stitching',
        'Quality Inspection',
        'Finishing',
        'Packing',
        'Ready for Dispatch',
        'Out For Delivery',
        'Delivered'
    ]

    current_stage = order.status
    if current_stage not in stages:
        # Match database stage mapping safely
        mapping = {
            'In Production': 'Stitching',
            'Quality Check': 'Quality Inspection'
        }
        current_stage = mapping.get(order.status, 'Order Confirmed')

    current_index = stages.index(current_stage) if current_stage in stages else 0

    # AI predictions
    risk_info = AIEngine.predict_delivery_delay_risk(order)

    # Google Maps coordinate values (Simulated coordinates)
    # Factory (start) at Bangalore garment cluster, vehicle (moving), customer delivery (dest) at Chennai port
    factory_lat, factory_lng = 12.9716, 77.5946
    dest_lat, dest_lng = 13.0827, 80.2707
    
    # Simulating a moving marker between start & end based on order progress
    progress_frac = order.progress_percentage / 100.0
    vehicle_lat = factory_lat + (dest_lat - factory_lat) * progress_frac
    vehicle_lng = factory_lng + (dest_lng - factory_lng) * progress_frac

    maps_data = {
        'factory': {'lat': factory_lat, 'lng': factory_lng, 'address': 'StitchTech Main Factory, Whitefield, Bangalore'},
        'vehicle': {'lat': vehicle_lat, 'lng': vehicle_lng, 'speed': 45 if progress_frac > 0.8 else 0},
        'destination': {'lat': dest_lat, 'lng': dest_lng, 'address': 'Warehouse Port Terminal A, Chennai'},
        'progress': order.progress_percentage
    }

    # Payments summary for this order
    unit_prices = {'Shirts': 15, 'Denim': 25, 'T-Shirts': 10, 'Dresses': 30, 'Jackets': 40}
    unit_price = unit_prices.get(order.garment_type, 15)
    total_amount = order.quantity * unit_price
    paid_amount = total_amount if order.status == 'Delivered' else (total_amount * 0.5)
    balance_amount = total_amount - paid_amount

    payment_info = {
        'total_amount': total_amount,
        'paid_amount': paid_amount,
        'balance_amount': balance_amount,
        'status': 'Paid' if balance_amount == 0 else 'Partial Payment (50% Deposit Paid)'
    }

    days_buffer = risk_info.get('days_buffer', 1)
    predicted_delivery_date = (order.deadline - timedelta(days=days_buffer)).strftime('%b %d, %Y')

    return render_template('customer/order_detail.html',
                           order=order,
                           stages=stages,
                           current_stage=current_stage,
                           current_index=current_index,
                           risk_info=risk_info,
                           maps_data=maps_data,
                           payment_info=payment_info,
                           predicted_delivery_date=predicted_delivery_date)

@customer_bp.route('/support', methods=['GET', 'POST'])
@customer_required
def support():
    customer = current_user.customer
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        description = request.form.get('description', '').strip()
        
        ticket = SupportTicket(customer_id=customer.id, subject=subject, description=description)
        db.session.add(ticket)
        db.session.commit()
        
        flash('Your support request has been raised successfully. A manager will contact you shortly.', 'success')
        return redirect(url_for('customer.support'))

    tickets = SupportTicket.query.filter_by(customer_id=customer.id).order_by(SupportTicket.created_at.desc()).all()
    return render_template('customer/support.html', tickets=tickets)

@customer_bp.route('/feedback/<int:order_id>', methods=['GET', 'POST'])
@customer_required
def feedback(order_id):
    customer = current_user.customer
    order = Order.query.filter_by(id=order_id, customer_id=customer.id).first_or_404()

    if request.method == 'POST':
        product_rating = int(request.form.get('product_rating', 5))
        delivery_rating = int(request.form.get('delivery_rating', 5))
        quality_rating = int(request.form.get('quality_rating', 5))
        review_text = request.form.get('review_text', '').strip()
        suggestions = request.form.get('suggestions', '').strip()

        fb = CustomerFeedback(
            customer_id=customer.id,
            order_id=order.id,
            product_rating=product_rating,
            delivery_rating=delivery_rating,
            quality_rating=quality_rating,
            review_text=review_text,
            suggestions=suggestions
        )
        db.session.add(fb)
        db.session.commit()

        flash('Thank you for your valuable feedback! We appreciate your suggestions.', 'success')
        return redirect(url_for('customer.dashboard'))

    return render_template('customer/feedback.html', order=order)

@customer_bp.route('/profile', methods=['GET', 'POST'])
@customer_required
def profile():
    cust_user = current_user
    if request.method == 'POST':
        cust_user.company_name = request.form.get('company_name', '').strip()
        cust_user.contact_name = request.form.get('contact_name', '').strip()
        cust_user.phone = request.form.get('phone', '').strip()
        cust_user.gst_number = request.form.get('gst_number', '').strip()
        cust_user.delivery_address = request.form.get('delivery_address', '').strip()
        cust_user.billing_address = request.form.get('billing_address', '').strip()
        
        new_password = request.form.get('new_password', '').strip()
        if new_password:
            cust_user.set_password(new_password)

        db.session.commit()
        flash('Your profile details have been updated successfully.', 'success')
        return redirect(url_for('customer.profile'))

    return render_template('customer/profile.html')

@customer_bp.route('/payments')
@customer_required
def payments():
    customer = current_user.customer
    orders = Order.query.filter_by(customer_id=customer.id).all()
    
    total_due = 0
    total_paid = 0
    unit_prices = {'Shirts': 15, 'Denim': 25, 'T-Shirts': 10, 'Dresses': 30, 'Jackets': 40}
    
    payments_list = []
    for order in orders:
        unit_price = unit_prices.get(order.garment_type, 15)
        tot = order.quantity * unit_price
        paid = tot if order.status == 'Delivered' else (tot * 0.5)
        bal = tot - paid
        
        total_paid += paid
        total_due += bal

        payments_list.append({
            'order_id': order.id,
            'garment_type': order.garment_type,
            'quantity': order.quantity,
            'total': tot,
            'paid': paid,
            'balance': bal,
            'status': 'Completed' if bal == 0 else 'Deposit Paid (50%)',
            'date': order.order_date.strftime('%b %d, %Y')
        })

    return render_template('customer/payments.html',
                           payments=payments_list,
                           total_due=total_due,
                           total_paid=total_paid)

# Document Generators (professional PDF placeholders sending file streams)
def generate_pdf_document(doc_type, order):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=15
    )

    story.append(Paragraph(f"StitchTech Industrial ERP - {doc_type}", title_style))
    story.append(Spacer(1, 10))

    meta_data = [
        [Paragraph(f"<b>Order Number:</b> ORD-{order.id:04d}", styles['Normal']), Paragraph(f"<b>Date:</b> {datetime.utcnow().strftime('%B %d, %Y')}", styles['Normal'])],
        [Paragraph(f"<b>Customer Name:</b> {order.customer.name}", styles['Normal']), Paragraph(f"<b>Delivery Mode:</b> Secure Cargo Freight", styles['Normal'])],
    ]
    t_meta = Table(meta_data, colWidths=[270, 270])
    t_meta.setStyle(TableStyle([
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 20))

    headers = ['Item Description', 'Garment Class', 'Ordered Quantity', 'Unit Price', 'Total Cost']
    unit_prices = {'Shirts': 15, 'Denim': 25, 'T-Shirts': 10, 'Dresses': 30, 'Jackets': 40}
    price = unit_prices.get(order.garment_type, 15)
    total_val = order.quantity * price

    table_data = [
        headers,
        [f"Industrial Garment Batch Execution", order.garment_type, f"{order.quantity:,} units", f"INR {price:.2f}", f"INR {total_val:,.2f}"]
    ]
    t_data = Table(table_data, colWidths=[180, 90, 100, 80, 90])
    t_data.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    story.append(t_data)
    story.append(Spacer(1, 30))

    footer_text = f"This document is digitally verified and issued on behalf of StitchTech ERP Garment Factory Floor Management."
    story.append(Paragraph(f"<i>{footer_text}</i>", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

@customer_bp.route('/document/<doc_type>/<int:order_id>')
@customer_required
def download_document(doc_type, order_id):
    customer = current_user.customer
    order = Order.query.filter_by(id=order_id, customer_id=customer.id).first_or_404()
    
    doc_types_map = {
        'invoice': 'Commercial Invoice',
        'po': 'Purchase Order Check',
        'challan': 'Delivery Challan',
        'cert': 'Quality Check & Conformity Certificate',
        'warranty': 'Garment Fabric Warranty Statement'
    }
    
    title = doc_types_map.get(doc_type, 'StitchTech Document')
    pdf_bytes = generate_pdf_document(title, order)
    
    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"{doc_type}_ORD_{order.id:04d}.pdf"
    )

# -------------------------------------------------------------
# CUSTOMER READ-ONLY INVOICE MANAGEMENT
# Reuses existing Invoice records and Owner/Manager PDF generation
# -------------------------------------------------------------

from app.billing_pdf import generate_invoice_pdf


@customer_bp.route('/invoice/<int:invoice_id>')
@customer_required
def invoice_view(invoice_id):
    """
    Customer Read-Only Invoice View
    Verifies that the requested invoice belongs to the logged-in customer.
    """
    customer = current_user.customer
    invoice = Invoice.query.filter_by(id=invoice_id).first()

    if not invoice:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('customer.dashboard'))

    # Security verification: Customer can ONLY access their own invoice
    if invoice.customer_id != customer.id or (invoice.order and invoice.order.customer_id != customer.id):
        flash('Access Denied: You do not have permission to view this invoice.', 'danger')
        return redirect(url_for('customer.dashboard'))

    return render_template('customer/invoice_view.html', invoice=invoice)

@customer_bp.route('/invoice/<int:invoice_id>/pdf')
@customer_required
def invoice_pdf(invoice_id):
    """
    Customer Invoice PDF Download
    Reuses existing Owner/Manager PDF generation format.
    Verifies that the requested invoice belongs to the logged-in customer.
    """
    customer = current_user.customer
    invoice = Invoice.query.filter_by(id=invoice_id).first()

    if not invoice:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('customer.dashboard'))

    # Security verification: Customer can ONLY download their own invoice PDF
    if invoice.customer_id != customer.id or (invoice.order and invoice.order.customer_id != customer.id):
        flash('Access Denied: You do not have permission to download this invoice.', 'danger')
        return redirect(url_for('customer.dashboard'))

    buffer = generate_invoice_pdf(invoice)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{invoice.invoice_number}.pdf",
        mimetype='application/pdf'
    )

@customer_bp.route('/order/<int:order_id>/invoice')
@customer_required
def order_invoice(order_id):
    """
    Convenience route from order detail to invoice
    Verifies order ownership and invoice presence.
    """
    customer = current_user.customer
    order = Order.query.filter_by(id=order_id, customer_id=customer.id).first()

    if not order:
        flash('Access Denied: Order not found or does not belong to your account.', 'danger')
        return redirect(url_for('customer.dashboard'))

    if not order.invoice:
        flash('Invoice Pending: No invoice has been generated for this order yet.', 'warning')
        return redirect(url_for('customer.order_detail', order_id=order.id))

    return redirect(url_for('customer.invoice_view', invoice_id=order.invoice.id))


# =============================================================
# ONLINE ORDER REQUESTS — Customer routes
# =============================================================

@customer_bp.route('/online-orders/place', methods=['GET', 'POST'])
@customer_required
def place_order_request():
    """Customer: submit a new garment order request for management review."""
    customer = current_user.customer

    if request.method == 'POST':
        garment_type = request.form.get('garment_type', '').strip()
        quantity_str = request.form.get('quantity', '0').strip()
        size_s_str = request.form.get('size_s', '0').strip()
        size_m_str = request.form.get('size_m', '0').strip()
        size_l_str = request.form.get('size_l', '0').strip()
        size_xl_str = request.form.get('size_xl', '0').strip()
        fabric_preference = request.form.get('fabric_preference', '').strip()
        color = request.form.get('color', '').strip()
        required_delivery_date_str = request.form.get('required_delivery_date', '').strip()
        special_requirements = request.form.get('special_requirements', '').strip()

        errors = []

        # Validate garment type
        allowed_types = ['Shirt', 'T-Shirt', 'Denim', 'Dress', 'Jacket', 'Other']
        if not garment_type or garment_type not in allowed_types:
            errors.append('Please select a valid garment type.')

        # Validate quantity
        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                errors.append('Quantity must be greater than 0.')
        except ValueError:
            errors.append('Please enter a valid quantity.')
            quantity = 0

        # Validate size quantities
        try:
            size_s = int(size_s_str) if size_s_str else 0
            size_m = int(size_m_str) if size_m_str else 0
            size_l = int(size_l_str) if size_l_str else 0
            size_xl = int(size_xl_str) if size_xl_str else 0
        except ValueError:
            errors.append('Size quantities must be valid integers.')
            size_s = size_m = size_l = size_xl = 0

        if size_s < 0 or size_m < 0 or size_l < 0 or size_xl < 0:
            errors.append('Size quantities cannot be negative.')

        size_total = size_s + size_m + size_l + size_xl
        if size_total > 0 and quantity > 0 and size_total != quantity:
            errors.append(f'Sum of size quantities ({size_total}) must equal total quantity ({quantity}).')

        # Validate delivery date
        required_delivery_date = None
        try:
            required_delivery_date = datetime.strptime(required_delivery_date_str, '%Y-%m-%d').date()
            from datetime import date as date_type
            if required_delivery_date <= date_type.today():
                errors.append('Required delivery date must be a future date.')
        except ValueError:
            errors.append('Please enter a valid required delivery date.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('customer/place_order_request.html', customer=customer,
                                   form_data=request.form)

        # Generate unique request number: REQ-YYYY-NNNN
        year = datetime.utcnow().year
        last_req = OnlineOrderRequest.query.order_by(OnlineOrderRequest.id.desc()).first()
        seq = (last_req.id + 1) if last_req else 1
        request_number = f'REQ-{year}-{seq:04d}'
        # Ensure uniqueness
        while OnlineOrderRequest.query.filter_by(request_number=request_number).first():
            seq += 1
            request_number = f'REQ-{year}-{seq:04d}'

        # If no size breakdown provided, distribute evenly
        if size_total == 0 and quantity > 0:
            size_s = quantity // 4
            size_m = quantity // 4
            size_l = quantity // 4
            size_xl = quantity - (size_s + size_m + size_l)

        req = OnlineOrderRequest(
            request_number=request_number,
            customer_id=customer.id,
            garment_type=garment_type,
            quantity=quantity,
            size_s=size_s,
            size_m=size_m,
            size_l=size_l,
            size_xl=size_xl,
            fabric_preference=fabric_preference or None,
            color=color or None,
            required_delivery_date=required_delivery_date,
            special_requirements=special_requirements or None,
            status='PENDING'
        )
        db.session.add(req)
        db.session.commit()

        flash(f'Order request submitted successfully. Request ID: {request_number}. Your order is waiting for management confirmation.', 'success')
        return redirect(url_for('customer.my_online_orders'))

    return render_template('customer/place_order_request.html', customer=customer, form_data={})


@customer_bp.route('/online-orders')
@customer_required
def my_online_orders():
    """Customer: view only their own online order requests."""
    customer = current_user.customer
    # Backend enforcement: filter strictly by this customer's id
    requests_list = OnlineOrderRequest.query.filter_by(
        customer_id=customer.id
    ).order_by(OnlineOrderRequest.submitted_at.desc()).all()
    return render_template('customer/my_online_orders.html', customer=customer, requests=requests_list)


@customer_bp.route('/online-orders/<int:req_id>')
@customer_required
def view_online_request(req_id):
    """Customer: view details of one of their own requests only."""
    customer = current_user.customer
    req = OnlineOrderRequest.query.filter_by(id=req_id, customer_id=customer.id).first()
    if not req:
        flash('Access Denied: Request not found or does not belong to your account.', 'danger')
        return redirect(url_for('customer.my_online_orders'))
    return render_template('customer/view_online_request.html', customer=customer, req=req)
