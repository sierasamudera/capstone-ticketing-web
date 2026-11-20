
import os
import re
import sqlite3

from werkzeug.security import generate_password_hash

from .ticket_state import SCHEMA as TICKET_STATE_SCHEMA

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(_BASE_DIR), "data")


def _default_db_path():
    return os.path.join(DATA_DIR, "ticketing.db")


def _translate_sql(sql):
    """Ubah placeholder SQLite (?) menjadi placeholder psycopg (%s)."""
    return sql.replace("?", "%s")


class _PostgresCursor:
    """Adapter cursor psycopg agar kompatibel dengan pola query aplikasi."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=()):
        self._cursor.execute(_translate_sql(sql), params)
        return self

    def executemany(self, sql, params):
        self._cursor.executemany(_translate_sql(sql), params)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()


class _PostgresConnection:
    """Adapter koneksi psycopg dengan antarmuka mirip sqlite3."""

    def __init__(self, connection, integrity_error):
        self._connection = connection
        self.IntegrityError = integrity_error

    def execute(self, sql, params=()):
        cursor = self._connection.cursor()
        return _PostgresCursor(cursor).execute(sql, params)

    def cursor(self):
        return _PostgresCursor(self._connection.cursor())

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def _connect_postgres(database_url):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "Driver PostgreSQL belum terpasang. Jalankan pip install psycopg[binary]."
        ) from exc

    connection = psycopg.connect(
        database_url,
        row_factory=dict_row,
    )
    return _PostgresConnection(connection, psycopg.IntegrityError)


def get_db_connection():
    from flask import current_app, has_app_context

    if has_app_context():
        backend = current_app.config.get("DB_BACKEND", "sqlite")

        if backend == "postgres":
            database_url = current_app.config.get("DATABASE_URL")
            if not database_url:
                raise RuntimeError("DATABASE_URL belum dikonfigurasi.")
            return _connect_postgres(database_url)

        db_path = current_app.config.get("DB_PATH") or _default_db_path()
    else:
        db_path = _default_db_path()

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _init_sqlite(db_file):
    os.makedirs(os.path.dirname(os.path.abspath(db_file)), exist_ok=True)
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS technicians (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            initial_status TEXT NOT NULL
        )
    """)

    cursor.execute("""
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
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            tech_id TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_status (
            ticket_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            handled_by TEXT,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.executescript(TICKET_STATE_SCHEMA)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parameters (
            id INTEGER PRIMARY KEY,
            priority_weights TEXT NOT NULL,
            shift_start TEXT NOT NULL,
            busy_penalty INTEGER NOT NULL,
            distribution_rule TEXT NOT NULL,
            tie_breaker TEXT NOT NULL,
            fallback_rule TEXT NOT NULL
        )
    """)

    _seed_defaults(cursor, sqlite=True)

    conn.commit()
    conn.close()


def _init_postgres(database_url):
    conn = _connect_postgres(database_url)

    statements = [
        """
        CREATE TABLE IF NOT EXISTS technicians (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            initial_status TEXT NOT NULL
        )
        """,
        """
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
        """,
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            tech_id TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ticket_status (
            ticket_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            handled_by TEXT,
            updated_at TEXT NOT NULL
        )
        """,
        TICKET_STATE_SCHEMA,
        """
                CREATE TABLE IF NOT EXISTS parameters (
            id INTEGER PRIMARY KEY,
            priority_weights TEXT NOT NULL,
            shift_start TEXT NOT NULL,
            busy_penalty INTEGER NOT NULL,
            distribution_rule TEXT NOT NULL,
            tie_breaker TEXT NOT NULL,
            fallback_rule TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS dataset_store (
            id INTEGER PRIMARY KEY,
            payload JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]

    for statement in statements:
        conn.execute(statement)

    _seed_defaults(conn.cursor(), sqlite=False)

    conn.commit()
    conn.close()


def _seed_defaults(cursor, sqlite):
    cursor.execute("SELECT COUNT(*) AS total FROM users")
    row = cursor.fetchone()
    user_count = row["total"] if isinstance(row, dict) else row[0]

    if user_count == 0:
        default_users = [
            ("admin", generate_password_hash("admin123"), "admin", None),
            ("t01", generate_password_hash("tech01"), "technician", "T01"),
            ("t02", generate_password_hash("tech02"), "technician", "T02"),
            ("t03", generate_password_hash("tech03"), "technician", "T03"),
            ("pelapor", generate_password_hash("pelapor123"), "user", None),
        ]

        if sqlite:
            cursor.executemany(
                """
                INSERT OR REPLACE INTO users
                (username, password, role, tech_id)
                VALUES (?, ?, ?, ?)
                """,
                default_users,
            )
        else:
            cursor.executemany(
                """
                INSERT INTO users (username, password, role, tech_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (username) DO NOTHING
                """,
                default_users,
            )

    cursor.execute("SELECT COUNT(*) AS total FROM ticket_status")
    row = cursor.fetchone()
    status_count = row["total"] if isinstance(row, dict) else row[0]

    if status_count == 0:
        if sqlite:
            cursor.execute("""
                INSERT INTO ticket_status
                (ticket_id, status, handled_by, updated_at)
                SELECT id, 'Open', NULL, datetime('now')
                FROM tickets
            """)
        else:
            cursor.execute("""
                INSERT INTO ticket_status
                (ticket_id, status, handled_by, updated_at)
                SELECT id, 'Open', NULL, CURRENT_TIMESTAMP::text
                FROM tickets
            """)

    cursor.execute("SELECT COUNT(*) AS total FROM parameters")
    row = cursor.fetchone()
    parameter_count = row["total"] if isinstance(row, dict) else row[0]

    if parameter_count == 0:
        cursor.execute(
            """
            INSERT INTO parameters (
                id, priority_weights, shift_start, busy_penalty,
                distribution_rule, tie_breaker, fallback_rule
            )
            VALUES (1, ?, ?, ?, ?, ?, ?)
            """,
            (
                '{"Low": 1, "Medium": 2, "High": 3}',
                "2026-09-23 08:00:00",
                1000000,
                "Lowest Active Workload",
                "Technician ID",
                "Earliest Estimated Finish",
            ),
        )


def init_db(db_path=None, backend="sqlite", database_url=None):
    """Inisialisasi schema SQLite atau PostgreSQL."""

    if backend == "postgres":
        if not database_url:
            raise RuntimeError("DATABASE_URL wajib diisi untuk PostgreSQL.")
        _init_postgres(database_url)
        return

    db_file = db_path or _default_db_path()
    _init_sqlite(db_file)
