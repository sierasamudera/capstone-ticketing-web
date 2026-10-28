"""Generator chart SVG untuk web app.

Mengikuti skill dataviz: palette kategoris 4 slot yang sudah divalidasi
(light & dark mode PASS), hue tetap per teknisi (tidak pernah diacak),
mark tipis dengan ujung dibulatani 4px, celah 2px antar bar, legend wajib
untuk >=2 series, label nilai langsung di atas bar (relief contrast), dan
tooltip per-mark.
"""

from __future__ import annotations

from typing import Optional

# Nilai dipakai sebagai *fallback* CSS variable (var(--viz-x, <hex>)).
# Saat template mendefinisikan --viz-x, chart mengikuti tema (light/dark)
# tanpa perlu di-render ulang server-side. Tanpa CSS variable, fallback
# hex memastikan chart tetap terbaca: SERIES_* dipilih lewat argumen `dark`.
SERIES_LIGHT = [
    "var(--viz-series-1,#2a78d6)",
    "var(--viz-series-2,#eb6834)",
    "var(--viz-series-3,#1baf7a)",
    "var(--viz-series-4,#eda100)",
]
SERIES_DARK = [
    "var(--viz-series-1,#3987e5)",
    "var(--viz-series-2,#d95926)",
    "var(--viz-series-3,#199e70)",
    "var(--viz-series-4,#c98500)",
]

INK = {
    "light": {
        "surface": "var(--viz-surface,#fcfcfb)",
        "primary": "var(--viz-primary,#0b0b0b)",
        "secondary": "var(--viz-secondary,#52514e)",
        "muted": "var(--viz-muted,#898781)",
        "gridline": "var(--viz-gridline,#e1e0d9)",
        "baseline": "var(--viz-baseline,#c3c2b7)",
        "border": "var(--viz-border,rgba(11,11,11,0.10))",
    },
    "dark": {
        "surface": "var(--viz-surface,#1a1a19)",
        "primary": "var(--viz-primary,#ffffff)",
        "secondary": "var(--viz-secondary,#c3c2b7)",
        "muted": "var(--viz-muted,#898781)",
        "gridline": "var(--viz-gridline,#2c2c2a)",
        "baseline": "var(--viz-baseline,#383835)",
        "border": "var(--viz-border,rgba(255,255,255,0.10))",
    },
}

GAP = 2  # celah permukaan antar mark (px)
BAR_W = 26  # lebar mark tipis
RADIUS = 4  # ujung data dibulatani


def series_color(index: int, dark: bool = False) -> str:
    palette = SERIES_DARK if dark else SERIES_LIGHT
    return palette[index % len(palette)]


