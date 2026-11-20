"""Tes status tiket oleh teknisi dan penugasan ulang oleh admin.

Semua tes memakai salinan data sementara (tmp_path); data asli tidak disentuh.
"""

import os
import shutil
import sqlite3
from types import SimpleNamespace

import pytest

import ticketing.web.app as appmod
from ticketing import ticket_state as ts
from ticketing.db import get_db_connection
from ticketing.seed import load_dataset
from ticketing.simulation import Simulation
from ticketing.web import create_app

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_JSON = os.path.join(BASE, "data", "tickets.json")
USERS = {"T01": ("t01", "tech01"), "T02": ("t02", "tech02"), "T03": ("t03", "tech03")}


@pytest.fixture
def env(tmp_path, monkeypatch):
    json_path = str(tmp_path / "tickets.json")
    db_path = str(tmp_path / "ticketing.db")
    shutil.copy(SRC_JSON, json_path)
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    appmod._store["dataset"] = None
    appmod._store["path"] = None
    app = create_app(data_path=json_path, db_path=db_path)
    app.config["TESTING"] = True
    ds = load_dataset(json_path)
    engine_map = ts.default_assignments(Simulation(ds).run_all())
    yield SimpleNamespace(app=app, db_path=db_path, ds=ds, engine_map=engine_map)
    appmod._store["dataset"] = None
    appmod._store["path"] = None


def _login(client, username, password):
    r = client.post("/login", data={"username": username, "password": password})
    assert r.status_code in (200, 302)


def _client_for(env, tech_id):
    c = env.app.test_client()
    _login(c, *USERS[tech_id])
    return c


def _admin(env):
    c = env.app.test_client()
    _login(c, "admin", "admin123")
    return c


def _state(env, tid):
    conn = sqlite3.connect(env.db_path)
    try:
        return ts.get_state(conn, tid)
    finally:
        conn.close()


def _pick(env):
    """Tiket biasa (bukan permintaan bantuan) yang ditugaskan mesin ke T01-T03."""
    tmap = {t.id: t for t in env.ds.tickets}
    for tid, tech in env.engine_map.items():
        if tech in USERS and not getattr(tmap[tid], "requested_by", None):
            return tid, tech
    pytest.skip("tidak ada tiket yang cocok untuk tes")


def _others(tech):
    return [t for t in USERS if t != tech]


# --------------------------- rute: status teknisi ---------------------------

def test_teknisi_start_lalu_resolve(env):
    tid, tech = _pick(env)
    c = _client_for(env, tech)
    r = c.post(f"/tickets/{tid}/status", data={"status": ts.IN_PROGRESS})
    assert r.status_code == 302
    st = _state(env, tid)
    assert st["status"] == ts.IN_PROGRESS
    assert st["assigned_to"] == tech and st["started_at"]
    c.post(f"/tickets/{tid}/status", data={"status": ts.RESOLVED})
    st = _state(env, tid)
    assert st["status"] == ts.RESOLVED and st["resolved_at"]


def test_tidak_boleh_lompat_dan_mundur(env):
    tid, tech = _pick(env)
    c = _client_for(env, tech)
    url = f"/tickets/{tid}/status"
    c.post(url, data={"status": ts.RESOLVED})  # lompat
    assert _state(env, tid) is None
    c.post(url, data={"status": ts.OPEN})  # status tidak valid
    assert _state(env, tid) is None
    c.post(url, data={"status": ts.IN_PROGRESS})
    c.post(url, data={"status": ts.RESOLVED})
    c.post(url, data={"status": ts.IN_PROGRESS})  # mundur
    assert _state(env, tid)["status"] == ts.RESOLVED


def test_teknisi_lain_ditolak(env):
    tid, tech = _pick(env)
    c = _client_for(env, _others(tech)[0])
    c.post(f"/tickets/{tid}/status", data={"status": ts.IN_PROGRESS})
    assert _state(env, tid) is None


def test_role_lain_ditolak(env):
    tid, _ = _pick(env)
    url = f"/tickets/{tid}/status"
    rep = env.app.test_client()
    _login(rep, "pelapor", "pelapor123")
    assert rep.post(url, data={"status": ts.IN_PROGRESS}).status_code == 403
    assert _admin(env).post(url, data={"status": ts.IN_PROGRESS}).status_code == 403
    anon = env.app.test_client().post(url, data={"status": ts.IN_PROGRESS})
    assert anon.status_code == 302 and "/login" in anon.headers["Location"]
    assert _state(env, tid) is None


def test_tiket_tidak_ada_404(env):
    c = _client_for(env, "T01")
    r = c.post("/tickets/TIDAK-ADA/status", data={"status": ts.IN_PROGRESS})
    assert r.status_code == 404


# --------------------------- rute: penugasan ulang --------------------------

