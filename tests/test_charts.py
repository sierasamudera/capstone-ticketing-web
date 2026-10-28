"""Test generator chart SVG (mengikuti skill dataviz)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from ticketing.web.charts import grouped_bar_chart, series_color

# charts.py memakai var(--viz-series-N, <hex>) — fallback hex adalah palette
# dataviz yang sudah divalidasi (CVD-safe). Kita assert terhadap fallback tsb.
PALETTE_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
PALETTE_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500"]


@pytest.fixture
def sample_chart():
    cats = [("S1", "S1"), ("S2", "S2")]
    series = [("T01", "T01"), ("T02", "T02"), ("T03", "T03"), ("T04", "T04")]
    values = {
        ("S1", "T01"): 245, ("S1", "T02"): 245, ("S1", "T03"): 125, ("S1", "T04"): 150,
        ("S2", "T01"): 185, ("S2", "T02"): 180, ("S2", "T03"): 195, ("S2", "T04"): 205,
    }
    return grouped_bar_chart(
        categories=cats, series=series, values=values,
        title="Beban per Teknisi", unit="menit",
    )


def test_chart_well_formed(sample_chart):
    svg = re.search(r"<svg.*?</svg>", sample_chart, re.S).group(0)
    ET.fromstring(svg)  # error kalau tidak well-formed


def test_chart_aria_label_dan_title(sample_chart):
    assert 'role="img"' in sample_chart
    assert "Beban per Teknisi" in sample_chart
    # tooltip per-mark untuk aksesibilitas
    assert sample_chart.count("<title>") == 8  # 8 bar


def test_chart_ada_legend_untuk_multi_series(sample_chart):
    """Skill: legend wajib untuk >= 2 series."""
    assert 'class="viz-legend"' in sample_chart
    assert sample_chart.count('class="viz-legend"') == 4


def test_chart_hue_konsisten_per_series():
    """Skill: warna mengikuti entitas, slot tetap, tidak diacak."""
    # var(--viz-series-N, <hex>) — fallback hex harus cocok slot
    assert PALETTE_LIGHT[0] in series_color(0)
    assert PALETTE_LIGHT[1] in series_color(1)
    assert PALETTE_DARK[0] in series_color(0, dark=True)
    assert series_color(5).startswith("var(--viz-series-2,")  # lipat ke slot 2
    assert PALETTE_LIGHT[1] in series_color(5)


def test_chart_palet_divalidasi_tidak_pelangi():
    """Skill: hanya palette yang sudah lulus validasi CVD."""
    for hexcolor in PALETTE_LIGHT + PALETTE_DARK:
        assert re.fullmatch(r"#[0-9a-f]{6}", hexcolor)


def test_chart_mark_tipis_dan_ujung_bulat(sample_chart):
    """Skill: mark tipis, ujung data dibulatani 4px."""
    assert 'rx="4"' in sample_chart
    # BAR_W tipis
    assert 'width="26"' in sample_chart


def test_chart_label_nilai_untuk_relief_contrast(sample_chart):
    """Skill: light mode ada WARN contrast -> label nilai langsung (relief)."""
    assert 'class="viz-value"' in sample_chart
    assert sample_chart.count('class="viz-value"') == 8


def test_chart_nilai_yang_ditampilkan_benar(sample_chart):
    vals = re.findall(r'class="viz-value"[^>]*>([\d.]+)</text>', sample_chart)
    assert sorted(map(float, vals)) == sorted(
        [245, 245, 125, 150, 185, 180, 195, 205]
    )


def test_chart_tidak_ada_mark_di_luar_canvas(sample_chart):
    svg = re.search(r"<svg.*?</svg>", sample_chart, re.S).group(0)
    vb = list(map(float, re.search(
        r'viewBox="([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)"', svg).groups()))
    marks = re.findall(
        r'<rect x="([\d.]+)" y="([\d.]+)" width="(\d+)" height="([\d.]+)" rx="4"',
        svg,
    )
    assert marks, "harus ada bar"
    W, H = vb[2], vb[3]
    for x, y, w, h in marks:
        x, y, w, h = float(x), float(y), int(w), float(h)
        assert 0 <= x and x + w <= W
        assert 0 <= y and y + h <= H
        assert h >= 0


def test_chart_kosong_tidak_crash():
    svg = grouped_bar_chart(
        categories=[("A", "A")], series=[("X", "X")], values={},
        title="Kosong", unit="menit",
    )
    assert "<svg" in svg


def test_chart_dark_mode_pakai_palet_dark():
    cats = [("S1", "S1")]
    series = [("T01", "T01")]
    svg = grouped_bar_chart(
        categories=cats, series=series, values={("S1", "T01"): 100},
        title="Dark", unit="menit", dark=True,
    )
    # fallback hex dark harus hadir
    assert PALETTE_DARK[0] in svg
    assert "#1a1a19" in svg  # surface dark


def test_chart_css_variable_dengan_fallback_hex(sample_chart):
    """Format var(--viz-x,#hex): fallback menjamin chart tetap terbaca
    tanpa CSS variable, dan CSS variable menang bila didefinisikan."""
    assert "var(--viz-series-1,#2a78d6)" in sample_chart
    assert "var(--viz-surface,#fcfcfb)" in sample_chart


def test_chart_css_viz_css_didefinisikan():
    """VIZ_CSS mendefinisikan --viz-series-* + dark scope untuk theming."""
    from ticketing.web.charts import VIZ_CSS

    assert "--viz-series-1: #2a78d6" in VIZ_CSS
    assert "html.dark .viz-root" in VIZ_CSS
    assert "--viz-series-1: #3987e5" in VIZ_CSS