def grouped_bar_chart(
    categories: list,
    series: list,
    values: dict,
    title: str,
    unit: str = "menit",
    dark: bool = False,
    height: int = 300,
    max_value: Optional[float] = None,
) -> str:
    """Grouped bar chart: kategori = skenario, series = teknisi.

    categories : list of (key, label)
    series     : list of (key, label)
    values     : {(category_key, series_key): angka}
    """
    ink = INK["dark"] if dark else INK["light"]
    palette = SERIES_DARK if dark else SERIES_LIGHT

    n_cat = len(categories)
    n_ser = len(series)
    top = 46  # ruang judul + label nilai
    bottom = 58  # ruang sumbu x + legend
    plot_h = height - top - bottom
    width = max(520, n_cat * (n_ser * (BAR_W + GAP) + GAP) + 120)
    plot_w = width - 80  # margin kiri untuk sumbu y
    x0 = 56

    vmax = max_value or max(values.values()) if values else 1
    vmax = max(vmax * 1.15, 1)

    def y(v: float) -> float:
        return top + plot_h - (v / vmax) * plot_h

    parts = [
        f'<svg viewBox="0 0 {width} {height}" class="viz-chart" '
        f'role="img" aria-label="{title}" '
        f'xmlns="http://www.w3.org/2000/svg">',
        f'<rect x="0" y="0" width="{width}" height="{height}" '
        f'fill="{ink["surface"]}"/>',
    ]

    # --- judul ---
    parts.append(
        f'<text x="{x0}" y="22" class="viz-title" fill="{ink["primary"]}">'
        f'{title}</text>'
    )

    # --- gridline + label sumbu Y (recesif) ---
    ticks = 4
    for i in range(ticks + 1):
        v = vmax * i / ticks
        yy = y(v)
        parts.append(
            f'<line x1="{x0}" y1="{yy:.1f}" x2="{x0 + plot_w}" y2="{yy:.1f}" '
            f'stroke="{ink["gridline"]}" stroke-width="1"/>'
        )
        label = f"{v:.0f}" if v >= 10 else f"{v:.1f}"
        parts.append(
            f'<text x="{x0 - 8}" y="{yy + 4:.1f}" text-anchor="end" '
            f'class="viz-axis" fill="{ink["muted"]}">{label}</text>'
        )
    parts.append(
        f'<text x="{x0 - 40}" y="{top - 10}" class="viz-axis" '
        f'fill="{ink["muted"]}">{unit}</text>'
    )

    # --- group per kategori ---
    group_w = plot_w / n_cat
    for ci, (cat_key, cat_label) in enumerate(categories):
        gx = x0 + ci * group_w
        # label kategori di sumbu X
        parts.append(
            f'<text x="{gx + group_w / 2:.1f}" y="{top + plot_h + 20}" '
            f'text-anchor="middle" class="viz-cat" fill="{ink["secondary"]}">'
            f'{cat_label}</text>'
        )
        # total kategori (label selektif: hanya headline per group)
        total = sum(values.get((cat_key, sk), 0) for _, sk in series)
        parts.append(
            f'<text x="{gx + group_w / 2:.1f}" y="{top + plot_h + 38}" '
            f'text-anchor="middle" class="viz-total" fill="{ink["muted"]}">'
            f'Σ {total:g}</text>'
        )

        bar_total = n_ser * BAR_W + (n_ser - 1) * GAP
        bx0 = gx + (group_w - bar_total) / 2
        for si, (ser_key, ser_label) in enumerate(series):
            v = values.get((cat_key, ser_key), 0)
            bx = bx0 + si * (BAR_W + GAP)
            by = y(v)
            bh = max(top + plot_h - by, 0)
            color = palette[si % len(palette)]
            tooltip = (
                f"{cat_label} · {ser_label}: {v:g} {unit} "
                f"({v / max(total, 1) * 100:.0f}% dari group)"
            )
            parts.append(
                f'<g class="viz-mark" tabindex="0" role="img" '
                f'aria-label="{tooltip}">'
                f'<title>{tooltip}</title>'
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{BAR_W}" '
                f'height="{bh:.1f}" rx="{RADIUS}" ry="{RADIUS}" '
                f'fill="{color}">'
                f'<animate attributeName="height" from="0" to="{bh:.1f}" '
                f'dur="0.4s" fill="freeze"/>'
                f'<animate attributeName="y" from="{top + plot_h}" '
                f'to="{by:.1f}" dur="0.4s" fill="freeze"/>'
                f'</rect>'
                # relief: label nilai langsung di atas mark (contrast WARN light)
                f'<text x="{bx + BAR_W / 2:.1f}" y="{by - 5:.1f}" '
                f'text-anchor="middle" class="viz-value" '
                f'fill="{ink["secondary"]}">{v:g}</text>'
                f'</g>'
            )

    # --- baseline ---
    parts.append(
        f'<line x1="{x0}" y1="{top + plot_h}" x2="{x0 + plot_w}" '
        f'y2="{top + plot_h}" stroke="{ink["baseline"]}" stroke-width="1.5"/>'
    )

    # --- legend (wajib untuk >= 2 series) ---
    lx = x0
    ly = height - 16
    for si, (ser_key, ser_label) in enumerate(series):
        color = palette[si % len(palette)]
        parts.append(
            f'<g class="viz-legend">'
            f'<rect x="{lx}" y="{ly - 9}" width="12" height="12" rx="3" '
            f'fill="{color}"/>'
            f'<text x="{lx + 17}" y="{ly + 1}" class="viz-legend-text" '
            f'fill="{ink["secondary"]}">{ser_label}</text>'
            f'</g>'
        )
        lx += 17 + len(ser_label) * 7.2 + 26

    parts.append("</svg>")
    return "".join(parts)


VIZ_CSS = """
/* Variabel chart — nilai hex adalah palette dataviz yang sudah divalidasi
   (CVD-safe). Definisi dark mengikuti .dark pada <html> (toggle Alpine). */
.viz-root {
  color-scheme: light;
  --viz-surface: #fcfcfb; --viz-primary: #0b0b0b; --viz-secondary: #52514e;
  --viz-muted: #898781; --viz-gridline: #e1e0d9; --viz-baseline: #c3c2b7;
  --viz-border: rgba(11,11,11,0.10);
  --viz-series-1: #2a78d6; --viz-series-2: #eb6834;
  --viz-series-3: #1baf7a; --viz-series-4: #eda100;
}
html.dark .viz-root {
  color-scheme: dark;
  --viz-surface: #1a1a19; --viz-primary: #ffffff; --viz-secondary: #c3c2b7;
  --viz-muted: #898781; --viz-gridline: #2c2c2a; --viz-baseline: #383835;
  --viz-border: rgba(255,255,255,0.10);
  --viz-series-1: #3987e5; --viz-series-2: #d95926;
  --viz-series-3: #199e70; --viz-series-4: #c98500;
}
.viz-chart { width: 100%; height: auto; display: block; border: 1px solid var(--viz-border); border-radius: 8px; }
.viz-title { font: 600 14px/1.2 system-ui, -apple-system, "Segoe UI", sans-serif; }
.viz-axis { font: 11px/1 system-ui, sans-serif; }
.viz-cat { font: 600 12px/1.2 system-ui, sans-serif; }
.viz-total { font: 10px/1 system-ui, sans-serif; }
.viz-value { font: 10px/1 system-ui, sans-serif; }
.viz-legend-text { font: 12px/1.2 system-ui, sans-serif; }
.viz-mark { cursor: pointer; }
.viz-mark:hover rect, .viz-mark:focus-visible rect { stroke: var(--viz-primary); stroke-width: 1.5; }
"""