def test_admin_reassign_dan_original_tidak_tertimpa(env):
    tid, tech = _pick(env)
    b, c3 = _others(tech)
    adm = _admin(env)
    r = adm.post(f"/tickets/{tid}/reassign",
                 data={"technician": b, "reason": "Teknisi awal sedang cuti"})
    assert r.status_code == 302
    st = _state(env, tid)
    assert st["assigned_to"] == b and st["assignment_type"] == ts.MANUAL
    assert st["original_technician"] == tech and st["reassigned_by"] == "admin"
    assert "cuti" in st["reassignment_reason"]
    adm.post(f"/tickets/{tid}/reassign",
             data={"technician": c3, "reason": "Dipindah lagi"})
    st = _state(env, tid)
    assert st["assigned_to"] == c3 and st["original_technician"] == tech


def test_teknisi_baru_bisa_mulai_teknisi_lama_tidak(env):
    tid, tech = _pick(env)
    b = _others(tech)[0]
    _admin(env).post(f"/tickets/{tid}/reassign",
                     data={"technician": b, "reason": "Pemerataan beban"})
    _client_for(env, tech).post(f"/tickets/{tid}/status",
                                data={"status": ts.IN_PROGRESS})
    assert _state(env, tid)["status"] == ts.OPEN
    _client_for(env, b).post(f"/tickets/{tid}/status",
                             data={"status": ts.IN_PROGRESS})
    assert _state(env, tid)["status"] == ts.IN_PROGRESS


def test_reassign_ditolak_setelah_in_progress(env):
    tid, tech = _pick(env)
    _client_for(env, tech).post(f"/tickets/{tid}/status",
                                data={"status": ts.IN_PROGRESS})
    _admin(env).post(f"/tickets/{tid}/reassign",
                     data={"technician": _others(tech)[0], "reason": "Coba pindah"})
    st = _state(env, tid)
    assert st["assigned_to"] == tech and st["assignment_type"] == ts.AUTOMATIC


# --------------------------- baris untuk template ---------------------------

def test_baris_tiket_mengikuti_status_terbaru(env):
    tid, tech = _pick(env)
    _client_for(env, tech).post(f"/tickets/{tid}/status",
                                data={"status": ts.IN_PROGRESS})
    with env.app.app_context():
        conn = get_db_connection()
        try:
            rows = ts.build_ticket_rows(conn, env.ds.tickets, env.engine_map)
        finally:
            conn.close()
    row = next(r for r in rows if r["id"] == tid)
    assert row["status"] == ts.IN_PROGRESS and row["assigned_to"] == tech
    assert all(r["status"] == ts.OPEN for r in rows if r["id"] != tid)


@pytest.mark.parametrize("user,pw", [
    ("admin", "admin123"), ("t01", "tech01"), ("pelapor", "pelapor123"),
])
def test_dashboard_tetap_terbuka(env, user, pw):
    c = env.app.test_client()
    _login(c, user, pw)
    assert c.get("/dashboard").status_code == 200


# --------------------------- aturan (tanpa Flask) ---------------------------

@pytest.fixture
def mem():
    conn = sqlite3.connect(":memory:")
    conn.execute(ts.SCHEMA)
    yield conn
    conn.close()


EMAP = {"T-1": "T01", "TK-1": "T01"}
VALID = {"T01", "T02", "T03", "T04"}


def _t(tid="T-1", requested_by=None):
    return SimpleNamespace(id=tid, requested_by=requested_by)


def test_reassign_alasan_wajib(mem):
    with pytest.raises(ts.StateError, match="Alasan wajib"):
        ts.reassign(mem, _t(), "T02", "admin", "  ", EMAP, VALID)
    assert ts.get_state(mem, "T-1") is None


def test_reassign_teknisi_tidak_dikenal(mem):
    with pytest.raises(ts.StateError, match="tidak dikenal"):
        ts.reassign(mem, _t(), "T99", "admin", "alasan sah", EMAP, VALID)


def test_reassign_sama_dengan_saat_ini(mem):
    with pytest.raises(ts.StateError, match="sama"):
        ts.reassign(mem, _t(), "T01", "admin", "alasan sah", EMAP, VALID)


def test_reassign_pemohon_ditolak(mem):
    t = _t("TK-1", requested_by="T02")
    with pytest.raises(ts.StateError, match="pemohon"):
        ts.reassign(mem, t, "T02", "admin", "alasan sah", EMAP, VALID)
    assert ts.get_state(mem, "TK-1") is None


def test_reassign_hanya_open(mem):
    ts.change_status(mem, "T-1", ts.IN_PROGRESS, "T01", EMAP)
    with pytest.raises(ts.StateError, match="berstatus Open"):
        ts.reassign(mem, _t(), "T02", "admin", "alasan sah", EMAP, VALID)


def test_status_bukan_penerima(mem):
    with pytest.raises(ts.StateError, match="tidak ditugaskan"):
        ts.change_status(mem, "T-1", ts.IN_PROGRESS, "T02", EMAP)


def test_status_lompat_ditolak(mem):
    with pytest.raises(ts.StateError, match="tidak diizinkan"):
        ts.change_status(mem, "T-1", ts.RESOLVED, "T01", EMAP)
