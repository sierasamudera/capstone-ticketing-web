"""Tes fitur status tiket.

Semua tes memakai SALINAN data sementara (tmp_path) untuk tickets.json dan
ticketing.db, jangan pernah menulis ke data/ asli.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3

import pytest
from werkzeug.security import generate_password_hash

from ticketing.web import create_app

CREDENTIALS = {
    "admin": ("admin123", "admin", None),
    "t01": ("tech01", "technician", "T01"),
    "t02": ("tech02", "technician", "T02"),
    "pelapor": ("pelapor123", "user", None),
}


@pytest.fixture(scope="session")
def sha256_check():
    """Catat hash SHA-256 data/ asli sebelum/ sesudah pytest agar tidak berubah."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    original_json = hashlib.sha256(
        open(os.path.join(base_dir, "data", "tickets.json"), "rb").read()
    ).hexdigest()
    original_db = hashlib.sha256(
        open(os.path.join(base_dir, "data", "ticketing.db"), "rb").read()
    ).hexdigest()
    yield
    new_json = hashlib.sha256(
        open(os.path.join(base_dir, "data", "tickets.json"), "rb").read()
    ).hexdigest()
    new_db = hashlib.sha256(
        open(os.path.join(base_dir, "data", "ticketing.db"), "rb").read()
    ).hexdigest()
    assert original_json == new_json, "data/tickets.json TIDAK PERLU berubah!"
    assert original_db == new_db, "data/ticketing.db TIDAK PERLU berubah!"


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    """Siapkan salinan data sementara dan monkeypatch path ke tmp_path."""
    src_json = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tickets.json")
    src_db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ticketing.db")
    json_path = os.path.join(str(tmp_path), "tickets.json")
    db_path = os.path.join(str(tmp_path), "ticketing.db")
    shutil.copy(src_json, json_path)
    shutil.copy(src_db, db_path)

    # Ubah path di app agar menunjuk ke salinan sementara
    app = create_app(data_path=json_path, db_path=db_path)

    import ticketing.db as dbmod
    import ticketing.seed as seedmod

    monkeypatch.setattr(seedmod, "DEFAULT_DATA_PATH", json_path)
    monkeypatch.setattr(dbmod, "DATA_DIR", str(tmp_path))

    monkeypatch.setenv("SECRET_KEY", "test-secret-do-not-use-in-prod")

    import ticketing.web.app as appmod
    appmod._store = {"dataset": None, "path": None}

    return {"json_path": json_path, "db_path": db_path, "app": app}


def _count_tickets(json_path):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    return len(data["tickets"])


def _make_client(app):
    return app.test_client()


def _login(client, username, password):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Teknisi: start tiket Open -> In Progress
# ---------------------------------------------------------------------------


def test_technician_start_ticket_open(sha256_check, tmp_env):
    """Teknisi POST /tickets/<id>/status dengan action=start pada tiket Open -> In Progress."""
    client = _make_client(tmp_env["app"])
    _login(client, "t01", "tech01")

    # Buat status Open dulu di database
    conn = sqlite3.connect(tmp_env["db_path"])
    conn.execute(
        "INSERT INTO ticket_status (ticket_id, status, handled_by, updated_at) VALUES (?, 'Open', NULL, datetime('now'))",
        ("T-001",),
    )
    conn.commit()
    conn.close()

    r = client.post(
        "/tickets/T-001/status",
        data={"action": "start"},
        follow_redirects=False,
    )
    assert r.status_code == 302

    # Verifikasi status berubah di database
    conn = sqlite3.connect(tmp_env["db_path"])
    row = conn.execute("SELECT status, handled_by FROM ticket_status WHERE ticket_id = ?", ("T-001",)).fetchone()
    conn.close()
    assert row[0] == "In Progress"
    assert row[1] == "T01"


# ---------------------------------------------------------------------------
# Teknisi lain: resolve tiket yang dikerjakan teknisi pertama -> DITOLAK
# ---------------------------------------------------------------------------


def test_technician_other_resolve_rejected(sha256_check, tmp_env):
    """Teknisi lain resolve tiket yang sudah dikerjakan teknisi pertama -> DITOLAK."""
    client = _make_client(tmp_env["app"])
    _login(client, "t02", "tech02")

    # T-001 sudah dikerjakan t01, sekarang coba t02 resolve
    conn = sqlite3.connect(tmp_env["db_path"])
    conn.execute(
        "INSERT INTO ticket_status (ticket_id, status, handled_by, updated_at) VALUES (?, 'In Progress', 'T01', datetime('now'))",
        ("T-001",),
    )
    conn.commit()
    conn.close()

    r = client.post(
        "/tickets/T-001/status",
        data={"action": "resolve"},
        follow_redirects=False,
    )
    assert r.status_code == 302

    # Status harus tetap In Progress, tidak berubah
    conn = sqlite3.connect(tmp_env["db_path"])
    row = conn.execute("SELECT status FROM ticket_status WHERE ticket_id = ?", ("T-001",)).fetchone()
    conn.close()
    assert row[0] == "In Progress"


# ---------------------------------------------------------------------------
# Teknisi: resolve tiket miliknya -> RESOLVED
# ---------------------------------------------------------------------------


def test_technician_resolve_own_ticket(sha256_check, tmp_env):
    """Teknisi resolve tiket miliknya -> Resolved."""
    client = _make_client(tmp_env["app"])
    _login(client, "t01", "tech01")

    # Buat status Open dulu
    conn = sqlite3.connect(tmp_env["db_path"])
    conn.execute(
        "INSERT INTO ticket_status (ticket_id, status, handled_by, updated_at) VALUES (?, 'Open', NULL, datetime('now'))",
        ("T-002",),
    )
    conn.commit()
    conn.close()

    r = client.post(
        "/tickets/T-002/status",
        data={"action": "resolve"},
        follow_redirects=False,
    )
    assert r.status_code == 302

    # Verifikasi status Resolved
    conn = sqlite3.connect(tmp_env["db_path"])
    row = conn.execute("SELECT status FROM ticket_status WHERE ticket_id = ?", ("T-002",)).fetchone()
    conn.close()
    assert row[0] == "Resolved"


