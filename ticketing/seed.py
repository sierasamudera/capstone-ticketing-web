"""Pemuatan dataset (SQLite database) dan import dari Excel.

Catatan_Revisi #8: ID tiket digenerate otomatis sistem dengan counter terpisah
per prefix (T- untuk User Report, TK- untuk Technician Request), bukan diketik
pengguna -- menghindari bentrok saat input bersamaan.

Catatan: Dataset kini disimpan di SQLite database (data/ticketing.db) agar
perubahan (tambah tiket/teknisi) persisten tanpa perlu layanan luar.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .models import (
    PRIORITY_WEIGHTS,
    Parameters,
    Priority,
    TechStatus,
    Technician,
    Ticket,
    TicketType,
)

DEFAULT_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tickets.json"
)


@dataclass
class Dataset:
    """Satu dataset lengkap: parameter + teknisi + tiket."""

    parameters: Parameters
    technicians: list = field(default_factory=list)
    tickets: list = field(default_factory=list)

    @property
    def tech_ids(self) -> list:
        return [t.id for t in self.technicians]


_DT_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M")


def _parse_dt(s) -> datetime:
    if isinstance(s, datetime):
        return s
    s = str(s).strip()
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"format waktu tidak valid: {s!r} (pakai 'YYYY-MM-DD HH:MM')")


def _load_parameters_from_json(path: str) -> Parameters:
    """Baca parameter konfigurasi dari file JSON (tetap di JSON)."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return Parameters(
        priority_weights={Priority(k): int(v) for k, v in raw["parameters"]["priority_weights"].items()},
        shift_start=_parse_dt(raw["parameters"]["shift_start"]),
        busy_penalty=int(raw["parameters"].get("busy_penalty", 1_000_000)),
        distribution_rule=raw["parameters"].get("distribution_rule", "Lowest Active Workload"),
        tie_breaker=raw["parameters"].get("tie_breaker", "Technician ID"),
        fallback_rule=raw["parameters"].get("fallback_rule", "Earliest Estimated Finish"),
    )


def load_dataset(path: Optional[str] = None) -> Dataset:
    """Muat dataset dari SQLite database (data/ticketing.db).

    Jika database masih kosong, fallback ke file JSON (data/tickets.json)
    untuk migrasi satu kali.
    """
    from .db import get_db_connection, init_db

    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM technicians")
    tech_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets")
    ticket_count = cursor.fetchone()[0]

    if tech_count == 0 and ticket_count == 0:
        # Fallback: migrasi dari JSON (sekali saja)
        json_path = path or DEFAULT_DATA_PATH
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        params = Parameters(
            priority_weights={Priority(k): int(v) for k, v in raw["parameters"]["priority_weights"].items()},
            shift_start=_parse_dt(raw["parameters"]["shift_start"]),
            busy_penalty=int(raw["parameters"].get("busy_penalty", 1_000_000)),
            distribution_rule=raw["parameters"].get("distribution_rule", "Lowest Active Workload"),
            tie_breaker=raw["parameters"].get("tie_breaker", "Technician ID"),
            fallback_rule=raw["parameters"].get("fallback_rule", "Earliest Estimated Finish"),
        )
        technicians = [
            Technician(
                id=str(t["id"]),
                name=str(t["name"]),
                initial_status=TechStatus(str(t.get("initial_status", "Available"))),
            )
            for t in raw["technicians"]
        ]
        tickets = [_ticket_from_dict(t) for t in raw["tickets"]]
        conn.close()
        return Dataset(parameters=params, technicians=technicians, tickets=tickets)

    params = _load_parameters_from_json(path or DEFAULT_DATA_PATH)

    cursor.execute("SELECT id, name, initial_status FROM technicians")
    technicians = [
        Technician(id=row["id"], name=row["name"], initial_status=TechStatus(row["initial_status"]))
        for row in cursor.fetchall()
    ]

    cursor.execute("SELECT * FROM tickets")
    tickets = [
        Ticket(
            id=row["id"],
            ticket_type=TicketType(row["ticket_type"]),
            created_by=row["created_by"],
            timestamp=_parse_dt(row["timestamp"]),
            category=row["category"],
            detail=row["detail"],
            priority=Priority(row["priority"]),
            duration=int(row["duration"]),
            related_id=row["related_id"],
            requested_by=row["requested_by"],
        )
        for row in cursor.fetchall()
    ]

    conn.close()
    return Dataset(parameters=params, technicians=technicians, tickets=tickets)


