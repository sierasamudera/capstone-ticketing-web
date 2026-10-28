"""Indikator pemerataan beban kerja (sheet Ringkasan + Skenario).

Menghitung, untuk satu hasil simulasi:
  - per teknisi       : jumlah tiket, total durasi (menit), beban berbobot (pt-min)
  - indikator pemerataan: Max, Min, Gap = Max-Min, Balance Index = Min/Max,
                          Std Dev (populasi, =STDEVP Excel),
                          Jain's Fairness Index = (Σx)² / (n·Σx²)
  - layanan           : rata-rata & maksimum Waiting Time, waktu selesai terakhir

Semua indikator dihitung dalam **menit** (kanonik). Karena sheet Skenario di
Excel memakai fraksi hari (kolom D-E: =MAX(Ringkasan!C11:C14) yang berformat
waktu), `to_day_fraction()` disediakan untuk membandingkan langsung dengan
angka di Excel (nilai / 1440).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .models import Assignment

MINUTES_PER_DAY = 1440


def to_day_fraction(minutes: float) -> float:
    """Ubah menit menjadi fraksi hari agar bisa dibandingkan dengan sheet Excel."""
    return minutes / MINUTES_PER_DAY


def jains_index(values: list) -> float:
    """Jain's Fairness Index = (Σx)² / (n·Σx²).

    Rumus sama persis dengan sheet Skenario:
      =IF(SUMSQ(x)=0; 0; SUM(x)^2 / (COUNT(x) * SUMSQ(x)))
    Nilai 1 = sangat merata, 1/n = sangat timpang.
    """
    n = len(values)
    if n == 0:
        return 0.0
    sum_x = sum(values)
    sum_sq = sum(v * v for v in values)
    if sum_sq == 0:
        return 0.0
    return (sum_x * sum_x) / (n * sum_sq)


def stdev_population(values: list) -> float:
    """Std Dev populasi, setara =STDEVP() di Excel."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(var)


@dataclass
class LoadSummary:
    """Satu baris di sheet Ringkasan (per teknisi, per skenario)."""

    tech_id: str
    tickets: int = 0
    total_minutes: int = 0
    weighted_load: int = 0  # point-minutes (pt-min)

    def add(self, assignment: Assignment) -> None:
        self.tickets += 1
        self.total_minutes += assignment.ticket.duration
        self.weighted_load += assignment.ticket.weighted_load


@dataclass
class BalanceIndicators:
    """Satu baris di sheet Skenario (indikator pemerataan satu skenario)."""

    name: str
    rule: str
    purpose: str
    note: str
    implemented: bool = True

    # beban menit
    max_minutes: float = 0.0
    min_minutes: float = 0.0
    gap_minutes: float = 0.0
    balance_index: float = 0.0  # Min/Max
    stdev_minutes: float = 0.0
    jains_index: float = 0.0

    # beban berbobot (pt-min)
    max_weighted: float = 0.0
    min_weighted: float = 0.0
    gap_weighted: float = 0.0
    jains_index_weighted: float = 0.0

    # layanan
    avg_waiting: float = 0.0
    max_waiting: float = 0.0
    last_finish: Optional[datetime] = None

    # agregat sheet Ringkasan
    total_tickets: int = 0
    unique_cases: int = 0
    total_duration: int = 0
    ideal_load: float = 0.0  # total durasi / jumlah teknisi

    loads: dict = field(default_factory=dict)  # tech_id -> LoadSummary
    assignments: list = field(default_factory=list)  # detail per tiket (untuk ekspor)

    # --- properti fraksi-hari untuk perbandingan langsung dengan Excel ---

    @property
    def max_minutes_day(self) -> float:
        return to_day_fraction(self.max_minutes)

    @property
    def min_minutes_day(self) -> float:
        return to_day_fraction(self.min_minutes)

    @property
    def gap_minutes_day(self) -> float:
        return to_day_fraction(self.gap_minutes)

    @property
    def stdev_minutes_day(self) -> float:
        return to_day_fraction(self.stdev_minutes)

    @property
    def avg_waiting_day(self) -> float:
        return to_day_fraction(self.avg_waiting)

    @property
    def best(self) -> bool:
        """Penanda: apakah skenario ini punya Gap menit terkecil (sheet Skenario R7)."""
        return False


