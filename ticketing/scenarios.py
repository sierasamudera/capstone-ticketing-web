"""Definisi skenario aturan distribusi (sheet Skenario).

  S1 Baseline      - Lowest Active Workload (rule V2; sengaja dipertahankan
                     sebagai bukti bias: semua teknisi Available berbeban aktif
                     0, jadi praktis tie-breaker ID yang menentukan).
  S2 Kumulatif     - Lowest Cumulative Workload (usulan perbaikan rule V2).
  S3 Priority-aware- Lowest Cumulative Weighted Workload (bobot prioritas
                     Low=1/Medium=2/High=3; Catatan_Revisi #4: masih asumsi).
  S4 Redistribution- Highest -> Lowest. Di Excel ditandai "BELUM
                     diimplementasikan" karena belum ada definisi tiket Queued.
                     Di program ini diimplementasikan sebagai USULAN:
                     (a) tiket yang tiba saat semua teknisi Busy berstatus
                         Queued (tidak langsung di-assign ke earliest-finish),
                     (b) fase redistribusi: tiket Queued prioritas tertinggi
                         diserahkan kepada teknisi bebas dengan beban kumulatif
                         TERENDAH -- beban yang tadinya menumpuk di teknisi
                         sibuk (tertinggi) dialihkan ke teknisi paling ringan.
"""

from __future__ import annotations

import itertools
from datetime import timedelta
from typing import Optional

from .engine import (
    ScoreFunction,
    SimResult,
    SimState,
    run_simulation,
)
from .models import Assignment, TechStatus, Technician, Ticket

# ---------------------------------------------------------------------------
# S1 / S2 / S3: tiga metrik beban untuk teknisi Available
# ---------------------------------------------------------------------------

S1_LOWEST_ACTIVE = ScoreFunction(
    name="S1 Baseline",
    note="Available + beban aktif terendah; tie-breaker ID",
    metric=ScoreFunction.active_workload,
)

S2_LOWEST_CUMULATIVE = ScoreFunction(
    name="S2 Cumulative",
    note="Available + beban kumulatif (menit) terendah; tie-breaker ID",
    metric=ScoreFunction.cumulative_workload,
)

S3_LOWEST_WEIGHTED = ScoreFunction(
    name="S3 Priority-aware",
    note="Available + beban kumulatif berbobot prioritas terendah; tie-breaker ID",
    metric=ScoreFunction.cumulative_weighted,
)

SCORE_FUNCTIONS = {
    "S1": S1_LOWEST_ACTIVE,
    "S2": S2_LOWEST_CUMULATIVE,
    "S3": S3_LOWEST_WEIGHTED,
}


def run_s1(tickets, technicians, params) -> SimResult:
    """S1 Baseline - Lowest Active Workload (tie-breaker Technician ID)."""
    return run_simulation(tickets, technicians, params, S1_LOWEST_ACTIVE)


def run_s2(tickets, technicians, params) -> SimResult:
    """S2 Cumulative - Lowest Cumulative Workload."""
    return run_simulation(tickets, technicians, params, S2_LOWEST_CUMULATIVE)


def run_s3(tickets, technicians, params) -> SimResult:
    """S3 Priority-aware - Lowest Cumulative Weighted Workload."""
    return run_simulation(tickets, technicians, params, S3_LOWEST_WEIGHTED)


# ---------------------------------------------------------------------------
# S4: Redistribution (Highest -> Lowest) -- USULAN
# ---------------------------------------------------------------------------

S4_NOTE_QUEUED = "Semua Busy → tiket Queued, menunggu redistribusi"
S4_NOTE_REDIST = "Redistribusi Highest→Lowest → teknisi bebas berbeban terendah"


