from flask import Flask
from flask_login import LoginManager
from app.config import Config
from app.models import db, User, CustomerUser

login_manager = LoginManager()
login_manager.login_view = 'auth.login_owner'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith('cust_'):
        return CustomerUser.query.get(int(user_id.replace('cust_', '')))
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    config_class.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)

    # Register Blueprints
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.owner.routes import owner_bp
    from app.manager.routes import manager_bp
    from app.worker.routes import worker_bp
    from app.customer.routes import customer_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(owner_bp, url_prefix='/owner')
    app.register_blueprint(manager_bp, url_prefix='/manager')
    app.register_blueprint(worker_bp, url_prefix='/worker')
    app.register_blueprint(customer_bp, url_prefix='/customer')

    with app.app_context():
        db.create_all()

    from app.billing_pdf import format_inr
    @app.template_filter('format_inr')
    def format_inr_filter(amount):
        return format_inr(amount, symbol='₹')

    import socket
    @app.context_processor
    def inject_lan_ip():
        def get_lan_ip():
            try:
                # Dummy connection to get the outgoing interface IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                return '127.0.0.1'
        return dict(get_lan_ip=get_lan_ip)

    @app.context_processor
    def inject_deadline_notifications():
        try:
            from flask import session
            from flask_login import current_user
            if current_user.is_authenticated and getattr(current_user, 'role', None) in ['owner', 'manager', 'worker']:
                from app.deadline_service import DeadlineNotificationService
                read_ids = session.get('read_deadline_notifs', [])
                notifs = DeadlineNotificationService.get_notifications_for_user(current_user, read_ids=read_ids)
                unread_count = sum(1 for n in notifs if not n.get('is_read'))
                return dict(
                    deadline_notifications=notifs,
                    deadline_unread_count=unread_count,
                    deadline_active_count=len(notifs)
                )
        except Exception:
            pass
        return dict(
            deadline_notifications=[],
            deadline_unread_count=0,
            deadline_active_count=0
        )

    return app
