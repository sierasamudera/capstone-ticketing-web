"""Mesin assignment tiket.

Mereplikasi formula di sheet Sim_S1_Baseline / Sim_S2_Kumulatif / Sim_S3_Prioritas
baris demi baris, dengan presisi penuh (tidak dibulatkan ke menit kecuali
menit tunggal).

Logika (diambil langsung dari formula Excel):
  - free_at(t)      = MAX(Shift Start; MAX(Estimated Finish tiket t sebelumnya))
                       -> rumus S..V: =MAX(Parameter!B7; MAXIFS(L$1:Ln; I$1:In; tech))
  - busy_min(t)     = ROUND((free_at(t) - arrival) * 1440; 2)
  - skor(t):
        Available (busy_min <= 0)  -> metrik beban aturan (S1=0, S2=kumulatif, S3=berbobot)
        Busy      (busy_min >  0)  -> busy_penalty + busy_min
                       -> rumus AE..AH: =IF(ROUND((S-C)*1440;2)<=0; W; B9 + ROUND(...))
  - pilih teknisi skor minimum; MATCH(MIN(...)) terhadap daftar terurut
    T01..T04 -> tie-breaker ID terkecil.
  - Status = Available bila skor minimum < busy_penalty, selainnya Busy.
  - Start  = MAX(arrival; free_at teknisi terpilih)
             -> rumus K: =IF(J="Available"; C; INDEX(S:V; O))
  - Finish = Start + durasi/1440   (rumus L)
  - Waiting = ROUND((Start - arrival) * 1440; 0)   (rumus M)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

from .models import (
    Assignment,
    Parameters,
    TechStatus,
    Technician,
    Ticket,
)

BUSY_PENALTY = 1_000_000


@dataclass
class SimState:
    """State terkini selama satu jalankan simulasi (kolom S-AH sheet Sim_*)."""

    free_at: dict = field(default_factory=dict)  # tech_id -> datetime  (kolom S-V)
    cum_minutes: dict = field(default_factory=dict)  # tech_id -> menit   (kolom W-Z)
    cum_weighted: dict = field(default_factory=dict)  # tech_id -> pt-min (kolom AD)
    tickets_done: dict = field(default_factory=dict)  # tech_id -> jumlah tiket

    def init(self, technicians: list, shift_start: datetime) -> None:
        for t in technicians:
            self.free_at[t.id] = shift_start
            self.cum_minutes[t.id] = 0
            self.cum_weighted[t.id] = 0
            self.tickets_done[t.id] = 0


def minutes_between(a: datetime, b: datetime) -> float:
    """Selisih dalam menit, setara (a-b)*1440 di Excel."""
    return (a - b).total_seconds() / 60.0


def round2(x: float) -> float:
    """ROUND(x; 2) ala Excel (banker's rounding dihindari untuk angka .5)."""
    from decimal import Decimal, ROUND_HALF_UP

    return float(Decimal(repr(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class ScoreFunction:
    """Metrik beban untuk teknisi Available (perbedaan antar S1/S2/S3).

    Setara bagian "true" dari rumus AE..AH:
      S1 -> IF(...; 0; ...)         : beban aktif teknisi Available memang 0
      S2 -> IF(...; W/ cum_menit; ...)
      S3 -> IF(...; AA/ cum_berbobot; ...)
    """

    def __init__(self, name: str, note: str, metric: Callable[[SimState, str], float]):
        self.name = name
        self.note = note
        self.metric = metric

    @staticmethod
    def active_workload(_state: SimState, _tech_id: str) -> float:
        """S1 Baseline: beban aktif teknisi Available selalu 0.

        Konsekuensinya (tercatat di Catatan_Revisi #1): pemilihan praktis
        ditentukan tie-breaker ID, bukan pemerataan.
        """
        return 0.0

    @staticmethod
    def cumulative_workload(state: SimState, tech_id: str) -> float:
        """S2 Kumulatif: total menit yang sudah ditugaskan ke teknisi."""
        return float(state.cum_minutes[tech_id])

    @staticmethod
    def cumulative_weighted(state: SimState, tech_id: str) -> float:
        """S3 Priority-aware: total menit x bobot prioritas."""
        return float(state.cum_weighted[tech_id])


@dataclass
class SimResult:
    """Hasil satu jalankan simulasi."""

    assignments: list = field(default_factory=list)
    queued: list = field(default_factory=list)  # tiket berstatus Queued (hanya S4)


def run_simulation(
    tickets: list,
    technicians: list,
    params: Parameters,
    score_fn: ScoreFunction,
    queue_when_all_busy: bool = False,
) -> SimResult:
    """Jalankan simulasi penuh untuk satu aturan distribusi.

    `tickets` HARUS sudah terurut naik berdasarkan Timestamp (sheet Input_Tiket
    terurut; Sheet Ringkasan R8 memverifikasi "Cek urutan Timestamp = OK").

    `queue_when_all_busy=False` (default, S1-S3): saat semua teknisi Busy, tiket
    langsung jatuh ke fallback Earliest Estimated Finish.
    `queue_when_all_busy=True` (S4): tiket diparkir berstatus Queued dan
    dikembalikan di `SimResult.queued` untuk fase redistribusi.
    """
    tickets = sorted(tickets, key=lambda t: t.timestamp)
    state = SimState()
    state.init(technicians, params.shift_start)

    assignments: list = []
    queued: list = []
    for ticket in tickets:
        assign = _assign_ticket(
            ticket, technicians, params, score_fn, state,
            queue_when_all_busy=queue_when_all_busy,
        )
        if assign is not None:
            assignments.append(assign)
        else:
            queued.append(ticket)

    return SimResult(assignments=assignments, queued=queued)


def _assign_ticket(
    ticket: Ticket,
    technicians: list,
    params: Parameters,
    score_fn: ScoreFunction,
    state: SimState,
    queue_when_all_busy: bool = False,
) -> Optional[Assignment]:
    # --- hitung skor seluruh teknisi saat tiket ini tiba (kolom AE-AH) ---
    scores: dict = {}
    busy_minutes: dict = {}
    for tech in technicians:
        free = state.free_at[tech.id]
        busy_min = round2(minutes_between(free, ticket.timestamp))
        busy_minutes[tech.id] = busy_min
        if busy_min <= 0:
            scores[tech.id] = float(score_fn.metric(state, tech.id))
        else:
            scores[tech.id] = float(params.busy_penalty) + busy_min

    # --- pilih teknisi: skor minimum, tie-breaker ID terkecil (MATCH(MIN)) ---
    chosen: Optional[Technician] = None
    best_score = None
    for tech in technicians:  # list terurut T01..T04 -> tie-break otomatis
        s = scores[tech.id]
        if best_score is None or s < best_score:
            best_score = s
            chosen = tech

    assert chosen is not None
    min_score = best_score

    # Snapshot free_at SEBELUM penugasan (kolom S-V di Excel: MAXIFS di atas
    # baris ini, jadi belum memasukkan tiket yang sedang diproses).
    free_at_snapshot = dict(state.free_at)

    # --- Status: Available bila tidak terkena busy penalty ---
    all_busy = min_score >= params.busy_penalty

    # --- Mode S4: parkir tiket, jangan ditugaskan dulu ---
    if all_busy and queue_when_all_busy:
        return None

    status = TechStatus.BUSY if all_busy else TechStatus.AVAILABLE

    # --- Start Time = MAX(arrival; free_at teknisi terpilih) ---
    start = (
        ticket.timestamp
        if status is TechStatus.AVAILABLE
        else max(ticket.timestamp, state.free_at[chosen.id])
    )
    finish = start + timedelta(minutes=ticket.duration)
    waiting = int(round(minutes_between(start, ticket.timestamp)))

    if all_busy:
        # Parameter!B8: Fallback (semua Busy) -> Earliest Estimated Finish.
        # Skor = penalty + sisa menit, jadi min sudah = yang paling cepat selesai.
        rule_note = "Semua Busy → teknisi dengan waktu selesai paling cepat"
    else:
        rule_note = score_fn.note

    # --- update state: beban kumulatif & waktu bebas teknisi terpilih ---
    state.free_at[chosen.id] = finish
    state.cum_minutes[chosen.id] += ticket.duration
    state.cum_weighted[chosen.id] += ticket.weighted_load
    state.tickets_done[chosen.id] += 1

    return Assignment(
        ticket=ticket,
        tech_id=chosen.id,
        tech_name=chosen.name,
        tech_index=next(
            (i for i, t in enumerate(technicians, 1) if t.id == chosen.id), 0
        ),
        status=status,
        arrival=ticket.timestamp,
        start=start,
        finish=finish,
        waiting=waiting,
        rule_note=rule_note,
        weighted_load=ticket.weighted_load,
        scores=dict(scores),
        free_at=free_at_snapshot,
    )
