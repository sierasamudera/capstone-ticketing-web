"""Fasad tingkat tinggi: muat dataset, jalankan semua skenario, hitung indikator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .metrics import BalanceIndicators, compute_indicators
from .scenarios import SCENARIOS, run_scenario
from .seed import Dataset, load_dataset


@dataclass
class SimulationResult:
    """Hasil menjalankan satu atau semua skenario."""

    indicators: dict = field(default_factory=dict)  # key -> BalanceIndicators

    def __getitem__(self, key: str) -> BalanceIndicators:
        return self.indicators[key]

    def __contains__(self, key: str) -> bool:
        return key in self.indicators

    @property
    def keys(self) -> list:
        return list(self.indicators)

    @property
    def best_by_gap_minutes(self) -> Optional[str]:
        impl = {k: v for k, v in self.indicators.items() if v.implemented}
        return min(impl, key=lambda k: impl[k].gap_minutes) if impl else None

    @property
    def best_by_gap_weighted(self) -> Optional[str]:
        impl = {k: v for k, v in self.indicators.items() if v.implemented}
        return min(impl, key=lambda k: impl[k].gap_weighted) if impl else None


class Simulation:
    """Membungkus dataset + eksekusi skenario."""

    def __init__(self, dataset: Dataset):
        self.dataset = dataset

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Simulation":
        return cls(load_dataset(path))

    @property
    def tickets(self):
        return self.dataset.tickets

    @property
    def technicians(self):
        return self.dataset.technicians

    @property
    def parameters(self):
        return self.dataset.parameters

    def run(self, key: str) -> BalanceIndicators:
        """Jalankan satu skenario, kembalikan indikatornya."""
        meta = SCENARIOS[key]
        result = run_scenario(key, self.tickets, self.technicians, self.parameters)
        return compute_indicators(
            name=meta["name"],
            rule=meta["rule"],
            purpose=meta["purpose"],
            note=meta["note"],
            assignments=result.assignments,
            technicians=self.technicians,
            implemented=meta["implemented"],
        )

    def run_all(self) -> SimulationResult:
        """Jalankan S1-S4 dan kembalikan semua indikator."""
        return SimulationResult(
            indicators={key: self.run(key) for key in SCENARIOS}
        )
