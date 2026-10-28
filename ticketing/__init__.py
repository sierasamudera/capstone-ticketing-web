"""Sistem Ticketing — simulasi distribusi beban kerja teknisi.

Replikasi program dari logika di file Excel Simulasi_Workload_Ticketing_revisi.xlsx.

Pemakaian cepat::

    from ticketing import Simulation

    sim = Simulation.load()          # muat dataset default (data/tickets.json)
    result = sim.run_all()           # jalankan S1, S2, S3, S4
    print(result.indicators["S2"])   # indikator pemerataan
"""

from .models import (
    Assignment,
    Parameters,
    Priority,
    TechStatus,
    Technician,
    Ticket,
    TicketType,
)
from .seed import Dataset, add_ticket, load_dataset, save_dataset
from .scenarios import SCENARIOS, run_scenario
from .metrics import BalanceIndicators, compute_indicators, scenario_ranking

__version__ = "1.0.0"

__all__ = [
    "Simulation",
    "SimulationResult",
    "Dataset",
    "Ticket",
    "Technician",
    "Parameters",
    "Priority",
    "TicketType",
    "TechStatus",
    "Assignment",
    "BalanceIndicators",
    "SCENARIOS",
    "add_ticket",
    "load_dataset",
    "save_dataset",
]
