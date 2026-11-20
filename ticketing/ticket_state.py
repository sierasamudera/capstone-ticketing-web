"""Status pengerjaan dan penugasan ulang tiket.

Lapisan operasional di atas mesin simulasi. Mesin S1-S4 TIDAK diubah:
penugasan awal tiap tiket tetap dari mesin (skenario DEFAULT_ASSIGN_SCENARIO).
Tabel ticket_state hanya menyimpan status pengerjaan dan penugasan ulang manual.
Tiket tanpa baris di tabel ini dianggap Open dan ditugaskan sesuai mesin.
"""

from __future__ import annotations

import sqlite3
import psycopg

from datetime import datetime

_INTEGRITY_ERRORS = (
    sqlite3.IntegrityError,
    psycopg.IntegrityError,
)

OPEN = "Open"
IN_PROGRESS = "In Progress"
RESOLVED = "Resolved"
AUTOMATIC = "Automatic"
MANUAL = "Manual Override"

# Skenario yang menjadi penugasan awal tiket di aplikasi web.
# Sesuaikan dengan kunci di ticketing.scenarios.SCENARIOS.
DEFAULT_ASSIGN_SCENARIO = "S2"

MIN_REASON_LEN = 5
_ALLOWED = {(OPEN, IN_PROGRESS), (IN_PROGRESS, RESOLVED)}

SCHEMA = """
CREATE TABLE IF NOT EXISTS ticket_state (
    ticket_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    assigned_to TEXT,
    assignment_type TEXT NOT NULL,
    original_technician TEXT,
    reassigned_by TEXT,
    reassigned_at TEXT,
    reassignment_reason TEXT,
    started_at TEXT,
    resolved_at TEXT,
    updated_at TEXT NOT NULL
)
"""


class StateError(ValueError):
    """Pelanggaran aturan bisnis; pesannya aman ditampilkan ke pengguna."""


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fetch_dicts(conn, sql, params=()):
    cur = conn.execute(sql, params)
    rows = cur.fetchall()

    if not rows:
        return []

    # PostgreSQL dict_row sudah menghasilkan dictionary.
    if isinstance(rows[0], dict):
        return [dict(row) for row in rows]

    # SQLite menghasilkan tuple.
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in rows]

def get_state(conn, ticket_id):
    rows = _fetch_dicts(
        conn, "SELECT * FROM ticket_state WHERE ticket_id = ?", (ticket_id,)
    )
    return rows[0] if rows else None


def get_all_states(conn):
    return {r["ticket_id"]: r for r in _fetch_dicts(conn, "SELECT * FROM ticket_state")}


def status_of(state):
    return state["status"] if state else OPEN


def assignee_of(state, ticket_id, engine_map):
    if state and state.get("assigned_to"):
        return state["assigned_to"]
    return engine_map.get(ticket_id)


def default_assignments(result, scenario=None):
    """Peta ticket_id -> teknisi dari skenario penugasan awal."""
    key = scenario or DEFAULT_ASSIGN_SCENARIO
    if key not in result.indicators:
        raise KeyError(
            f"Skenario '{key}' tidak ada. Pilihan: {list(result.indicators)}"
        )
    return {a.ticket.id: a.tech_id for a in result.indicators[key].assignments}


def change_status(conn, ticket_id, new_status, actor_tech_id, engine_map, now=None):
    """Teknisi mengubah status: Open -> In Progress -> Resolved."""
    now = now or now_text()
    if new_status not in (IN_PROGRESS, RESOLVED):
        raise StateError("Status tujuan tidak valid.")
    state = get_state(conn, ticket_id)
    current = status_of(state)
    if (current, new_status) not in _ALLOWED:
        raise StateError(
            f"Perubahan status dari {current} ke {new_status} tidak diizinkan. "
            "Urutannya Open, In Progress, Resolved."
        )
    if not actor_tech_id or assignee_of(state, ticket_id, engine_map) != actor_tech_id:
        raise StateError("Tiket ini tidak ditugaskan kepada Anda.")
    started = now if new_status == IN_PROGRESS else None
    resolved = now if new_status == RESOLVED else None
    if state is None:
        try:
            conn.execute(
                "INSERT INTO ticket_state (ticket_id, status, assigned_to, "
                "assignment_type, started_at, resolved_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ticket_id, new_status, actor_tech_id, AUTOMATIC, started, resolved, now),
            )
        except _INTEGRITY_ERRORS:
            conn.rollback()
            raise StateError("Status tiket sudah berubah. Muat ulang halaman.")
    else:
        cur = conn.execute(
            "UPDATE ticket_state SET status = ?, started_at = COALESCE(started_at, ?), "
            "resolved_at = COALESCE(resolved_at, ?), updated_at = ? "
            "WHERE ticket_id = ? AND status = ?",
            (new_status, started, resolved, now, ticket_id, current),
        )
        if cur.rowcount != 1:
            conn.rollback()
            raise StateError("Status tiket sudah berubah. Muat ulang halaman.")
    conn.commit()