def run_s4(tickets, technicians, params) -> SimResult:
    """S4 Redistribution (Highest -> Lowest). Lihat docstring modul.

    Event-driven simulation, SATU pass, agar tiket Queued benar-benar
    disisipkan pada saat teknisi bebas -- bukan dicomot ke akhir hari:

      - Event 'free' (teknisi bebas) diproses SEBELUM event 'arrival' pada
        timestamp yang sama, supaya tiket antrian (backlog dari teknisi
        sibuk) lebih dulu dilayani daripada tiket baru yang tiba.
      - Saat tiket tiba dan ada teknisi bebas -> aturan S2 (teknisi bebas
        berbeban kumulatif terendah).
      - Saat semua sibuk -> tiket masuk antrean (status Queued), dan event
        'free' dijadwalkan pada waktu bebas paling cepat.
      - Drain antrean: tiap tiket antrian prioritas tertinggi diserahkan ke
        teknisi bebas dengan beban kumulatif TERENDAH (inti "Highest ->
        Lowest").
    """
    import heapq

    tickets = sorted(tickets, key=lambda t: t.timestamp)
    state = SimState()
    state.init(technicians, params.shift_start)

    # Antrean prioritas per event: (waktu, jenis, urutan, payload).
    # jenis 0 = free (didahulukan), 1 = arrival.
    events: list = []
    seq = itertools.count()
    for t in tickets:
        heapq.heappush(events, (t.timestamp, 1, next(seq), t))

    queue: list = []  # antrean tiket: (−bobot, arrival, id, ticket)
    assignments: list = []

    def free_techs(now) -> list:
        return [t for t in technicians if state.free_at[t.id] <= now]

    def pick_target(now) -> Optional[Technician]:
        free = free_techs(now)
        if not free:
            return None
        return min(free, key=lambda t: (state.cum_minutes[t.id], t.id))

    def assign(ticket: Ticket, target: Technician, now) -> None:
        # Snapshot free_at SEBELUM penugasan (konsisten dengan S1-S3).
        free_at_snapshot = dict(state.free_at)
        start = max(ticket.timestamp, state.free_at[target.id])
        finish = start + timedelta(minutes=ticket.duration)
        waiting = int(round((start - ticket.timestamp).total_seconds() / 60.0))
        state.free_at[target.id] = finish
        state.cum_minutes[target.id] += ticket.duration
        state.cum_weighted[target.id] += ticket.weighted_load
        state.tickets_done[target.id] += 1
        assignments.append(
            Assignment(
                ticket=ticket,
                tech_id=target.id,
                tech_name=target.name,
                tech_index=next(
                    (i for i, t in enumerate(technicians, 1) if t.id == target.id), 0
                ),
                # semua tech Busy saat tiba -> tiket lalu Queued
                status=TechStatus.BUSY,
                arrival=ticket.timestamp,
                start=start,
                finish=finish,
                waiting=waiting,
                rule_note=S4_NOTE_REDIST,
                weighted_load=ticket.weighted_load,
                scores={},
                free_at=free_at_snapshot,
            )
        )

    while events:
        now, _kind, _seq, payload = heapq.heappop(events)

        if _kind == 1:  # arrival
            ticket: Ticket = payload
            target = pick_target(now)
            if target is not None:
                assign(ticket, target, now)
            else:
                heapq.heappush(
                    queue, (-ticket.weight, ticket.timestamp, ticket.id, ticket)
                )

        # drain antrean selama masih ada teknisi bebas pada waktu ini
        while queue:
            target = pick_target(now)
            if target is None:
                break
            _, _, _, ticket = heapq.heappop(queue)
            assign(ticket, target, now)

        # jadwalkan event free berikutnya bila antrean masih berisi
        if queue:
            earliest = min(state.free_at[t.id] for t in technicians)
            heapq.heappush(events, (earliest, 0, next(seq), None))

    assignments.sort(key=lambda a: (a.arrival, a.ticket.id))
    return SimResult(assignments=assignments, queued=[])


SCENARIOS = {
    "S1": {
        "name": "S1 Baseline",
        "rule": "Lowest Active Workload (Available; tie-breaker ID)",
        "purpose": "Distribusi dasar (rule V2 setelah koreksi)",
        "note": "Rule V2: semua Available berbeban aktif 0 → praktis memilih ID terkecil",
        "runner": run_s1,
        "implemented": True,
    },
    "S2": {
        "name": "S2 Cumulative",
        "rule": "Lowest Cumulative Workload",
        "purpose": "Pemerataan berdasarkan total menit yang sudah ditugaskan "
                   "(termasuk tiket Technician Request)",
        "note": "Usulan perbaikan rule; perlu validasi dosen",
        "runner": run_s2,
        "implemented": True,
    },
    "S3": {
        "name": "S3 Priority-aware",
        "rule": "Lowest Cumulative Weighted Workload",
        "purpose": "Priority ikut memengaruhi pemilihan",
        "note": "Bobot prioritas Low=1, Medium=2, High=3 belum final",
        "runner": run_s3,
        "implemented": True,
    },
    "S4": {
        "name": "S4 Redistribution",
        "rule": "Highest → Lowest",
        "purpose": "Menguji dampak redistribusi tiket antrean",
        "note": "USULAN implementasi: tiket Queued dialihkan ke teknisi bebas "
                "berbeban terendah. Perlu validasi dosen.",
        "runner": run_s4,
        "implemented": True,
    },
}


def run_scenario(key: str, tickets, technicians, params) -> SimResult:
    """Jalankan satu skenario berdasarkan key-nya (S1..S4)."""
    if key not in SCENARIOS:
        raise ValueError(f"Skenario tidak dikenal: {key!r} (pilih: {', '.join(SCENARIOS)})")
    return SCENARIOS[key]["runner"](tickets, technicians, params)
