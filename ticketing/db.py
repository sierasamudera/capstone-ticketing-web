import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

from .models import Ticket, Technician, TicketType, Priority, TechStatus

# Path absolut berbasis __file__ agar aman di semua working directory
# (terutama PythonAnywhere di Linux).
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(_BASE_DIR), "data")

from flask import current_app, has_app_context


def _default_db_path():
    return os.path.join(DATA_DIR, "ticketing.db")


def _default_data_path():
    return os.path.join(DATA_DIR, "tickets.json")


def get_db_connection():
    db_path = current_app.config.get("DB_PATH") if has_app_context() else None
    db_path = db_path or _default_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    # Selalu gunakan path absolut agar CREATE TABLE IF NOT EXISTS bekerja
    db_file = db_path if db_path else _default_db_path()
    os.makedirs(os.path.dirname(db_file), exist_ok=True)
    conn = sqlite3.connect(db_file)

    cursor = conn.cursor()

    # Buat tabel Teknisi
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technicians (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            initial_status TEXT NOT NULL
        )
    ''')

    # Buat tabel Tiket
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            ticket_type TEXT NOT NULL,
            created_by TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            category TEXT NOT NULL,
            detail TEXT NOT NULL,
            priority TEXT NOT NULL,
            duration INTEGER NOT NULL,
            related_id TEXT,
            requested_by TEXT
        )
    ''')

    # Buat tabel Users untuk autentikasi role-based
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            tech_id TEXT
        )
    ''')

    # Buat tabel Status Tiket (fitur penanganan oleh teknisi)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_status (
            ticket_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            handled_by TEXT,
            updated_at TEXT NOT NULL
        )
    ''')

    # Seed default users jika tabel users kosong.
    # Password di-hash (werkzeug) — lihat README untuk kredensial demo.
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        default_users = [
            ('admin', generate_password_hash('admin123'), 'admin', None),
            ('t01', generate_password_hash('tech01'), 'technician', 'T01'),
            ('t02', generate_password_hash('tech02'), 'technician', 'T02'),
            ('t03', generate_password_hash('tech03'), 'technician', 'T03'),
            ('pelapor', generate_password_hash('pelapor123'), 'user', None),
        ]
        cursor.executemany('INSERT OR REPLACE INTO users (username, password, role, tech_id) VALUES (?, ?, ?, ?)', default_users)

    # Seed default status jika tabel ticket_status kosong
    cursor.execute('SELECT COUNT(*) FROM ticket_status')
    if cursor.fetchone()[0] == 0:
        # Set default status Open untuk semua tiket yang sudah ada
        cursor.execute('''
            INSERT INTO ticket_status (ticket_id, status, handled_by, updated_at)
            SELECT id, 'Open', NULL, datetime('now')
            FROM tickets
        ''')

    # Buat tabel Parameters (sheet Parameter Excel) — simpan di DB
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parameters (
            id INTEGER PRIMARY KEY,
            priority_weights TEXT NOT NULL,
            shift_start TEXT NOT NULL,
            busy_penalty INTEGER NOT NULL,
            distribution_rule TEXT NOT NULL,
            tie_breaker TEXT NOT NULL,
            fallback_rule TEXT NOT NULL
        )
    ''')

    # Seed parameter default jika tabel kosong
    cursor.execute('SELECT COUNT(*) FROM parameters')
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            'INSERT INTO parameters (id, priority_weights, shift_start, busy_penalty, distribution_rule, tie_breaker, fallback_rule) VALUES (1, ?, ?, ?, ?, ?, ?)',
            ('{"Low": 1, "Medium": 2, "High": 3}', '2026-09-23 08:00:00', 1000000, 'Lowest Active Workload', 'Technician ID', 'Earliest Estimated Finish'),
        )

    conn.commit()
    conn.close()