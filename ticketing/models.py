"""Model data inti sistem ticketing.

Struktur ini mereplikasi sheet Excel:
  - Ticket        <- sheet Input_Tiket (kolom A-K)
  - Technician    <- sheet Teknisi (kolom A-C)
  - Parameters    <- sheet Parameter (kolom A-C)
  - Assignment    <- sheet Sim_S1/S2/S3 (kolom A-AH)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

# ---------------------------------------------------------------------------
# Enumerasi (menggantikan dropdown / nilai validasi di Excel)
# ---------------------------------------------------------------------------

TICKET_TYPES = ("User Report", "Technician Request")
PRIORITIES = ("Low", "Medium", "High")

CATEGORIES = (
    "Network",
    "Hardware",
    "Software",
    "Account",
    "Multimedia",
    "Printer",
    "Academic System",
    "CCTV/Infrastructure",
)


class TicketType(str, Enum):
    """Ticket Type di sheet Input_Tiket kolom B."""

    USER_REPORT = "User Report"
    TECHNICIAN_REQUEST = "Technician Request"

    @property
    def prefix(self) -> str:
        """Prefix ID: T- untuk User Report, TK- untuk Technician Request."""
        return "TK-" if self is TicketType.TECHNICIAN_REQUEST else "T-"


class Priority(str, Enum):
    """Priority di sheet Input_Tiket kolom I; bobotnya dari sheet Parameter."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class TechStatus(str, Enum):
    """Status teknisi saat sebuah tiket tiba (kolom J di sheet Sim_*)."""

    AVAILABLE = "Available"
    BUSY = "Busy"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@dataclass
class Ticket:
    """Satu baris di sheet Input_Tiket."""

    id: str
    ticket_type: TicketType
    created_by: str
    timestamp: datetime
    category: str
    detail: str
    priority: Priority
    duration: int  # Service Duration (min), kolom K
    related_id: Optional[str] = None  # Related Ticket ID, kolom D
    requested_by: Optional[str] = None  # Requested By (Technician), kolom E
    weight: int = field(init=False)  # Priority Weight, kolom J (VLOOKUP ke Parameter)

    def __post_init__(self) -> None:
        # Priority Weight = VLOOKUP(priority; Parameter!A2:B4)
        self.weight = PRIORITY_WEIGHTS[self.priority]

    @property
    def is_root_case(self) -> bool:
        """Kasus baru (root) = tidak punya Related Ticket ID.

        Dipakai indikator "Jumlah kasus (unik)" di sheet Ringkasan supaya
        tiket bantuan (TK-) tidak dihitung dobel.
        """
        return self.related_id is None

    @property
    def weighted_load(self) -> int:
        """Kolom Weighted Load (pt-min) = durasi x bobot prioritas."""
        return self.duration * self.weight


@dataclass
class Technician:
    """Satu baris di sheet Teknisi."""

    id: str  # T01..T04, dipakai sebagai tie-breaker
    name: str
    initial_status: TechStatus = TechStatus.AVAILABLE


@dataclass(frozen=True)
class Parameters:
    """Sheet Parameter.

    busy_penalty dipakai supaya teknisi Busy selalu kalah dari teknisi
    Available pada perhitungan skor (Parameter!B9 = 1.000.000).
    """

    priority_weights: dict  # {Priority: bobot}
    shift_start: datetime
    busy_penalty: int = 1_000_000
    distribution_rule: str = "Lowest Active Workload"
    tie_breaker: str = "Technician ID"
    fallback_rule: str = "Earliest Estimated Finish"

    def weight_of(self, priority: Priority) -> int:
        return self.priority_weights[priority]


@dataclass
class Assignment:
    """Satu baris hasil di sheet Sim_S1/S2/S3 (kolom A-AH)."""

    ticket: Ticket
    tech_id: str
    tech_name: str
    tech_index: int  # posisi teknisi di daftar (untuk tie-breaker)
    status: TechStatus  # kolom J
    arrival: datetime  # kolom C (Timestamp)
    start: datetime  # kolom K (Start Time)
    finish: datetime  # kolom L (Estimated Finish)
    waiting: int  # kolom M (menit)
    rule_note: str  # kolom N (Assignment Rule)
    weighted_load: int  # kolom P (Weighted Load pt-min tiket ini)
    # kolom AE-AH: skor lengkap per teknisi (transparansi keputusan)
    scores: dict = field(default_factory=dict)
    # kolom S-V: waktu bebas tiap teknisi saat tiket ini tiba
    free_at: dict = field(default_factory=dict)

    @property
    def duration(self) -> int:
        return self.ticket.duration


# Bobot default sesuai sheet Parameter (Low=1, Medium=2, High=3).
# Catatan_Revisi #4: nilai ini masih asumsi dan perlu validasi dosen.
PRIORITY_WEIGHTS: dict = {
    Priority.LOW: 1,
    Priority.MEDIUM: 2,
    Priority.HIGH: 3,
}


def default_parameters(shift_start: datetime) -> Parameters:
    return Parameters(
        priority_weights=dict(PRIORITY_WEIGHTS),
        shift_start=shift_start,
    )
