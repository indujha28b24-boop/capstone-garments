import os
import socket
import qrcode
from datetime import datetime, timedelta
from app import create_app
from app.models import db, User, Customer, Order, ProductionTracking, Worker, Manager, Inventory, Machine, Attendance, Performance, Alert, ActivityLog, QRTracking, CustomerUser

app = create_app()

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def seed_database():
    with app.app_context():
        print("Re-creating database schema...")
        db.drop_all()
        db.create_all()

        qr_folder = app.config['QR_FOLDER']
        os.makedirs(qr_folder, exist_ok=True)

        print("Seeding Users for 6 Dedicated Login Portals...")
        # 1. Owner
        owner_user = User(username='owner', role='owner', department='Executive')
        owner_user.set_password('admin123')

        # 2. Manager
        mgr_user = User(username='manager', role='manager', department='Floor Management')
        mgr_user.set_password('manager123')

        # 3. Department Workers
        cut_user = User(username='cutting_worker01', role='worker', department='Cutting')
        cut_user.set_password('worker123')

        stitch_user = User(username='stitching_worker01', role='worker', department='Stitching')
        stitch_user.set_password('worker123')

        qa_user = User(username='quality_worker01', role='worker', department='Quality Check')
        qa_user.set_password('worker123')

        pack_user = User(username='packing_worker01', role='worker', department='Packing')
        pack_user.set_password('worker123')

        db.session.add_all([owner_user, mgr_user, cut_user, stitch_user, qa_user, pack_user])
        db.session.commit()

        print("Seeding Manager and Department Worker Profiles...")
        mgr_profile = Manager(user_id=mgr_user.id, name='Robert Sterling', department='Floor Management', contact='+1 555-0144')
        db.session.add(mgr_profile)

        w_cut = Worker(user_id=cut_user.id, name='Marcus Vance', department='Cutting', skill='Laser & Pattern Cutting', contact='+1 555-0192', status='Available', attendance='Present')
        w_stitch = Worker(user_id=stitch_user.id, name='Elena Rostova', department='Stitching', skill='Precision High-Speed Sewing', contact='+1 555-0188', status='Busy', attendance='Present')
        w_qa = Worker(user_id=qa_user.id, name='Aisha Patel', department='Quality Check', skill='Garment Inspection & QA', contact='+1 555-0176', status='Busy', attendance='Present')
        w_pack = Worker(user_id=pack_user.id, name='Carlos Santana', department='Packing', skill='Poly-wrapping & Dispatch Shipping', contact='+1 555-0122', status='Available', attendance='Present')

        db.session.add_all([w_cut, w_stitch, w_qa, w_pack])
        db.session.commit()

        # Performance scores
        p1 = Performance(worker_id=w_cut.id, productivity_score=93.5, completed_tasks=34)
        p2 = Performance(worker_id=w_stitch.id, productivity_score=97.0, completed_tasks=52)
        p3 = Performance(worker_id=w_qa.id, productivity_score=95.2, completed_tasks=48)
        p4 = Performance(worker_id=w_pack.id, productivity_score=91.8, completed_tasks=40)

        db.session.add_all([p1, p2, p3, p4])

        # Attendance
        today = datetime.utcnow().date()
        for wrk in [w_cut, w_stitch, w_qa, w_pack]:
            att = Attendance(worker_id=wrk.id, date=today, status='Present')
            db.session.add(att)

        print("Seeding Customers...")
        c1 = Customer(name='Apex Apparel Retailers', phone='+1 800-555-0100', email='procurement@apexapparel.com')
        c2 = Customer(name='Global Denim House', phone='+1 800-555-0200', email='orders@globaldenim.com')
        c3 = Customer(name='Urban Thread Co.', phone='+1 800-555-0300', email='supply@urbanthread.com')
        c4 = Customer(name='Velvet Elegance Couture', phone='+1 800-555-0400', email='buyers@velvetelegance.com')

        db.session.add_all([c1, c2, c3, c4])
        db.session.commit()

        print("Seeding Customer User credentials...")
        cu1 = CustomerUser(customer_id=c1.id, email='procurement@apexapparel.com', company_name='Apex Apparel Retailers', contact_name='Jane Miller', phone='+1 800-555-0100', gst_number='29AAAAA1111A1Z1', delivery_address='45 Logistics Blvd, Sector 4, Chennai, TN', billing_address='HQ Suite 900, Financial District, Mumbai, MH')
        cu1.set_password('customer123')
        
        cu2 = CustomerUser(customer_id=c2.id, email='orders@globaldenim.com', company_name='Global Denim House', contact_name='John Davis', phone='+1 800-555-0200', gst_number='27BBBBB2222B2Z2', delivery_address='Denim Port Complex, Staging Dock B, Mumbai, MH', billing_address='Denim Port Complex, Staging Dock B, Mumbai, MH')
        cu2.set_password('customer123')
        
        cu3 = CustomerUser(customer_id=c3.id, email='supply@urbanthread.com', company_name='Urban Thread Co.', contact_name='Sarah Jenkins', phone='+1 800-555-0300', gst_number='19CCCCC3333C3Z3', delivery_address='Urban Fabric Depot, Kolkata, WB', billing_address='Urban Fabric Depot, Kolkata, WB')
        cu3.set_password('customer123')
        
        cu4 = CustomerUser(customer_id=c4.id, email='buyers@velvetelegance.com', company_name='Velvet Elegance Couture', contact_name='Audrey Hepburn', phone='+1 800-555-0400', gst_number='07DDDDD4444D4Z4', delivery_address='High Fashion Hub, New Delhi, DL', billing_address='High Fashion Hub, New Delhi, DL')
        cu4.set_password('customer123')

        db.session.add_all([cu1, cu2, cu3, cu4])
        db.session.commit()

        print("Seeding Inventory...")
        inv1 = Inventory(item_name='100% Egyptian Cotton Fabric', category='Cotton fabric', quantity=1450.0, unit='Meters', minimum_stock=300.0)
        inv2 = Inventory(item_name='Heavyweight Denim Roll (14oz)', category='Denim', quantity=80.0, unit='Meters', minimum_stock=200.0)  # LOW STOCK
        inv3 = Inventory(item_name='Polyester Blend Yarn Spools', category='Polyester fabric', quantity=620.0, unit='Units', minimum_stock=150.0)
        inv4 = Inventory(item_name='Silk Chiffon Fabric', category='Silk', quantity=450.0, unit='Meters', minimum_stock=100.0)
        inv5 = Inventory(item_name='Antique Brass Metal Buttons', category='Buttons', quantity=4500.0, unit='Units', minimum_stock=1000.0)
        inv6 = Inventory(item_name='YKK Heavy Metallic Zippers (18")', category='Zippers', quantity=75.0, unit='Units', minimum_stock=250.0)  # LOW STOCK
        inv7 = Inventory(item_name='Woven Satin Brand Care Labels', category='Labels', quantity=8500.0, unit='Units', minimum_stock=2000.0)
        inv8 = Inventory(item_name='Transparent Poly-Packaging Bags', category='Packaging materials', quantity=3200.0, unit='Units', minimum_stock=800.0)

        db.session.add_all([inv1, inv2, inv3, inv4, inv5, inv6, inv7, inv8])

        print("Seeding Machines...")
        m1 = Machine(machine_name='Gerber Cutter G-500', machine_type='Cutting Machine', status='Running', maintenance_date=datetime.utcnow() + timedelta(days=20))
        m2 = Machine(machine_name='Juki DDL-9000C Sewing Line A', machine_type='Sewing Machine', status='Running', maintenance_date=datetime.utcnow() + timedelta(days=14))
        m3 = Machine(machine_name='Juki DDL-9000C Sewing Line B', machine_type='Sewing Machine', status='Running', maintenance_date=datetime.utcnow() + timedelta(days=25))
        m4 = Machine(machine_name='Yamato 5-Thread Overlock O-02', machine_type='Overlock Machine', status='Idle', maintenance_date=datetime.utcnow() + timedelta(days=10))
        m5 = Machine(machine_name='Brother Electronic Buttonholer B-01', machine_type='Button Hole', status='Maintenance', maintenance_date=datetime.utcnow() - timedelta(days=1))
        m6 = Machine(machine_name='Veit Industrial Steam Ironing Station', machine_type='Ironing Machine', status='Running', maintenance_date=datetime.utcnow() + timedelta(days=45))

        db.session.add_all([m1, m2, m3, m4, m5, m6])

        print("Seeding Orders, Production Tracking & Unique Tracking IDs...")
        now = datetime.utcnow()
        o1 = Order(customer_id=c1.id, garment_type='Shirts', quantity=1200, order_date=now - timedelta(days=10), deadline=now + timedelta(days=4), status='In Production')
        o2 = Order(customer_id=c2.id, garment_type='Denim', quantity=650, order_date=now - timedelta(days=12), deadline=now + timedelta(days=2), status='In Production')
        o3 = Order(customer_id=c3.id, garment_type='T-Shirts', quantity=2500, order_date=now - timedelta(days=5), deadline=now + timedelta(days=12), status='In Production')
        o4 = Order(customer_id=c4.id, garment_type='Dresses', quantity=400, order_date=now - timedelta(days=15), deadline=now + timedelta(days=8), status='In Production')
        o5 = Order(customer_id=c1.id, garment_type='Jackets', quantity=300, order_date=now - timedelta(days=18), deadline=now - timedelta(days=1), status='Delivered')

        db.session.add_all([o1, o2, o3, o4, o5])
        db.session.commit()

        t1 = ProductionTracking(order_id=o1.id, stage='Stitching', progress_percentage=65)
        t2 = ProductionTracking(order_id=o2.id, stage='Cutting', progress_percentage=30)
        t3 = ProductionTracking(order_id=o3.id, stage='Fabric Received', progress_percentage=15)
        t4 = ProductionTracking(order_id=o4.id, stage='Quality Check', progress_percentage=85)
        t5 = ProductionTracking(order_id=o5.id, stage='Delivered', progress_percentage=100)

        db.session.add_all([t1, t2, t3, t4, t5])
        db.session.commit()

        print("Generating Unique QR Code Tracking IDs...")
        local_ip = get_local_ip()
        for ord_item in [o1, o2, o3, o4, o5]:
            tracking_id = f"TRK-{1000 + ord_item.id}"
            qr_filename = f"order_{ord_item.id}.png"
            qr_path = os.path.join(qr_folder, qr_filename)
            tracking_url = f"http://{local_ip}:5000/track/{tracking_id}"
            img = qrcode.make(tracking_url)
            img.save(qr_path)

            qr_info = QRTracking(order_id=ord_item.id, tracking_id=tracking_id, qr_code_path=f"qrcodes/{qr_filename}")
            db.session.add(qr_info)

        print("Seeding Smart Alerts...")
        a1 = Alert(alert_type='Low Inventory', message='Denim Fabric stock (80m) is below the minimum threshold (200m).', priority='High', status='Active')
        a2 = Alert(alert_type='Machine Maintenance', message='Brother Buttonhole B-01 is currently offline undergoing maintenance.', priority='Medium', status='Active')
        a3 = Alert(alert_type='Delay Risk', message='Order #102 (Denim Jeans) has a 85% probability of deadline delay due to cutting bottleneck.', priority='Critical', status='Active')
        a4 = Alert(alert_type='Completed Orders', message='Order #105 (300 Custom Jackets) successfully packed and dispatched.', priority='Low', status='Resolved')

        db.session.add_all([a1, a2, a3, a4])

        print("Seeding Activity Logs...")
        l1 = ActivityLog(user_id=owner_user.id, action="System initialized with 6 department login portals and QR Tracking IDs")
        l2 = ActivityLog(user_id=mgr_user.id, action="Updated Order #101 production stage to Stitching (65%)")
        l3 = ActivityLog(user_id=qa_user.id, action="QA inspector passed 45 units for Order #104 (Dresses)")

        db.session.add_all([l1, l2, l3])

        db.session.commit()
        print("Database Seeding Completed Successfully!")

if __name__ == '__main__':
    seed_database()
