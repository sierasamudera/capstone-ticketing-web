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


def _parameters_from_dict(raw: dict) -> Parameters:
    """Baca parameter dari dict JSON (data/tickets.json).

    ``raw`` bisa berupa dict penuh (dengan kunci "parameters") atau sudah
    berupa isi "parameters" itu sendiri.
    """
    p = raw.get("parameters", raw)
    return Parameters(
        priority_weights={Priority(k): int(v) for k, v in p["priority_weights"].items()},
        shift_start=_parse_dt(p["shift_start"]),
        busy_penalty=int(p.get("busy_penalty", 1_000_000)),
        distribution_rule=p.get("distribution_rule", "Lowest Active Workload"),
        tie_breaker=p.get("tie_breaker", "Technician ID"),
        fallback_rule=p.get("fallback_rule", "Earliest Estimated Finish"),
    )


def _parameters_from_db(conn) -> Parameters:
    """Baca parameter konfigurasi dari tabel parameters di SQLite."""
    row = conn.execute(
        "SELECT priority_weights, shift_start, busy_penalty, distribution_rule, tie_breaker, fallback_rule FROM parameters WHERE id = 1"
    ).fetchone()
    if not row:
        return _parameters_from_dict(_default_parameters_dict())
    return Parameters(
        priority_weights={Priority(k): int(v) for k, v in json.loads(row["priority_weights"]).items()},
        shift_start=_parse_dt(row["shift_start"]),
        busy_penalty=int(row["busy_penalty"]),
        distribution_rule=row["distribution_rule"],
        tie_breaker=row["tie_breaker"],
        fallback_rule=row["fallback_rule"],
    )


def _default_parameters_dict() -> dict:
    return {
        "parameters": {
            "priority_weights": {"Low": 1, "Medium": 2, "High": 3},
            "shift_start": "2026-09-23 08:00:00",
            "busy_penalty": 1_000_000,
            "distribution_rule": "Lowest Active Workload",
            "tie_breaker": "Technician ID",
            "fallback_rule": "Earliest Estimated Finish",
        }
    }


def _load_parameters_from_json(path: str) -> Parameters:
    """Baca parameter konfigurasi dari file JSON (tetap di JSON)."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return _parameters_from_dict(raw)


def load_dataset(path: Optional[str] = None) -> Dataset:
    """Muat dataset dari file JSON (default data/tickets.json).

    Untuk parameter dan autentikasi, aplikasi Flask tetap membaca dari
    SQLite DB (lihat ticketing.web.app).
    """
    json_path = path or DEFAULT_DATA_PATH
    return _load_dataset_from_json(json_path)


def _load_dataset_from_json(path: str) -> Dataset:
    """Baca dataset lengkap dari file JSON (migrasi / uji isolasi)."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    params = _parameters_from_dict(raw["parameters"])
    technicians = [
        Technician(
            id=str(t["id"]),
            name=str(t["name"]),
            initial_status=TechStatus(str(t.get("initial_status", "Available"))),
        )
        for t in raw["technicians"]
    ]
    tickets = [_ticket_from_dict(t) for t in raw["tickets"]]
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
    """Simpan dataset ke SQLite database (data/ticketing.db) atau file JSON.

    Jika ``path`` diberikan dan berekstensi .json, tulis ke file JSON (dipakai
    oleh uji untuk isolasi data per test). Sebaliknya tulis ke SQLite DB.
    """
    if path and path.lower().endswith(".json"):
        return _save_dataset_to_json(dataset, path)

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


def _save_dataset_to_json(dataset: Dataset, path: str) -> str:
    """Simpan dataset ke file JSON (untuk uji isolasi data per test)."""
    import json as _json

    raw = {
        "parameters": {
            "priority_weights": {k.value: v for k, v in dataset.parameters.priority_weights.items()},
            "shift_start": dataset.parameters.shift_start.strftime("%Y-%m-%d %H:%M:%S"),
            "busy_penalty": dataset.parameters.busy_penalty,
            "distribution_rule": dataset.parameters.distribution_rule,
            "tie_breaker": dataset.parameters.tie_breaker,
            "fallback_rule": dataset.parameters.fallback_rule,
        },
        "technicians": [
            {
                "id": t.id,
                "name": t.name,
                "initial_status": t.initial_status.value,
            }
            for t in dataset.technicians
        ],
        "tickets": [
            {
                "id": t.id,
                "ticket_type": t.ticket_type.value,
                "created_by": t.created_by,
                "timestamp": t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "category": t.category,
                "detail": t.detail,
                "priority": t.priority.value,
                "duration": t.duration,
                "related_id": t.related_id,
                "requested_by": t.requested_by,
            }
            for t in dataset.tickets
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(raw, f, ensure_ascii=False, indent=2)
    return path


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
