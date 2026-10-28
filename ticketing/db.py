import sqlite3
from datetime import datetime
from .models import Ticket, Technician, TicketType, Priority, TechStatus

def get_db_connection():
    # SQLite file akan ada di folder data/ticketing.db
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
