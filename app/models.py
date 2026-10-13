from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'owner', 'manager', 'worker'
    department = db.Column(db.String(80), default='Executive') # Executive, Floor Management, Cutting, Stitching, Quality Check, Packing
    created_date = db.Column(db.DateTime, default=datetime.utcnow)

    worker_profile = db.relationship('Worker', backref='user', uselist=False, lazy=True)
    manager_profile = db.relationship('Manager', backref='user', uselist=False, lazy=True)
    activity_logs = db.relationship('ActivityLog', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    orders = db.relationship('Order', backref='customer', lazy=True)

    @property
    def customer_name(self):
        return self.name


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    garment_type = db.Column(db.String(80), nullable=False)  # Shirts, Denim, T-Shirts, Dresses, Jackets
    quantity = db.Column(db.Integer, nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), default='Order Confirmed') # Order Confirmed, In Production, Quality Check, Packing, Delivered, Delayed
    priority_override = db.Column(db.String(20), nullable=True) # 'URGENT', 'HIGH', 'NORMAL', 'LOW' or None

    tracking = db.relationship('ProductionTracking', backref='order', uselist=False, cascade='all, delete-orphan')
    qr_info = db.relationship('QRTracking', backref='order', uselist=False, cascade='all, delete-orphan')

    @property
    def smart_priority(self):
        if self.priority_override:
            return self.priority_override

        if self.status == 'Delivered' or self.progress_percentage >= 100:
            return 'LOW'

        now = datetime.utcnow()
        days_left = (self.deadline - now).total_seconds() / 86400.0

        if days_left <= 0:
            return 'URGENT'

        remaining_progress = 100 - self.progress_percentage
        required_rate = remaining_progress / max(0.5, days_left)

        if days_left <= 2 and self.progress_percentage < 80:
            return 'URGENT'
        if required_rate > 30:
            return 'URGENT'
        if required_rate > 18 or days_left < 4:
            return 'HIGH'
        if self.progress_percentage < 15:
            return 'NORMAL'
        return 'LOW'

    @property
    def smart_priority_reasons(self):
        reasons = []
        if self.priority_override:
            return [f"Priority manually set to {self.priority_override} by manager."]

        if self.status == 'Delivered' or self.progress_percentage >= 100:
            return ['Order already completed/delivered.']

        now = datetime.utcnow()
        days_left = (self.deadline - now).total_seconds() / 86400.0

        if days_left <= 0:
            return ['Delivery deadline has already passed!']

        remaining_progress = 100 - self.progress_percentage
        required_rate = remaining_progress / max(0.5, days_left)

        if days_left <= 2:
            reasons.append(f"Delivery deadline is very close ({round(days_left, 1)} days remaining).")
        elif days_left < 7:
            reasons.append(f"Few days remaining ({round(days_left, 1)} days).")

        if self.progress_percentage < 30 and days_left < 7:
            reasons.append(f"Production progress is low ({self.progress_percentage}%).")

        # Check pending quantity
        pending_qty = self.quantity * (remaining_progress / 100.0)
        if pending_qty > 0:
            reasons.append(f"Large quantity ({int(pending_qty)} pcs) is still pending.")

        if required_rate > 20:
            reasons.append(f"Requires high progress speed ({round(required_rate, 1)}% completion per day).")

        if not reasons:
            reasons.append("Production is progressing on target schedule.")
        return reasons

    @property
    def current_stage(self):
        return self.tracking.stage if self.tracking else 'Order Confirmed'

    @property
    def progress_percentage(self):
        return self.tracking.progress_percentage if self.tracking else 0


class ProductionTracking(db.Model):
    __tablename__ = 'production_tracking'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, unique=True)
    stage = db.Column(db.String(80), default='Order Confirmed') 
    # Stages: Order Confirmed -> Fabric Received -> Cutting -> Stitching -> Quality Check -> Packing -> Delivered
    progress_percentage = db.Column(db.Integer, default=10)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Worker(db.Model):
    __tablename__ = 'workers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(80), nullable=False)  # Cutting, Stitching, Quality Check, Packing
    skill = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(30), nullable=True, default='+1 555-0100')
    status = db.Column(db.String(30), default='Available')  # Available, Busy, On Leave
    attendance = db.Column(db.String(30), default='Present')  # Present, Absent, Half Day, Leave

    attendance_records = db.relationship('Attendance', backref='worker', lazy=True)
    performance_records = db.relationship('Performance', backref='worker', lazy=True)


class Manager(db.Model):
    __tablename__ = 'managers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(80), nullable=False)
    contact = db.Column(db.String(30), nullable=True, default='+1 555-0144')


class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)  # Fabric, Cotton, Polyester, Denim, Buttons, Zippers, Labels, Packaging materials
    quantity = db.Column(db.Float, nullable=False, default=0.0)  # meters or units
    unit = db.Column(db.String(20), default='Meters') # Meters, Units, Rolls, Boxes
    minimum_stock = db.Column(db.Float, nullable=False, default=100.0)


