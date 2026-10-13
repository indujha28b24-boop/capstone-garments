import os
import socket


def _detect_lan_ip():
    """
    Detect the LAN IP of this machine so QR codes embed an address
    reachable by phones on the same Wi-Fi network.
    Falls back to 127.0.0.1 only when no network is available.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'stichtech-garment-erp-secret-key-2026-secure'
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f"sqlite:///{os.path.join(BASE_DIR, 'garment_erp.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # QR Code & Artifact Storage
    QR_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'qrcodes')
    REPORTS_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'reports')

    # ---------------------------------------------------------------
    # QR Base URL – the root URL encoded inside every QR code image.
    #
    # Priority:
    #   1. QR_BASE_URL env variable  → set this in production to your
    #      deployed domain, e.g. https://stitchtech.example.com
    #   2. Auto-detected LAN IP      → works for mobile QR scanning
    #      on the same Wi-Fi network during local development.
    #
    # This is intentionally NOT request.host_url because that reflects
    # what the *browser* used to connect (often 127.0.0.1), which is
    # unreachable from any other device.
    # ---------------------------------------------------------------
    QR_BASE_URL = (
        os.environ.get('QR_BASE_URL')
        or f"http://{_detect_lan_ip()}:5000"
    )

    @staticmethod
    def init_app(app):
        os.makedirs(Config.QR_FOLDER, exist_ok=True)
        os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)
