import sqlite3
from datetime import datetime
from .models import Ticket, Technician, TicketType, Priority, TechStatus

def get_db_connection():
    # SQLite file akan ada di folder data/ticketing.db
    import os
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect('data/ticketing.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
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

    # Seed default users jika tabel users kosong
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        default_users = [
            ('admin', 'admin123', 'admin', None),
            ('t01', 'tech01', 'technician', 'T01'),
            ('t02', 'tech02', 'technician', 'T02'),
            ('t03', 'tech03', 'technician', 'T03'),
            ('t04', 'tech04', 'technician', 'T04'),
            ('pelapor', 'pelapor123', 'user', None),
        ]
        cursor.executemany('INSERT OR REPLACE INTO users (username, password, role, tech_id) VALUES (?, ?, ?, ?)', default_users)

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

def migrate_from_json(dataset):
    conn = get_db_connection()
    cursor = conn.cursor()

    for t in dataset.technicians:
        cursor.execute('INSERT OR REPLACE INTO technicians VALUES (?, ?, ?)',
                       (t.id, t.name, t.initial_status.value))

    for t in dataset.tickets:
        cursor.execute('INSERT OR REPLACE INTO tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (t.id, t.ticket_type.value, t.created_by, t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        t.category, t.detail, t.priority.value, t.duration, t.related_id, t.requested_by))

    conn.commit()
    conn.close()