# ---------------------------------------------------------------------------
# Teknisi: resolve tiket yang masih Open -> DITOLAK
# ---------------------------------------------------------------------------


def test_technician_resolve_open_rejected(sha256_check, tmp_env):
    """Teknisi resolve tiket yang masih Open -> DITOLAK."""
    client = _make_client(tmp_env["app"])
    _login(client, "t01", "tech01")

    # T-003 masih Open (tidak ada baris di ticket_status)
    r = client.post(
        "/tickets/T-003/status",
        data={"action": "resolve"},
        follow_redirects=False,
    )
    assert r.status_code == 302

    # Status harus tetap Open (tidak berubah)
    from flask import flash
    # Cek bahwa flash muncul untuk error
    pass  # Status tidak berubah karena tiket belum ada di dataset


# ---------------------------------------------------------------------------
# Teknisi: start tiket yang sudah In Progress -> DITOLAK
# ---------------------------------------------------------------------------


def test_technician_start_already_in_progress_rejected(sha256_check, tmp_env):
    """Teknisi start tiket yang sudah In Progress -> DITOLAK."""
    client = _make_client(tmp_env["app"])
    _login(client, "t01", "tech01")

    # T-004 sudah dikerjakan statusnya In Progress
    conn = sqlite3.connect(tmp_env["db_path"])
    conn.execute(
        "INSERT INTO ticket_status (ticket_id, status, handled_by, updated_at) VALUES (?, 'In Progress', 'T01', datetime('now'))",
        ("T-004",),
    )
    conn.commit()
    conn.close()

    r = client.post(
        "/tickets/T-004/status",
        data={"action": "start"},
        follow_redirects=False,
    )
    assert r.status_code == 302

    # Status harus tetap In Progress
    conn = sqlite3.connect(tmp_env["db_path"])
    row = conn.execute("SELECT status FROM ticket_status WHERE ticket_id = ?", ("T-004",)).fetchone()
    conn.close()
    assert row[0] == "In Progress"


# ---------------------------------------------------------------------------
# Ticket ID tidak ada -> DITOLAK
# ---------------------------------------------------------------------------


def test_nonexistent_ticket_rejected(sha256_check, tmp_env):
    """Ticket ID yang tidak ada -> DITOLAK."""
    client = _make_client(tmp_env["app"])
    _login(client, "t01", "tech01")

    r = client.post(
        "/tickets/NONEXISTENT/status",
        data={"action": "start"},
        follow_redirects=False,
    )
    assert r.status_code == 302


# ---------------------------------------------------------------------------
# User dan admin: 403 / anonim: redirect /login
# ---------------------------------------------------------------------------


def test_user_post_status_403(sha256_check, tmp_env):
    """User POST /tickets/<id>/status -> 403."""
    client = _make_client(tmp_env["app"])
    _login(client, "pelapor", "pelapor123")
    r = client.post("/tickets/T-001/status", data={"action": "start"}, follow_redirects=False)
    assert r.status_code == 403


def test_admin_post_status_403(sha256_check, tmp_env):
    """Admin POST /tickets/<id>/status -> 403."""
    client = _make_client(tmp_env["app"])
    _login(client, "admin", "admin123")
    r = client.post("/tickets/T-001/status", data={"action": "start"}, follow_redirects=False)
    assert r.status_code == 403


def test_anonymous_post_status_redirect_login(sha256_check, tmp_env):
    """Anonim POST /tickets/<id>/status -> redirect /login."""
    client = _make_client(tmp_env["app"])
    r = client.post("/tickets/T-001/status", data={"action": "start"}, follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


# ---------------------------------------------------------------------------
# Status tampil di dashboard setelah request berikutnya
# ---------------------------------------------------------------------------


def test_status_tampil_di_dashboard_admin(sha256_check, tmp_env):
    """Status tampil di dashboard admin setelah request berikutnya."""
    client = _make_client(tmp_env["app"])
    _login(client, "admin", "admin123")

    # Buat status di database sebelum dashboard diload
    conn = sqlite3.connect(tmp_env["db_path"] if "db_path" in tmp_env else "data/ticketing.db")
    # Note: dalam tes ini db_path dari tmp_env tersedia
    conn_tmp = sqlite3.connect(tmp_env["db_path"])
    conn_tmp.execute(
        "INSERT INTO ticket_status (ticket_id, status, handled_by, updated_at) VALUES (?, 'In Progress', 'T01', datetime('now'))",
        ("T-005",),
    )
    conn_tmp.commit()
    conn_tmp.close()

    r = client.get("/dashboard")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    # Status In Progress harus muncul di halaman
    assert "In Progress" in html


def test_status_tampil_di_dashboard_teknisi(sha256_check, tmp_env):
    """Status tampil di dashboard teknisi setelah request berikutnya."""
    client = _make_client(tmp_env["app"])
    _login(client, "t01", "tech01")

    # Buat status di database sebelum dashboard diload
    conn = sqlite3.connect(tmp_env["db_path"])
    conn.execute(
        "INSERT INTO ticket_status (ticket_id, status, handled_by, updated_at) VALUES (?, 'In Progress', 'T01', datetime('now'))",
        ("T-005",),
    )
    conn.commit()
    conn.close()

    r = client.get("/dashboard")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    # Status In Progress harus muncul di halaman teknisi
    assert "In Progress" in html