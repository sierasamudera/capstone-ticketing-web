"""Sistem autentikasi role-based (login/register/logout) untuk Flask app.

Akun di-load dari tabel users di SQLite database (data/ticketing.db),
sehingga kredensial & role persisten di server. Tabel users di-seed oleh
ticketing.db.init_db().

Role:
    admin        -> akses penuh (kelola teknisi, simulasi, semua tiket)
    technician   -> akses ke tiket yang ditugaskan ke teknisi ybs
    user/pelapor -> akses ke tiket yang dibuat oleh diri sendiri
"""

from __future__ import annotations

from functools import wraps
from typing import Optional

from flask import abort, flash, redirect, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db_connection

_login_manager: Optional[LoginManager] = None


class AuthUser(UserMixin):
    """User session — mengikuti kontrak Flask-Login UserMixin."""

    __slots__ = ("username", "role", "tech_id")

    def __init__(self, username: str, role: str, tech_id: Optional[str]):
        self.username = username
        self.role = role
        self.tech_id = tech_id

    def get_id(self) -> str:
        return self.username

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_technician(self) -> bool:
        return self.role == "technician"

    def is_reporter(self) -> bool:
        return self.role == "user"


def init_login_manager(app) -> LoginManager:
    """Buat & konfigurasi LoginManager untuk Flask app."""
    lm = LoginManager()
    lm.init_app(app)
    lm.login_view = "login"
    lm.login_message = "Silakan login terlebih dahulu."
    lm.login_message_category = "warning"

    @lm.user_loader
    def load_user(user_id):
        return _fetch_user(user_id)

    return lm


def _fetch_user(username: str) -> Optional[AuthUser]:
    if not username:
        return None
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT username, password, role, tech_id FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return AuthUser(row["username"], row["role"], row["tech_id"])


def authenticate(username: str, password: str) -> Optional[AuthUser]:
    """Cek kredensial: password di DB sudah di-hash (werkzeug).

    Jika password di DB masih plain-text (data lama / migrasi), tetap
    diterima lalu di-upgrade ke hash secara otomatis.
    """
    if not username or not password:
        return None
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT username, password, role, tech_id FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    stored = row["password"]
    if stored.startswith(("pbkdf2:", "scrypt:")):
        ok = check_password_hash(stored, password)
    else:
        # fallback: plain-text (data lama) — validasi manual, lalu upgrade
        ok = stored == password
        if ok:
            _upgrade_password_hash(row["username"], stored)
    if not ok:
        return None
    return AuthUser(row["username"], row["role"], row["tech_id"])


def _upgrade_password_hash(username: str, plain_password: str) -> None:
    """Ganti password plain-text di DB menjadi hash (one-way)."""
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (generate_password_hash(plain_password), username),
        )
        conn.commit()
    finally:
        conn.close()


def do_login(user: AuthUser) -> None:
    login_user(user, remember=False)
    session["role"] = user.role
    session["tech_id"] = user.tech_id


def do_logout() -> None:
    logout_user()
    session.pop("role", None)
    session.pop("tech_id", None)


def register_user(username: str, password: str, role: str = "user") -> AuthUser:
    """Daftarkan akun pelapor baru ke tabel users (SQLite).

    Hanya role ``user`` (pelapor) yang boleh didaftarkan melalui halaman
    register. Admin dan teknisi dibuat oleh admin lewat menu manajemen, supaya
    daftar teknisi tetap terkontrol (mesin distribusi butuh daftar teknisi
    aktif yang valid). Password di-hash dengan werkzeug sebelum disimpan.
    """
    if role != "user":
        raise ValueError("Role 'user' (pelapor) satu-satunya role yang bisa didaftarkan.")
    if not username or not password:
        raise ValueError("Username dan password wajib diisi.")
    if len(password) < 4:
        raise ValueError("Password minimal 4 karakter.")
    from .db import get_db_connection

    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            raise ValueError(f"Username '{username}' sudah terdaftar.")
        conn.execute(
            "INSERT INTO users (username, password, role, tech_id) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(password), role, None),
        )
        conn.commit()
    finally:
        conn.close()
    return AuthUser(username, role, None)


def login_required(role: Optional[str] = None):
    def wrapper(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("login"))
            if role and current_user.role != role:
                abort(403)
            return fn(*args, **kwargs)

        return wrapped

    return wrapper


def require_any_role(roles):
    def wrapper(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("login"))
            if current_user.role not in roles:
                flash("Anda tidak memiliki akses untuk halaman ini.", "error")
                return redirect(url_for("index"))
            return fn(*args, **kwargs)

        return wrapped

    return wrapper