def reassign(conn, ticket, new_tech_id, admin_username, reason,
             engine_map, valid_tech_ids, now=None):
    """Admin memindahkan tiket Open ke teknisi lain (Manual Override)."""
    now = now or now_text()
    ticket_id = ticket.id
    reason = (reason or "").strip()
    if len(reason) < MIN_REASON_LEN:
        raise StateError(f"Alasan wajib diisi (minimal {MIN_REASON_LEN} karakter).")
    if new_tech_id not in valid_tech_ids:
        raise StateError("Teknisi tujuan tidak dikenal.")
    state = get_state(conn, ticket_id)
    if status_of(state) != OPEN:
        raise StateError("Penugasan ulang hanya untuk tiket berstatus Open.")
    if getattr(ticket, "requested_by", None) == new_tech_id:
        raise StateError(
            "Teknisi pemohon tidak boleh menjadi penerima tiket permintaan "
            "bantuannya sendiri."
        )
    current = assignee_of(state, ticket_id, engine_map)
    if new_tech_id == current:
        raise StateError("Teknisi tujuan sama dengan teknisi saat ini.")
    if state is None:
        try:
            conn.execute(
                "INSERT INTO ticket_state (ticket_id, status, assigned_to, "
                "assignment_type, original_technician, reassigned_by, reassigned_at, "
                "reassignment_reason, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ticket_id, OPEN, new_tech_id, MANUAL, current,
                 admin_username, now, reason, now),
            )
        except _INTEGRITY_ERRORS:
            conn.rollback()
            raise StateError("Status tiket sudah berubah. Muat ulang halaman.")
    else:
        cur = conn.execute(
            "UPDATE ticket_state SET assigned_to = ?, assignment_type = ?, "
            "original_technician = COALESCE(original_technician, ?), "
            "reassigned_by = ?, reassigned_at = ?, reassignment_reason = ?, "
            "updated_at = ? WHERE ticket_id = ? AND status = ?",
            (new_tech_id, MANUAL, current, admin_username, now, reason, now,
             ticket_id, OPEN),
        )
        if cur.rowcount != 1:
            conn.rollback()
            raise StateError("Status tiket sudah berubah. Muat ulang halaman.")
    conn.commit()


def _val(x):
    return getattr(x, "value", x)


def _fmt_ts(ts):
    return ts.strftime("%Y-%m-%d %H:%M") if hasattr(ts, "strftime") else str(ts)


def build_ticket_rows(conn, tickets, engine_map):
    """Baris siap tampil untuk template (status dan teknisi TERKINI dari DB)."""
    states = get_all_states(conn)
    ordered = sorted(
        tickets, key=lambda x: (str(getattr(x, "timestamp", "")), x.id)
    )
    rows = []
    for t in ordered:
        st = states.get(t.id)
        rows.append({
            "id": t.id,
            "ticket_type": _val(getattr(t, "ticket_type", "")),
            "created_by": getattr(t, "created_by", ""),
            "timestamp": _fmt_ts(getattr(t, "timestamp", "")),
            "category": _val(getattr(t, "category", "")),
            "detail": getattr(t, "detail", ""),
            "priority": _val(getattr(t, "priority", "")),
            "duration": getattr(t, "duration", ""),
            "related_id": getattr(t, "related_id", None),
            "requested_by": getattr(t, "requested_by", None),
            "status": status_of(st),
            "assigned_to": assignee_of(st, t.id, engine_map),
            "assignment_type": st["assignment_type"] if st else AUTOMATIC,
            "original_technician": st["original_technician"] if st else None,
            "reassigned_by": st["reassigned_by"] if st else None,
            "reassigned_at": st["reassigned_at"] if st else None,
            "reassignment_reason": st["reassignment_reason"] if st else None,
            "updated_at": st["updated_at"] if st else None,
        })
    return rows
