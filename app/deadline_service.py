from datetime import datetime, timedelta
from app.models import Order, Worker

class DeadlineNotificationService:
    """
    In-App Order Deadline Notification Service.
    Calculates notifications dynamically from existing Order deadline data and current date.
    Does not require duplicate database tables or external background schedulers.
    """

    @staticmethod
    def calculate_deadline_info(order, current_date=None):
        """
        Calculate deadline status and notification payload for a single order.
        Returns None if order is completed/delivered or deadline > 3 days.
        """
        # Do not generate overdue/deadline warnings for orders that are already Delivered/Completed
        if not order:
            return None

        status = getattr(order, 'status', '')
        if status in ['Delivered', 'Completed'] or getattr(order, 'progress_percentage', 0) >= 100:
            return None

        if current_date is None:
            current_date = datetime.utcnow().date()
        elif isinstance(current_date, datetime):
            current_date = current_date.date()

        deadline_date = order.deadline.date() if isinstance(order.deadline, datetime) else order.deadline
        days_remaining = (deadline_date - current_date).days

        # Rules:
        # More than 3 days remaining: No urgent deadline notification is required.
        if days_remaining > 3:
            return None

        customer_name = order.customer.name if order.customer else 'Unknown Customer'
        stage = order.current_stage or 'Order Confirmed'
        progress = getattr(order, 'progress_percentage', 0)

        # 3 days remaining: WARNING
        if days_remaining == 3:
            level = 'WARNING'
            due_text = 'Deadline in 3 days'
            short_message = f"Order #{order.id} deadline is in 3 days."
            worker_due = "deadline is in 3 days"
            badge_class = 'warning'
            badge_style = 'background-color: #f59e0b; color: #1e293b;'
            icon = 'bi-exclamation-triangle-fill'
            severity = 1

        # 2 days remaining: WARNING
        elif days_remaining == 2:
            level = 'WARNING'
            due_text = 'Deadline in 2 days'
            short_message = f"Order #{order.id} deadline is in 2 days."
            worker_due = "deadline is in 2 days"
            badge_class = 'warning'
            badge_style = 'background-color: #f59e0b; color: #1e293b;'
            icon = 'bi-exclamation-triangle-fill'
            severity = 1

        # 1 day remaining: URGENT
        elif days_remaining == 1:
            level = 'URGENT'
            due_text = 'Due Tomorrow'
            short_message = f"Order #{order.id} is due tomorrow."
            worker_due = "is due tomorrow"
            badge_class = 'orange'
            badge_style = 'background-color: #f97316; color: #ffffff;'
            icon = 'bi-clock-fill'
            severity = 2

        # Deadline is today: CRITICAL
        elif days_remaining == 0:
            level = 'CRITICAL'
            due_text = 'Due Today'
            short_message = f"Order #{order.id} is due today."
            worker_due = "is due today"
            badge_class = 'danger'
            badge_style = 'background-color: #dc2626; color: #ffffff;'
            icon = 'bi-exclamation-circle-fill'
            severity = 3

        # Deadline has passed and order not completed/delivered: OVERDUE
        else:
            level = 'OVERDUE'
            days_overdue = abs(days_remaining)
            if days_overdue == 1:
                due_text = 'Overdue by 1 day'
                short_message = f"Order #{order.id} has passed its deadline (overdue by 1 day)."
                worker_due = "has passed its deadline (overdue by 1 day)"
            else:
                due_text = f'Overdue by {days_overdue} days'
                short_message = f"Order #{order.id} has passed its deadline (overdue by {days_overdue} days)."
                worker_due = f"has passed its deadline (overdue by {days_overdue} days)"
            badge_class = 'dark-danger'
            badge_style = 'background-color: #991b1b; color: #ffffff;'
            icon = 'bi-slash-circle-fill'
            severity = 4

        # Specific message representations for Owner, Manager, and Worker
        owner_message = f"{level}: Order #{order.id} - {customer_name} ({order.garment_type}). Deadline: {order.deadline.strftime('%d %b %Y')}. Current Stage: {stage}. {due_text}."
        manager_message = f"{level}: Order #{order.id} ({order.garment_type}, {order.quantity:,} pcs). Deadline: {order.deadline.strftime('%d %b %Y')}. Stage: {stage} ({progress}%). {due_text}."
        worker_message = f"{level}: Order #{order.id} assigned to {stage} {worker_due}."

        return {
            'id': f"deadline-ord-{order.id}",
            'order_id': order.id,
            'customer_name': customer_name,
            'garment_type': order.garment_type,
            'quantity': order.quantity,
            'deadline': order.deadline,
            'deadline_str': order.deadline.strftime('%d %b %Y'),
            'current_stage': stage,
            'progress_percentage': progress,
            'level': level,
            'severity': severity,
            'days_remaining': days_remaining,
            'due_text': due_text,
            'message': short_message,
            'owner_message': owner_message,
            'manager_message': manager_message,
            'worker_message': worker_message,
            'badge_class': badge_class,
            'badge_style': badge_style,
            'icon': icon,
        }

    @staticmethod
    def is_order_relevant_to_worker(order, worker_dept):
        """
        Check if an order is relevant to the worker's existing department.
        Existing worker departments include: Cutting, Stitching, Quality Check / Quality, Packing.
        """
        if not worker_dept:
            return False

        w_dept = worker_dept.strip().lower()
        stage = (order.current_stage or '').strip().lower()

        # Exact match
        if w_dept == stage:
            return True

        # Quality Check / QA / Quality variants
        if 'quality' in w_dept and 'quality' in stage:
            return True

        # Substring containment
        if w_dept in stage or stage in w_dept:
            return True

        return False

    @staticmethod
    def get_notifications_for_user(user, current_date=None, read_ids=None):
        """
        Dynamically calculates active deadline notifications for the authenticated user.
        - Owner: all active orders.
        - Manager: all active production orders.
        - Worker: only orders relevant to worker's department.
        - Customer: empty list (internal production notifications only).
        """
        if not user or not getattr(user, 'is_authenticated', False):
            return []

        role = getattr(user, 'role', None)
        if role not in ['owner', 'manager', 'worker']:
            return []

        if read_ids is None:
            read_ids = set()
        elif not isinstance(read_ids, set):
            read_ids = set(read_ids)

        # Retrieve active orders (exclude Delivered)
        active_orders = Order.query.filter(Order.status != 'Delivered').order_by(Order.deadline.asc()).all()

        worker_dept = None
        if role == 'worker':
            if hasattr(user, 'worker_profile') and user.worker_profile:
                worker_dept = user.worker_profile.department
            else:
                worker_dept = getattr(user, 'department', None)

        notifications = []
        for order in active_orders:
            info = DeadlineNotificationService.calculate_deadline_info(order, current_date=current_date)
            if not info:
                continue

            item = dict(info)
            if role == 'worker':
                # Filter to only relevant worker department
                if not DeadlineNotificationService.is_order_relevant_to_worker(order, worker_dept):
                    continue
                item['display_message'] = info['worker_message']
                item['target_url'] = '/worker/dashboard'
            elif role == 'manager':
                item['display_message'] = info['manager_message']
                item['target_url'] = '/manager/orders'
            else:  # owner
                item['display_message'] = info['owner_message']
                item['target_url'] = '/owner/orders'

            item['is_read'] = item['id'] in read_ids
            notifications.append(item)

        # Sort: OVERDUE / CRITICAL first (highest severity), then closest days_remaining
        notifications.sort(key=lambda x: (-x['severity'], x['days_remaining']))
        return notifications
