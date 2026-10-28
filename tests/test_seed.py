"""Verifikasi dataset seed cocok dengan sheet Input_Tiket Excel asli."""

from __future__ import annotations

import os

import pytest

from ticketing.seed import load_dataset

EXCEL = r"C:\Users\SUPER USER\OneDrive - Universitas Terbuka\TUTON SEMESTER 7\Capstone Project\Tugas 1\Simulasi_Workload_Ticketing_revisi.xlsx"

pytestmark = pytest.mark.skipif(
    not os.path.exists(EXCEL), reason="file Excel asli tidak ditemukan"
)


@pytest.fixture(scope="module")
def excel_input():
    import openpyxl

    wb = openpyxl.load_workbook(EXCEL, data_only=True)
    ws = wb["Input_Tiket"]
    rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[0]]
    return rows


def test_jumlah_tiket(excel_input):
    ds = load_dataset()
    assert len(ds.tickets) == len(excel_input) == 22


def test_field_per_baris(excel_input):
    """Setiap baris Input_Tiket harus terbaca persis sama di dataset."""
    ds = load_dataset()
    by_id = {t.id: t for t in ds.tickets}
    for row in excel_input:
        t = by_id[row[0]]
        assert t.ticket_type.value == row[1]
        assert t.created_by == row[2]
        assert t.related_id == (row[3] or None)
        assert t.requested_by == (row[4] or None)
        assert t.timestamp.strftime("%Y-%m-%d %H:%M:%S") == row[5].strftime("%Y-%m-%d %H:%M:%S")
        assert t.category == row[6]
        assert t.detail == row[7]
        assert t.priority.value == row[8]
        assert t.weight == row[9]  # VLOOKUP ke Parameter
        assert t.duration == row[10]


def test_urutan_timestamp_meningkat():
    """Sheet Ringkasan R8: 'Cek urutan Timestamp = OK'."""
    ds = load_dataset()
    stamps = [t.timestamp for t in sorted(ds.tickets, key=lambda x: x.timestamp)]
    assert stamps == sorted(stamps)


def test_prefix_id_sesuai_jenis():
    """Catatan_Revisi #7: T- untuk User Report, TK- untuk Technician Request."""
    ds = load_dataset()
    for t in ds.tickets:
        expected_prefix = "TK-" if t.ticket_type.value == "Technician Request" else "T-"
        assert t.id.startswith(expected_prefix), t.id


def test_tiket_technician_request_punya_related():
    """Catatan_Revisi #7: tiket bantuan harus terhubung ke kasus lain."""
    ds = load_dataset()
    for t in ds.tickets:
        if t.ticket_type.value == "Technician Request":
            assert t.related_id is not None
            assert t.requested_by is not None


def test_jumlah_kasus_unik():
    """Sheet Ringkasan: 22 tiket, 20 kasus unik (2 TK- punya Related Ticket ID)."""
    ds = load_dataset()
    assert sum(1 for t in ds.tickets if t.is_root_case) == 20


def test_parameter_dari_sheet():
    """Bobot prioritas & busy penalty harus sama dengan sheet Parameter."""
    import openpyxl

    ds = load_dataset()
    wb = openpyxl.load_workbook(EXCEL, data_only=True)
    ws = wb["Parameter"]
    params = {str(r[0]): r[1] for r in ws.iter_rows(min_row=2, values_only=True) if r[0]}

    assert ds.parameters.priority_weights == {
        "Low": params["Low"], "Medium": params["Medium"], "High": params["High"]
    }
    assert ds.parameters.busy_penalty == params["Busy penalty (skor)"]
    assert (
        ds.parameters.shift_start.strftime("%Y-%m-%d %H:%M:%S")
        == params["Shift Start"].strftime("%Y-%m-%d %H:%M:%S")
    )


def test_teknisi_dari_sheet():
    import openpyxl

    ds = load_dataset()
    wb = openpyxl.load_workbook(EXCEL, data_only=True)
    ws = wb["Teknisi"]
    rows = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[0]]
    assert [t.id for t in ds.technicians] == [r[0] for r in rows]
    assert [t.name for t in ds.technicians] == [r[1] for r in rows]
