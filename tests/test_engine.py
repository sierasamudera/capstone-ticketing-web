"""Validasi mesin assignment terhadap sheet Sim_S1/S2/S3 Excel.

Setiap baris di sheet Simulasi (Assigned Technician, Start, Finish, Waiting,
Status) harus terbentuk persis sama oleh program.
"""

from __future__ import annotations

import os

import pytest

from ticketing.engine import SimState
from ticketing.scenarios import run_s1, run_s2, run_s3, run_s4
from ticketing.seed import load_dataset

EXCEL = r"C:\Users\SUPER USER\OneDrive - Universitas Terbuka\TUTON SEMESTER 7\Capstone Project\Tugas 1\Simulasi_Workload_Ticketing_revisi.xlsx"

pytestmark = pytest.mark.skipif(
    not os.path.exists(EXCEL), reason="file Excel asli tidak ditemukan"
)

RUNNERS = {"S1": run_s1, "S2": run_s2, "S3": run_s3}
SHEET_OF = {
    "S1": "Sim_S1_Baseline",
    "S2": "Sim_S2_Kumulatif",
    "S3": "Sim_S3_Prioritas",
}

# Indeks kolom di sheet Sim_* (0-based):
# I=8 Assigned Technician, J=9 Status, K=10 Start, L=11 Finish, M=12 Waiting,
# P=15 Weighted Load, S..V=18..21 Free At, W..Z=22..25 beban kumulatif menit,
# AA..AD=26..29 beban kumulatif berbobot.


@pytest.fixture(scope="module")
def dataset():
    return load_dataset()


@pytest.fixture(scope="module")
def excel_rows():
    import openpyxl

    wb = openpyxl.load_workbook(EXCEL, data_only=True)
    return {
        key: {
            str(r[0]): r
            for r in wb[SHEET_OF[key]].iter_rows(min_row=2, values_only=True)
            if r[0]
        }
        for key in SHEET_OF
    }


@pytest.mark.parametrize("key", ["S1", "S2", "S3"])
def test_assigned_technician_sesuai_excel(dataset, excel_rows, key):
    result = RUNNERS[key](dataset.tickets, dataset.technicians, dataset.parameters)
    for a in result.assignments:
        row = excel_rows[key][a.ticket.id]
        assert a.tech_id == row[8], f"{key} {a.ticket.id}: {a.tech_id} != {row[8]}"


@pytest.mark.parametrize("key", ["S1", "S2", "S3"])
def test_status_sesuai_excel(dataset, excel_rows, key):
    result = RUNNERS[key](dataset.tickets, dataset.technicians, dataset.parameters)
    for a in result.assignments:
        row = excel_rows[key][a.ticket.id]
        assert a.status.value == row[9], f"{key} {a.ticket.id}"


@pytest.mark.parametrize("key", ["S1", "S2", "S3"])
def test_start_finish_waiting_sesuai_excel(dataset, excel_rows, key):
    result = RUNNERS[key](dataset.tickets, dataset.technicians, dataset.parameters)
    for a in result.assignments:
        row = excel_rows[key][a.ticket.id]
        assert a.start == row[10], f"{key} {a.ticket.id} start {a.start} != {row[10]}"
        assert a.finish == row[11], f"{key} {a.ticket.id} finish {a.finish} != {row[11]}"
        assert a.waiting == row[12], f"{key} {a.ticket.id} waiting {a.waiting} != {row[12]}"


@pytest.mark.parametrize("key", ["S1", "S2", "S3"])
def test_weighted_load_kolom_P(dataset, excel_rows, key):
    """Kolom P = Weighted Load (pt-min) = durasi x bobot prioritas."""
    result = RUNNERS[key](dataset.tickets, dataset.technicians, dataset.parameters)
    for a in result.assignments:
        row = excel_rows[key][a.ticket.id]
        assert a.weighted_load == row[15], f"{key} {a.ticket.id}"


