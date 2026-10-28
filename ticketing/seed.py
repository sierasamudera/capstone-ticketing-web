"""Pemuatan dataset (SQLite database) dan import dari Excel.

Catatan_Revisi #8: ID tiket digenerate otomatis sistem dengan counter terpisah
per prefix (T- untuk User Report, TK- untuk Technician Request), bukan diketik
pengguna -- menghindari bentrok saat input bersamaan.

Catatan: Dataset kini disimpan di SQLite database (data/ticketing.db) agar
perubahan (tambah tiket/teknisi) persisten tanpa perlu layanan luar.

Catatan: Fungsi load_dataset kini support jalankan dari pytest (path argumen)
dan dari CLI. Struktur data tetap kompatibel dengan model lama.
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
    raise ValueError(f"format waktu tidak valid: {s!r} (pakai 'YYYY-MM-DD HH:MM')" )


def _default_parameters() -> Parameters:
    """Return default Parameters (digunakan saat dataset masih kosong)."""
    return Parameters(
        priority_weights=dict(PRIORITY_WEIGHTS),
        shift_start=datetime(2026, 9, 23, 8, 0, 0),
    )


def _load_parameters(raw: dict) -> Parameters:
    """Ekstraksi parameters dari dict mentah (baik dari JSON maupun dict temp test)."""
    return Parameters(
        priority_weights={Priority(k): int(v) for k, v in raw.get("parameters", {}).get("priority_weights", {}).items()},
        shift_start=_parse_dt(raw.get("parameters", {}).get("shift_start", "2026-09-23 08:00:00")),
        busy_penalty=int(raw.get("parameters", {}).get("busy_penalty", 1_000_000)),
        distribution_rule=raw.get("parameters", {}).get("distribution_rule", "Lowest Active Workload"),
        tie_breaker=raw.get("parameters", {}).get("tie_breaker", "Technician ID"),
        fallback_rule=raw.get("parameters", {}).get("fallback_rule", "Earliest Estimated Finish"),
    )


def load_dataset(path: Optional[str] = None) -> Dataset:
    """Muat dataset.

    Args:
        path: Jika diberikan, coba baca dari file JSON sementara (seperti saat test pytest).
              Jika file tersebut tidak ada, turun ke baca dari database SQLite
              atau file JSON asli (data/tickets.json).
        None: Baca langsung dari database SQLite atau file JSON asli.

    Returns:
        Dataset berisi parameters, technicians, dan tickets.
    """
    import sqlite3

    # Jika ada path argumen (seperti test case bikin file sementara),
    # coba baca dari file JSON tersebut dulu.
    if path is not None:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            params = _load_parameters(raw)
            technicians = [
                Technician(id=str(t["id"]), name=str(t["name"]), initial_status=TechStatus(str(t.get("initial_status", "Available"))))
                for t in raw.get("technicians", [])
            ]
            tickets = [_ticket_from_dict(t) for t in raw.get("tickets", [])]
            return Dataset(parameters=params, technicians=technicians, tickets=tickets)
        # Jika path tadi tidak ada (file sementara test sudah expired/hapus),
        # turun ke bawah baca dari database/file asli.

    # Jika tidak ada path argumen, atau path tadi gaada:
    # Coba baca dari database SQLite dulu.
    conn = sqlite3.connect("data/ticketing.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM technicians")
    tech_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tickets")
    ticket_count = cursor.fetchone()[0]

    if tech_count > 0 or ticket_count > 0:
        # Database sudah punya data, baca dari SQLite
        # Ambil config default parameters
        params = _load_parameters({"parameters": {
            "priority_weights": {Priority.LOW: 1, Priority.MEDIUM: 2, Priority.HIGH: 3},
            "shift_start": "2026-09-23 08:00:00",
            "busy_penalty": 1_000_000,
            "distribution_rule": "Lowest Active Workload",
            "tie_breaker": "Technician ID",
            "fallback_rule": "Earliest Estimated Finish",
        }})

        cursor.execute("SELECT id, name, initial_status FROM technicians")
        technicians = [
            Technician(id=row[0], name=row[1], initial_status=TechStatus(row[2]))
            for row in cursor.fetchall()
        ]

        cursor.execute("SELECT * FROM tickets")
        tickets = []
        for row in cursor.fetchall():
            tickets.append(Ticket(
                id=str(row[0]),
                ticket_type=TicketType(row[1]),
                created_by=str(row[2]),
                timestamp=_parse_dt(row[3]),
                category=str(row[4]),
                detail=str(row[5]),
                priority=Priority(str(row[6])),
                duration=int(row[7]),
                related_id=row[8],
                requested_by=row[9],
            ))
        conn.close()
        return Dataset(parameters=params, technicians=technicians, tickets=tickets)

    # Jika database masih kosong, baca dari file JSON asli (data/tickets.json)
    json_path = "data/tickets.json"
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        params = _load_parameters(raw)
        technicians = [
            Technician(id=str(t["id"]), name=str(t["name"]), initial_status=TechStatus(str(t.get("initial_status", "Available"))))
            for t in raw.get("technicians", [])
        ]
        tickets = [_ticket_from_dict(t) for t in raw.get("tickets", [])]
        return Dataset(parameters=params, technicians=technicians, tickets=tickets)

    # Jika tidak ada data sama sekali, kembalikan Dataset kosong dengan default
    return Dataset(parameters=_default_parameters(), technicians=[], tickets=[])