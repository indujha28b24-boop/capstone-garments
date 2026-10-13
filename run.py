import os
import socket
from app import create_app
from seed import seed_database

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

def migrate_db():
    import sqlite3
    db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'garment_erp.db')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(orders)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'priority_override' not in columns:
                cursor.execute("ALTER TABLE orders ADD COLUMN priority_override VARCHAR(20)")
                conn.commit()
                print("Successfully added priority_override column to orders table.")
        except Exception as e:
            print("Migration warning:", e)
        finally:
            conn.close()

if __name__ == '__main__':
    db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'garment_erp.db')
    if not os.path.exists(db_path):
        print("Database file not found. Seeding initial database...")
        seed_database()
    else:
        migrate_db()

    local_ip = get_local_ip()

    print("\n=======================================================")
    print("STITCHTECH AI GARMENT PRODUCTION ERP SYSTEM IS ONLINE")
    print(f"Desktop Local URL : http://127.0.0.1:5000")
    print(f"Mobile Wi-Fi URL  : http://{local_ip}:5000")
    print("=======================================================\n")

    # Host on 0.0.0.0 so mobile phones on the same Wi-Fi can connect to Safari
    app.run(host='0.0.0.0', port=5000, debug=True)
