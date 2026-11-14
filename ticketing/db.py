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