def _ticket_from_dict(d: dict) -> Ticket:
    return Ticket(
        id=str(d["id"]),
        ticket_type=TicketType(str(d["ticket_type"])),
        created_by=str(d["created_by"]),
        timestamp=_parse_dt(d["timestamp"]),
        category=str(d["category"]),
        detail=str(d["detail"]),
        priority=Priority(str(d["priority"])),
        duration=int(d["duration"]),
        related_id=d.get("related_id"),
        requested_by=d.get("requested_by"),
    )


def save_dataset(dataset: Dataset, path: Optional[str] = None) -> str:
    """Simpan dataset ke SQLite database (data/ticketing.db)."""
    from .db import get_db_connection, init_db

    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM technicians")
    for t in dataset.technicians:
        cursor.execute(
            "INSERT INTO technicians VALUES (?, ?, ?)",
            (t.id, t.name, t.initial_status.value),
        )

    cursor.execute("DELETE FROM tickets")
    for t in dataset.tickets:
        cursor.execute(
            "INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                t.id,
                t.ticket_type.value,
                t.created_by,
                t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                t.category,
                t.detail,
                t.priority.value,
                int(t.duration),
                t.related_id,
                t.requested_by,
            ),
        )

    conn.commit()
    conn.close()
    return "data/ticketing.db"


# ---------------------------------------------------------------------------
# Generator ID otomatis (counter terpisah per prefix)
# ---------------------------------------------------------------------------


class TicketIdGenerator:
    """Counter ID terpisah per prefix: T-001, T-002, ... dan TK-001, TK-002, ...

    Mencegah bentrok nomor saat dua pengguna input bersamaan.
    """

    def __init__(self, existing_ids: Optional[list] = None):
        self.counters: dict = {"T-": 0, "TK-": 0}
        if existing_ids:
            for tid in existing_ids:
                prefix, num = _split_id(tid)
                if prefix in self.counters:
                    self.counters[prefix] = max(self.counters[prefix], num)

    def next(self, ticket_type) -> str:
        """Terima TicketType atau nilai string-nya ('User Report'/'Technician Request')."""
        if isinstance(ticket_type, TicketType):
            prefix = ticket_type.prefix
        else:
            prefix = TicketType(str(ticket_type)).prefix
        self.counters[prefix] += 1
        return f"{prefix}{self.counters[prefix]:03d}"


def _split_id(ticket_id: str):
    """Pisah 'TK-002' -> ('TK-', 2); 'T-005' -> ('T-', 5)."""
    tid = str(ticket_id).strip()
    if tid.startswith("TK-"):
        return "TK-", int(tid[3:])
    if tid.startswith("T-"):
        return "T-", int(tid[2:])
    return "", 0


def add_ticket(
    dataset: Dataset,
    ticket_type: str,
    created_by: str,
    timestamp,
    category: str,
    detail: str,
    priority: str,
    duration: int,
    related_id: Optional[str] = None,
    requested_by: Optional[str] = None,
) -> Ticket:
    """Tambah tiket baru ke dataset dengan ID otomatis.

    Untuk Technician Request, created_by diisi 'Admin' dan related_id +
    requested_by wajib (tiket bantuan harus terhubung ke kasus lain).
    """
    ttype = TicketType(ticket_type)
    gen = TicketIdGenerator([t.id for t in dataset.tickets])
    ticket = Ticket(
        id=gen.next(ttype),
        ticket_type=ttype,
        created_by=created_by,
        timestamp=_parse_dt(timestamp) if not isinstance(timestamp, datetime) else timestamp,
        category=category,
        detail=detail,
        priority=Priority(priority),
        duration=int(duration),
        related_id=related_id,
        requested_by=requested_by,
    )
    dataset.tickets.append(ticket)
    return ticket