def compute_loads(assignments: list, technicians: list) -> dict:
    """Sheet Ringkasan R10-R14: per teknisi -> jumlah tiket, durasi, berbobot.

    Total Durasi = beban kumulatif (dasar pemerataan), termasuk tiket
    Technician Request (Catatan di sheet Ringkasan).
    """
    loads = {t.id: LoadSummary(tech_id=t.id) for t in technicians}
    for a in assignments:
        if a.tech_id in loads:
            loads[a.tech_id].add(a)
    return loads


def compute_indicators(
    name: str,
    rule: str,
    purpose: str,
    note: str,
    assignments: list,
    technicians: list,
    implemented: bool = True,
) -> BalanceIndicators:
    """Hitung seluruh indikator untuk satu hasil simulasi (sheet Skenario)."""
    loads = compute_loads(assignments, technicians)
    minutes = [loads[t.id].total_minutes for t in technicians]
    weighted = [loads[t.id].weighted_load for t in technicians]

    ind = BalanceIndicators(
        name=name,
        rule=rule,
        purpose=purpose,
        note=note,
        implemented=implemented,
        loads=loads,
        assignments=list(assignments),
    )

    # --- beban menit (kolom D-I sheet Skenario) ---
    if minutes:
        ind.max_minutes = max(minutes)
        ind.min_minutes = min(minutes)
        ind.gap_minutes = ind.max_minutes - ind.min_minutes
        ind.balance_index = ind.min_minutes / ind.max_minutes if ind.max_minutes else 0.0
        ind.stdev_minutes = stdev_population(minutes)
        ind.jains_index = jains_index(minutes)

    # --- beban berbobot (kolom J-K sheet Skenario) ---
    if weighted:
        ind.max_weighted = max(weighted)
        ind.min_weighted = min(weighted)
        ind.gap_weighted = ind.max_weighted - ind.min_weighted
        ind.jains_index_weighted = jains_index(weighted)

    # --- layanan (kolom L-N sheet Skenario) ---
    waitings = [a.waiting for a in assignments]
    if waitings:
        ind.avg_waiting = sum(waitings) / len(waitings)
        ind.max_waiting = max(waitings)
    if assignments:
        ind.last_finish = max(a.finish for a in assignments)

    # --- agregat sheet Ringkasan ---
    ind.total_tickets = len(assignments)
    ind.unique_cases = sum(1 for a in assignments if a.ticket.is_root_case)
    ind.total_duration = sum(a.ticket.duration for a in assignments)
    ind.ideal_load = (
        ind.total_duration / len(technicians) if technicians else 0.0
    )

    return ind


def scenario_ranking(indicators: dict) -> dict:
    """Sheet Skenario R7-R10: skenario terbaik & penurunan Gap."""
    impl = {k: v for k, v in indicators.items() if v.implemented}
    if not impl:
        return {}

    best_min = min(impl, key=lambda k: impl[k].gap_minutes)
    best_w = min(impl, key=lambda k: impl[k].gap_weighted)
    base = impl.get("S1")

    result = {
        "best_gap_minutes": best_min,
        "best_gap_weighted": best_w,
    }
    if base is not None:
        for key, field_name in (
            ("S2", "gap_minutes"),
            ("S3", "gap_weighted"),
        ):
            other = impl.get(key)
            if other is not None:
                denom = getattr(base, field_name) or float("nan")
                reduction = 1 - (getattr(other, field_name) / denom)
                result[f"reduction_{key}"] = reduction

    return result