class Machine(db.Model):
    __tablename__ = 'machines'
    id = db.Column(db.Integer, primary_key=True)
    machine_name = db.Column(db.String(100), nullable=False)
    machine_type = db.Column(db.String(80), nullable=False)  # Cutting Machine, Sewing Machine, Button Hole, Overlock, Ironing
    status = db.Column(db.String(30), default='Running')  # Running, Idle, Maintenance
    maintenance_date = db.Column(db.DateTime, nullable=True)


class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('workers.id'), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date)
    status = db.Column(db.String(30), default='Present')  # Present, Absent, Half Day, Leave


class Performance(db.Model):
    __tablename__ = 'performance'
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('workers.id'), nullable=False)
    productivity_score = db.Column(db.Float, default=90.0)
    completed_tasks = db.Column(db.Integer, default=0)


class Alert(db.Model):
    __tablename__ = 'alerts'
    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(80), nullable=False)  # Low Inventory, Machine Problem, Worker Shortage, Delay Risk, Production Complete
    message = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='Medium')  # Low, Medium, High, Critical
    status = db.Column(db.String(20), default='Active')  # Active, Resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AIPrediction(db.Model):
    __tablename__ = 'ai_predictions'
    id = db.Column(db.Integer, primary_key=True)
    prediction_type = db.Column(db.String(80), nullable=False)
    input_data = db.Column(db.Text, nullable=False)
    result = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class QRTracking(db.Model):
    __tablename__ = 'qr_tracking'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    tracking_id = db.Column(db.String(80), unique=True, nullable=False) # e.g. TRK-84920
    qr_code_path = db.Column(db.String(255), nullable=False)


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class CustomerUser(UserMixin, db.Model):
    __tablename__ = 'customer_users'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, unique=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    company_name = db.Column(db.String(150), nullable=True)
    contact_name = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    gst_number = db.Column(db.String(50), nullable=True)
    delivery_address = db.Column(db.Text, nullable=True)
    billing_address = db.Column(db.Text, nullable=True)
    profile_photo = db.Column(db.String(255), nullable=True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', backref=db.backref('customer_user', uselist=False, cascade='all, delete-orphan'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f"cust_{self.id}"

    @property
    def role(self):
        return 'customer'

    @property
    def username(self):
        return self.contact_name or self.email



class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Open')  # Open, In Progress, Resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', backref=db.backref('support_tickets', lazy=True, cascade='all, delete-orphan'))


class CustomerFeedback(db.Model):
    __tablename__ = 'customer_feedbacks'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    rating = db.Column(db.Integer, default=5)  # Overall star rating 1-5
    product_rating = db.Column(db.Integer, default=5)
    delivery_rating = db.Column(db.Integer, default=5)
    quality_rating = db.Column(db.Integer, default=5)
    review_text = db.Column(db.Text, nullable=True)
    suggestions = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', backref=db.backref('feedbacks', lazy=True, cascade='all, delete-orphan'))
    order = db.relationship('Order', backref=db.backref('feedbacks', lazy=True, cascade='all, delete-orphan'))


class ProductionDelay(db.Model):
    __tablename__ = 'production_delays'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    reason = db.Column(db.String(80), nullable=False)
    note = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    order = db.relationship('Order', backref=db.backref('delays', lazy=True, cascade='all, delete-orphan'))
    user = db.relationship('User')


class OrderSizeQuantity(db.Model):
    __tablename__ = 'order_size_quantities'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    size = db.Column(db.String(10), nullable=False)  # S, M, L, XL
    planned_quantity = db.Column(db.Integer, nullable=False, default=0)
    completed_quantity = db.Column(db.Integer, nullable=False, default=0)

    order = db.relationship('Order', backref=db.backref('size_quantities', lazy=True, cascade='all, delete-orphan'))


class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    additional_charges = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    tax_percentage = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(20), default='Pending') # Pending, Paid, Partially Paid
    invoice_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order = db.relationship('Order', backref=db.backref('invoice', uselist=False, lazy=True))
    customer = db.relationship('Customer', backref=db.backref('invoices', lazy=True))

    @property
    def derived_rate(self):
        if self.order and self.order.quantity and self.order.quantity > 0:
            return round(self.subtotal / float(self.order.quantity), 2)
        return 0.0



