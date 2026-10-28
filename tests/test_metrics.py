"""Validasi indikator pemerataan terhadap sheet Skenario Excel.

Nilai pembanding diambil langsung dari sheet Skenario (kolom D-O) dan
sheet Ringkasan (kolom beban per teknisi).
"""

from __future__ import annotations

import os

import pytest

from ticketing.metrics import compute_indicators, jains_index, stdev_population
from ticketing.scenarios import SCENARIOS, run_scenario
from ticketing.seed import load_dataset
from ticketing.simulation import Simulation

EXCEL = r"C:\Users\SUPER USER\OneDrive - Universitas Terbuka\TUTON SEMESTER 7\Capstone Project\Tugas 1\Simulasi_Workload_Ticketing_revisi.xlsx"

pytestmark = pytest.mark.skipif(
    not os.path.exists(EXCEL), reason="file Excel asli tidak ditemukan"
)

TOL = 1e-6


@pytest.fixture(scope="module")
def dataset():
    return load_dataset()


@pytest.fixture(scope="module")
def skenario_rows():
    import openpyxl

    wb = openpyxl.load_workbook(EXCEL, data_only=True)
    ws = wb["Skenario"]
    out = {}
    for row in ws.iter_rows(min_row=2, max_row=5, values_only=True):
        key = str(row[0]).split()[0]
        if key in ("S1", "S2", "S3"):
            out[key] = row
    return out


def _dayfrac(value):
    """Excel menyimpan durasi sebagai timedelta/fraksi hari."""
    import datetime as _dt

    if value is None:
        return None
    if isinstance(value, _dt.timedelta):
        return value.total_seconds() / 86400.0
    if isinstance(value, _dt.datetime):
        return (value - _dt.datetime(1899, 12, 30)).total_seconds() / 86400.0
    return float(value)


@pytest.mark.parametrize("key", ["S1", "S2", "S3"])
def test_indikator_skenario_sesuai_excel(dataset, skenario_rows, key):
    ind = Simulation(dataset).run(key)
    row = skenario_rows[key]

    # D=Max, E=Min, F=Gap, G=Min/Max, H=StdDev, I=Jain's (fraksi hari untuk D-H)
    assert abs(ind.max_minutes / 1440 - _dayfrac(row[3])) < TOL
    assert abs(ind.min_minutes / 1440 - _dayfrac(row[4])) < TOL
    assert abs(ind.gap_minutes / 1440 - _dayfrac(row[5])) < TOL
    assert abs(ind.balance_index - _dayfrac(row[6])) < TOL
    assert abs(ind.stdev_minutes / 1440 - _dayfrac(row[7])) < TOL
    assert abs(ind.jains_index - _dayfrac(row[8])) < TOL

    # J=Gap Weighted, K=Jain's Weighted (pt-min, bukan fraksi hari)
    assert abs(ind.gap_weighted - _dayfrac(row[9])) < TOL
    assert abs(ind.jains_index_weighted - _dayfrac(row[10])) < TOL

    # L=Avg waiting (menit), M=Max waiting (menit)
    assert abs(ind.avg_waiting - _dayfrac(row[11])) < TOL
    assert abs(ind.max_waiting - _dayfrac(row[12])) < TOL


@pytest.mark.parametrize("key", ["S1", "S2", "S3"])
def test_beban_per_teknisi_sheet_ringkasan(dataset, key):
    """Sheet Ringkasan R11-R14: total durasi per teknisi per skenario."""
    import openpyxl

    wb = openpyxl.load_workbook(EXCEL, data_only=True)
    ws = wb["Ringkasan"]
    header = [str(c) if c is not None else "" for c in
              next(ws.iter_rows(min_row=10, max_row=10, values_only=True))]
    ind = Simulation(dataset).run(key)
    for row in ws.iter_rows(min_row=11, max_row=14, values_only=True):
        tech = str(row[0])
        for i, h in enumerate(header):
            if h.startswith(key) and "Durasi" in h:
                expected = _dayfrac(row[i])
                assert abs(ind.loads[tech].total_minutes / 1440 - expected) < TOL, (
                    f"{key} {tech}: {ind.loads[tech].total_minutes} menit != {expected}"
                )
            if h.startswith(key) and "Weighted" in h:
                assert abs(ind.loads[tech].weighted_load - _dayfrac(row[i])) < TOL


@pytest.mark.parametrize("key", ["S1", "S2", "S3"])
def test_agregat_sheet_ringkasan(dataset, key):
    """Sheet Ringkasan R2-R7: total tiket, kasus unik, durasi, beban ideal."""
    ind = Simulation(dataset).run(key)
    assert ind.total_tickets == 22
    assert ind.unique_cases == 20
    assert ind.total_duration == 765
    assert abs(ind.ideal_load - 191.25) < TOL


def test_last_finish_sama_untuk_semua_skenario(dataset):
    """Sheet Skenario kolom N: semua skenario selesai 13:05."""
    sim = Simulation(dataset)
    for key in ("S1", "S2", "S3"):
        ind = sim.run(key)
        assert ind.last_finish is not None
        assert ind.last_finish.strftime("%H:%M") == "13:05"


# ---------------------------------------------------------------------------
# Unit metrik murni
# ---------------------------------------------------------------------------


def test_jains_index_perfectly_balanced():
    assert jains_index([100, 100, 100, 100]) == pytest.approx(1.0)


def test_jains_index_extremely_imbalanced():
    # (Σx)²/(n·Σx²) = 400²/(4·10000) = 0.01... -> 1/n saat satu pemegang
    assert jains_index([400, 0, 0, 0]) == pytest.approx(0.25)


def test_jains_index_empty():
    assert jains_index([]) == 0.0


def test_jains_index_all_zero():
    assert jains_index([0, 0, 0]) == 0.0


def test_stdev_population():
    # STDEVP(245,245,125,150): mean=191.25, var=2967.1875
    val = stdev_population([245, 245, 125, 150])
    assert val == pytest.approx(54.47189642375231, abs=1e-9)


def test_stdev_single_value():
    assert stdev_population([42]) == 0.0


def test_reduksi_gap_sheet_skenario_r9_r10(dataset):
    """Sheet Skenario: penurunan Gap menit S2 vs S1 = 79.17%, weighted S3 vs S1 = 71.43%."""
    sim = Simulation(dataset)
    s1, s2, s3 = sim.run("S1"), sim.run("S2"), sim.run("S3")
    assert abs((1 - s2.gap_minutes / s1.gap_minutes) - 0.7916666666666667) < TOL
    assert abs((1 - s3.gap_weighted / s1.gap_weighted) - 0.7142857142857143) < TOL


def test_skenario_terbaik_gap(dataset):
    """Sheet Skenario R7-R8: Gap menit terkecil = S2, weighted terkecil = S3."""
    result = Simulation(dataset).run_all()
    assert result.best_by_gap_minutes == "S2"
    assert result.best_by_gap_weighted == "S3"