@pytest.mark.parametrize("key", ["S1", "S2", "S3"])
def test_beban_kumulatif_kolom_W_AD(dataset, excel_rows, key):
    """Kolom W-Z (beban kumulatif menit) & AA-AD (berbobot) per teknisi.

    Di Excel nilai ini dihitung SEBELUM tiket pada baris tsb. di-assign
    (SUMIFS merujuk baris di atasnya), jadi kita bandingkan state sebelum
    penugasan tiap tiket.
    """
    result = RUNNERS[key](dataset.tickets, dataset.technicians, dataset.parameters)
    state = SimState()
    state.init(dataset.technicians, dataset.parameters.shift_start)
    tech_ids = [t.id for t in dataset.technicians]

    for a in result.assignments:
        row = excel_rows[key][a.ticket.id]
        cum_min_excel = [row[i] for i in range(22, 26)]
        cum_w_excel = [row[i] for i in range(26, 30)]
        for i, tid in enumerate(tech_ids):
            assert state.cum_minutes[tid] == cum_min_excel[i], (
                f"{key} {a.ticket.id} cum_min {tid}: "
                f"{state.cum_minutes[tid]} != {cum_min_excel[i]}"
            )
            assert state.cum_weighted[tid] == cum_w_excel[i], (
                f"{key} {a.ticket.id} cum_weighted {tid}: "
                f"{state.cum_weighted[tid]} != {cum_w_excel[i]}"
            )
        state.free_at[a.tech_id] = a.finish
        state.cum_minutes[a.tech_id] += a.ticket.duration
        state.cum_weighted[a.tech_id] += a.ticket.weighted_load
        state.tickets_done[a.tech_id] += 1


@pytest.mark.parametrize("key", ["S1", "S2", "S3"])
def test_free_at_kolom_S_V(dataset, excel_rows, key):
    """Kolom S-V = Free At T01..T04 (waktu teknisi bebas saat tiket tiba)."""
    result = RUNNERS[key](dataset.tickets, dataset.technicians, dataset.parameters)
    for a in result.assignments:
        row = excel_rows[key][a.ticket.id]
        for i, tid in enumerate([t.id for t in dataset.technicians]):
            expected = row[18 + i]
            got = a.free_at[tid]
            assert got == expected, (
                f"{key} {a.ticket.id} free_at {tid}: {got} != {expected}"
            )


@pytest.mark.parametrize("key", ["S1", "S2", "S3"])
def test_skor_minimum_tapi_busy_penalty_menang(dataset, excel_rows, key):
    """Kolom AE-AH: skor teknisi Busy pasti >= busy_penalty (1.000.000)."""
    result = RUNNERS[key](dataset.tickets, dataset.technicians, dataset.parameters)
    for a in result.assignments:
        row = excel_rows[key][a.ticket.id]
        for i in range(30, 34):  # AE..AH
            excel_score = row[i]
            if excel_score is None:
                continue
            tid = [t.id for t in dataset.technicians][i - 30]
            assert abs(a.scores[tid] - excel_score) < 1e-9, (
                f"{key} {a.ticket.id} skor {tid}: {a.scores[tid]} != {excel_score}"
            )


# ---------------------------------------------------------------------------
# Skenario S4 (di Excel ditandai "BELUM diimplementasikan")
# ---------------------------------------------------------------------------


def test_s4_semua_tiket_tertangani(dataset):
    """Tidak boleh ada tiket tertinggal di antrean di akhir hari."""
    result = run_s4(dataset.tickets, dataset.technicians, dataset.parameters)
    assert len(result.queued) == 0
    assert len(result.assignments) == len(dataset.tickets)


def test_s4_lebih_merata_dari_s1(dataset):
    """Tujuan S4: redistribusi harus memperkecil gap dibanding baseline."""
    s1 = run_s1(dataset.tickets, dataset.technicians, dataset.parameters)
    s4 = run_s4(dataset.tickets, dataset.technicians, dataset.parameters)
    mins_s1 = [sum(a.ticket.duration for a in s1.assignments if a.tech_id == t.id)
               for t in dataset.technicians]
    mins_s4 = [sum(a.ticket.duration for a in s4.assignments if a.tech_id == t.id)
               for t in dataset.technicians]
    gap_s1 = max(mins_s1) - min(mins_s1)
    gap_s4 = max(mins_s4) - min(mins_s4)
    assert gap_s4 < gap_s1, f"gap S4 ({gap_s4}) harus < gap S1 ({gap_s1})"


def test_s4_total_durasi_tetap(dataset):
    """Redistribusi hanya memindahkan tiket, tidak mengubah total durasi."""
    result = run_s4(dataset.tickets, dataset.technicians, dataset.parameters)
    total = sum(a.ticket.duration for a in result.assignments)
    assert total == sum(t.duration for t in dataset.tickets)


def test_s4_start_tidak_sebelum_arrival(dataset):
    result = run_s4(dataset.tickets, dataset.technicians, dataset.parameters)
    for a in result.assignments:
        assert a.start >= a.ticket.timestamp
        minutes = (a.finish - a.start).total_seconds() / 60
        assert minutes == a.ticket.duration
        assert a.waiting >= 0