class QualityInspection(db.Model):
    """
    Quality Control Inspection record for a garment order.
    Created by Quality Check workers; read by Owner and Manager.
    """
    __tablename__ = 'quality_inspections'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    inspector_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    inspector_name = db.Column(db.String(120), nullable=True)

    # Quantities
    inspected_qty = db.Column(db.Integer, nullable=False, default=0)
    passed_qty = db.Column(db.Integer, nullable=False, default=0)
    defective_qty = db.Column(db.Integer, nullable=False, default=0)

    # Defect info
    defect_type = db.Column(db.String(80), nullable=True)
    # Choices: Stitching Defect, Fabric Defect, Measurement/Size Issue,
    #          Color Issue, Button/Zipper Issue, Other
    remarks = db.Column(db.Text, nullable=True)

    # Final result
    result = db.Column(db.String(30), nullable=False, default='Passed')
    # Choices: Passed, Rework Required, Rejected

    inspected_at = db.Column(db.DateTime, default=datetime.utcnow)

    order = db.relationship('Order', backref=db.backref('quality_inspections', lazy=True))
    inspector = db.relationship('User', backref=db.backref('quality_inspections', lazy=True))

    @property
    def inspected_quantity(self):
        return self.inspected_qty

    @inspected_quantity.setter
    def inspected_quantity(self, val):
        self.inspected_qty = val

    @property
    def passed_quantity(self):
        return self.passed_qty

    @passed_quantity.setter
    def passed_quantity(self, val):
        self.passed_qty = val

    @property
    def defective_quantity(self):
        return self.defective_qty

    @defective_quantity.setter
    def defective_quantity(self, val):
        self.defective_qty = val



class OnlineOrderRequest(db.Model):
    """
    Customer-submitted online order request.
    Awaits Owner/Manager review before becoming a production Order.
    Status: PENDING -> APPROVED (creates Order) or REJECTED.
    """
    __tablename__ = 'online_order_requests'
    id = db.Column(db.Integer, primary_key=True)
    request_number = db.Column(db.String(30), unique=True, nullable=False)  # e.g. REQ-2026-0001
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)

    # Garment details
    garment_type = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    size_s = db.Column(db.Integer, nullable=False, default=0)
    size_m = db.Column(db.Integer, nullable=False, default=0)
    size_l = db.Column(db.Integer, nullable=False, default=0)
    size_xl = db.Column(db.Integer, nullable=False, default=0)
    fabric_preference = db.Column(db.String(120), nullable=True)
    color = db.Column(db.String(80), nullable=True)
    required_delivery_date = db.Column(db.Date, nullable=False)
    special_requirements = db.Column(db.Text, nullable=True)

    # Workflow
    status = db.Column(db.String(20), nullable=False, default='PENDING')  # PENDING, APPROVED, REJECTED
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Linked production order (set on approval)
    converted_order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)

    # Relationships
    customer = db.relationship('Customer', backref=db.backref('online_order_requests', lazy=True))
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref=db.backref('reviewed_requests', lazy=True))
    converted_order = db.relationship('Order', foreign_keys=[converted_order_id], backref=db.backref('online_request', uselist=False))

    @property
    def display_status(self):
        if self.status in ['ACCEPTED', 'APPROVED']:
            return 'ACCEPTED'
        return self.status


class ProductionCost(db.Model):
    """
    Production cost breakdown for a garment Order.
    Owner-only financial tracking attached to an existing Order.
    """
    __tablename__ = 'production_costs'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, unique=True)
    fabric_cost = db.Column(db.Float, default=0.0, nullable=False)
    labour_cost = db.Column(db.Float, default=0.0, nullable=False)
    machine_cost = db.Column(db.Float, default=0.0, nullable=False)
    other_cost = db.Column(db.Float, default=0.0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = db.relationship('Order', backref=db.backref('cost', uselist=False, cascade='all, delete-orphan'))

    @property
    def total_cost(self):
        return round((self.fabric_cost or 0.0) + (self.labour_cost or 0.0) + (self.machine_cost or 0.0) + (self.other_cost or 0.0), 2)


class SampleMonthlyFinancial(db.Model):
    """
    Isolated sample monthly financial dataset for academic prototype demonstration.
    Stores monthly Revenue and Cost Breakdown (Fabric, Labour, Machine, Other) for Jan 2025 - Oct 2026.
    Does not interfere with real invoices, orders, billing, or production tracking.
    """
    __tablename__ = 'sample_monthly_financials'
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    revenue = db.Column(db.Float, nullable=False, default=0.0)
    fabric_cost = db.Column(db.Float, nullable=False, default=0.0)
    labour_cost = db.Column(db.Float, nullable=False, default=0.0)
    machine_cost = db.Column(db.Float, nullable=False, default=0.0)
    other_cost = db.Column(db.Float, nullable=False, default=0.0)
    is_demo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('year', 'month', name='uq_sample_financial_year_month'),
    )

    @property
    def total_cost(self):
        return round((self.fabric_cost or 0.0) + (self.labour_cost or 0.0) + (self.machine_cost or 0.0) + (self.other_cost or 0.0), 2)

    @property
    def net_result(self):
        return round(self.revenue - self.total_cost, 2)

    @property
    def profit(self):
        return self.net_result if self.net_result > 0 else 0.0

    @property
    def loss(self):
        return abs(self.net_result) if self.net_result < 0 else 0.0

    @property
    def profit_margin(self):
        if self.revenue > 0:
            return round((self.profit / self.revenue) * 100, 2)
        return 0.0


