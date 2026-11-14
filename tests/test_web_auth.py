"""Tes Flask test client untuk auth, role, dan POST /tickets.

Semua tes memakai SALINAN data sementara (tmp_path) untuk tickets.json dan
ticketing.db, jangan pernah menulis ke data/ asli.
"""

from __future__ import annotations

import hashlib
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
    """Membuat test client dari app yang diberikan."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Anonim
# ---------------------------------------------------------------------------

def test_anonim_post_tickets_redirect_login(sha256_check, tmp_env):
    """Anonim POST /tickets harus redirect ke /login."""
    client = _make_client(tmp_env["app"])
    r = client.post(
        "/tickets",
        data={
            "ticket_type": "User Report",
            "timestamp": "2026-09-23T14:00",
            "category": "Network",
            "detail": "tes",
            "priority": "Medium",
            "duration": "30",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


# ---------------------------------------------------------------------------
# User (pelapor)
# ---------------------------------------------------------------------------

def test_user_post_tickets_force_user_report(sha256_check, tmp_env):
    """User POST /tickets dengan ticket_type='Technician Request' -> disimpan sebagai User Report."""
    client = _make_client(tmp_env["app"])
    _login(client, "pelapor", "pelapor123")
    before = _count_tickets(tmp_env["json_path"])
    r = client.post(
        "/tickets",
        data={
            "ticket_type": "Technician Request",  # dipaksa jadi User Report di server
            "timestamp": "2026-09-23T14:00",
            "category": "Network",
            "detail": "tes pelapor",
            "priority": "High",
            "duration": "30",
            "related_id": "T-001",  # diabaikan untuk user
            "requested_by": "T01",  # diabaikan untuk user
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "/dashboard" in r.headers["Location"]

    after = _count_tickets(tmp_env["json_path"])
    assert after == before + 1

    with open(tmp_env["json_path"], encoding="utf-8") as f:
        data = json.load(f)
    new_ticket = data["tickets"][-1]
    assert new_ticket["ticket_type"] == "User Report"
    assert new_ticket["created_by"] == "pelapor"
    assert new_ticket["detail"] == "tes pelapor"
    assert new_ticket["related_id"] is None
    assert new_ticket["requested_by"] is None


def test_user_post_reset_403(sha256_check, tmp_env):
    """User POST /reset harus 403 (hanya admin)."""
    client = _make_client(tmp_env["app"])
    _login(client, "pelapor", "pelapor123")
    r = client.post("/reset", follow_redirects=False)
    assert r.status_code == 403


def test_user_get_run_s1_403(sha256_check, tmp_env):
    """User GET /run/S1 harus 403 (hanya admin)."""
    client = _make_client(tmp_env["app"])
    _login(client, "pelapor", "pelapor123")
    r = client.get("/run/S1", follow_redirects=False)
    assert r.status_code == 403


def test_tiket_baru_muncul_di_dashboard_setelah_reload(sha256_check, tmp_env):
    """Tiket baru muncul di dashboard setelah request berikutnya."""
    client = _make_client(tmp_env["app"])
    _login(client, "pelapor", "pelapor123")
    client.post(
        "/tickets",
        data={
            "ticket_type": "User Report",
            "timestamp": "2026-09-23T14:00",
            "category": "Software",
            "detail": "tes muncul dashboard",
            "priority": "Low",
            "duration": "20",
        },
        follow_redirects=False,
    )
    r = client.get("/dashboard")
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert "tes muncul dashboard" in html


# ---------------------------------------------------------------------------
# Technician
# ---------------------------------------------------------------------------

def test_technician_without_related_id_ditolak(sha256_check, tmp_env):
    """Teknisi POST /tickets tanpa related_id -> ditolak, tidak ada tiket baru."""
    client = _make_client(tmp_env["app"])
    _login(client, "t01", "tech01")
    before = _count_tickets(tmp_env["json_path"])
    r = client.post(
        "/tickets",
        data={
            "ticket_type": "Technician Request",
            "timestamp": "2026-09-23T14:00",
            "category": "Network",
            "detail": "tes teknisi tanpa related",
            "priority": "Medium",
            "duration": "25",
            "requested_by": "T01",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    after = _count_tickets(tmp_env["json_path"])
    assert after == before  # tidak ada tiket baru


def test_technician_with_valid_related_id(sha256_check, tmp_env):
    """Teknisi POST /tickets dengan related_id valid -> tersimpan dengan requested_by = akun login."""
    client = _make_client(tmp_env["app"])
    _login(client, "t01", "tech01")
    before = _count_tickets(tmp_env["json_path"])
    r = client.post(
        "/tickets",
        data={
            "ticket_type": "Technician Request",
            "timestamp": "2026-09-23T14:00",
            "category": "Network",
            "detail": "tes teknisi dengan related",
            "priority": "High",
            "duration": "25",
            "related_id": "T-001",
            "requested_by": "T99",  # diabaikan, diambil dari akun login
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    after = _count_tickets(tmp_env["json_path"])
    assert after == before + 1

    with open(tmp_env["json_path"], encoding="utf-8") as f:
        data = json.load(f)
    new_ticket = data["tickets"][-1]
    assert new_ticket["ticket_type"] == "Technician Request"
    assert new_ticket["created_by"] == "t01"
    assert new_ticket["related_id"] == "T-001"
    assert new_ticket["requested_by"] == "T01"  # dari akun teknisi yang login


def test_technician_related_id_tidak_valid(sha256_check, tmp_env):
    """Teknisi POST /tickets dengan related_id yang tidak ada -> ditolak."""
    client = _make_client(tmp_env["app"])
    _login(client, "t01", "tech01")
    before = _count_tickets(tmp_env["json_path"])
    r = client.post(
        "/tickets",
        data={
            "ticket_type": "Technician Request",
            "timestamp": "2026-09-23T14:00",
            "category": "Network",
            "detail": "tes related tidak valid",
            "priority": "Medium",
            "duration": "25",
            "related_id": "T-999",  # tidak ada di dataset
            "requested_by": "T01",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    after = _count_tickets(tmp_env["json_path"])
    assert after == before  # tidak ada tiket baru


def test_technician_get_run_s1_403(sha256_check, tmp_env):
    """Teknisi GET /run/S1 harus 403 (hanya admin)."""
    client = _make_client(tmp_env["app"])
    _login(client, "t01", "tech01")
    r = client.get("/run/S1", follow_redirects=False)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

def test_admin_post_tickets_ok(sha256_check, tmp_env):
    """Admin POST /tickets berhasil (perilaku seperti sekarang)."""
    client = _make_client(tmp_env["app"])
    _login(client, "admin", "admin123")
    before = _count_tickets(tmp_env["json_path"])
    r = client.post(
        "/tickets",
        data={
            "ticket_type": "User Report",
            "timestamp": "2026-09-23T14:00",
            "category": "Network",
            "detail": "tes admin",
            "priority": "High",
            "duration": "30",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    after = _count_tickets(tmp_env["json_path"])
    assert after == before + 1


def test_admin_get_run_s1_ok(sha256_check, tmp_env):
    """Admin GET /run/S1 berhasil."""
    client = _make_client(tmp_env["app"])
    _login(client, "admin", "admin123")
    r = client.get("/run/S1", follow_redirects=False)
    assert r.status_code == 200


def _login(client, username, password):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )