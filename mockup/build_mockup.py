"""Render mockup statis multi-role (hybrid, siap dijinjakan ke Flask).

Mockup = HTML murni, bisa dibuka lewat ``file://`` tanpa server. Angka & chart
diambil dari mesin simulasi yang sudah divalidasi terhadap Excel, jadi mockup
tidak pernah menyajikan nilai fiktif. Autentikasi disimulasikan di localStorage;
saat dijinjakan ke Flask, ``_auth.js`` diganti decorator ``@role_required`` dan
link ``../admin/dashboard.html`` diganti ``url_for('admin.dashboard')``.

Jalankan::

    python mockup/build_mockup.py
"""

from __future__ import annotations

import html
import json
import os
import sys

# Izinkan dijalankan dari mana saja: root proyek = parent dir mockup/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ticketing import __version__
from ticketing.models import CATEGORIES
from ticketing.simulation import Simulation
from ticketing.web.charts import VIZ_CSS, grouped_bar_chart

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Skenario yang dipakai sebagai "kondisi operasional" di halaman teknisi/admin.
# S2 = Gap menit terkecil (paling merata) menurut mesin.
OPERATIONAL = "S2"

# ---------------------------------------------------------------------------
# Users demo — role menentukan halaman tujuan login.
# MOCKUP: tidak ada autentikasi nyata. Password apa pun diterima.
# ---------------------------------------------------------------------------
USERS = [
    {"username": "admin", "nama": "Admin Helpdesk", "role": "admin", "tech_id": None},
    {"username": "t01", "nama": "Teknisi A", "role": "teknisi", "tech_id": "T01"},
    {"username": "pelapor", "nama": "Mahasiswa Contoh", "role": "pelapor", "tech_id": None},
]

ROLE_HOME = {
    "admin": "admin/dashboard.html",
    "teknisi": "teknisi/dashboard.html",
    "pelapor": "pelapor/dashboard.html",
}

NAV_PER_ROLE = {
    "pelapor": [
        ("pelapor/dashboard.html", "Tiket Saya"),
        ("pelapor/tiket-baru.html", "Buat Tiket"),
    ],
    "teknisi": [
        ("teknisi/dashboard.html", "Tiket Ditugaskan"),
        ("teknisi/minta-bantuan.html", "Minta Bantuan"),
    ],
    "admin": [
        ("admin/dashboard.html", "Monitoring Beban"),
        ("admin/simulasi.html", "Simulasi Skenario"),
        ("admin/tiket.html", "Semua Tiket"),
        ("admin/tiket-baru.html", "Buat Tiket TK-"),
        ("admin/teknisi.html", "Manajemen Teknisi"),
    ],
}

TAILWIND_CONFIG = """
  tailwind.config = {
    darkMode: 'class',
    theme: { extend: {
      fontFamily: { sans: ['system-ui','-apple-system','"Segoe UI"','sans-serif'],
                    mono: ['ui-monospace','SFMono-Regular','Menlo','Consolas','monospace'] },
      colors: {
        canvas: { DEFAULT: '#f9f9f7', dark: '#0d0d0d' },
        panel:  { DEFAULT: '#fcfcfb', dark: '#1a1a19' },
        panel2: { DEFAULT: '#ffffff', dark: '#232321' },
        ink:    { DEFAULT: '#0b0b0b', dark: '#ffffff' },
        ink2:   { DEFAULT: '#52514e', dark: '#c3c2b7' },
        muted:  { DEFAULT: '#898781', dark: '#898781' },
        line:   { DEFAULT: '#e1e0d9', dark: '#2c2c2a' },
        accent: { DEFAULT: '#2a78d6', dark: '#3987e5' },
        good:   { DEFAULT: '#0ca30c', dark: '#0ca30c' },
        warn:   { DEFAULT: '#b26a00', dark: '#eda100' },
        danger: { DEFAULT: '#d03b3b', dark: '#e66767' },
      },
    } },
  };
"""

CSS_EXTRA = """
[x-cloak] { display: none !important; }
.tbl { width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; font-size:.8125rem; }
.tbl th { padding:.375rem .5rem; text-align:left; font-weight:600; white-space:nowrap;
          color:#52514e; border-bottom:1px solid #e1e0d9; }
html.dark .tbl th { color:#c3c2b7; border-color:#2c2c2a; }
.tbl td { padding:.375rem .5rem; border-bottom:1px solid #e1e0d9; }
html.dark .tbl td { border-color:#2c2c2a; }
.tbl td.num, .tbl th.num { text-align:right; }
.tbl tbody tr:hover td { background:#ffffff; }
html.dark .tbl tbody tr:hover td { background:#232321; }
"""

# Script path (relatif terhadap halaman) + guard. APP_ROOT HARUS didefinisikan
# sebelum _auth.js dimuat karena requireRole memakainya untuk redirect.
GUARD_SNIPPET = """
<script>const APP_ROOT = "{root}";</script>
<script src="{root}_auth.js"></script>
<script src="{root}_data.js"></script>
<script>requireRole({roles});</script>
"""

_NO_GUARD = """
<script>const APP_ROOT = "{root}";</script>
<script src="{root}_auth.js"></script>
<script src="{root}_data.js"></script>
"""

# Root mockup tidak punya halaman "depan" sendiri — sistem dimulai dari login.
# Meta refresh (bukan JS) supaya jalan walau JavaScript dimatikan, dan tetap
# valid saat dibuka via file://. Netlify memakai redirect 302 di netlify.toml;
# file ini menangani host statis tanpa konfigurasi redirect (file://, GitHub
# Pages, Surge, dsb).
INDEX_REDIRECT = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<title>Sistem Ticketing</title>
<meta http-equiv="refresh" content="0; url=login.html">
<link rel="canonical" href="login.html">
</head>
<body>
<p>Mengalihkan ke halaman masuk&hellip; <a href="login.html">Lanjut</a>.</p>
</body>
</html>
"""

AUTH_JS = """/* Mockup auth — disimulasikan di localStorage.
 * Saat dijinjakan ke Flask: hapus file ini, ganti requireRole dengan
 * decorator @role_required('admin') di blueprint. */
const SESSION_KEY = 'mockup_session';

function login(username, role) {
  localStorage.setItem(SESSION_KEY, JSON.stringify({username, role, ts: Date.now()}));
}
function session() {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY)); }
  catch (e) { return null; }
}
function requireRole() {
  var roles = Array.prototype.slice.call(arguments);
  var s = session();
  if (!s) { location.replace(APP_ROOT + 'login.html'); return; }
  if (roles.length && roles.indexOf(s.role) === -1) {
    location.replace(APP_ROOT + '403.html');
  }
}
function logout() {
  localStorage.removeItem(SESSION_KEY);
  location.replace(APP_ROOT + 'login.html');
}
function currentUser() {
  var s = session();
  return s ? s.username : null;
}

/* Status alur kerja tiket (Open -> In Progress -> Resolved).
 * USULAN: siklus ini tidak ada di mesin Excel; default Open, perubahan
 * disimpan client-side hanya untuk demo. */
var STATUS_KEY = 'mockup_ticket_status';
function ticketStatus(id, fallback) {
  try {
    var all = JSON.parse(localStorage.getItem(STATUS_KEY) || '{}');
    return all[id] || fallback || 'Open';
  } catch (e) { return fallback || 'Open'; }
}
function setTicketStatus(id, status) {
  var all = {};
  try { all = JSON.parse(localStorage.getItem(STATUS_KEY) || '{}'); } catch (e) {}
  all[id] = status;
  localStorage.setItem(STATUS_KEY, JSON.stringify(all));
}

/* Satu sumber status untuk SEMUA badge di semua halaman.
 *
 * Setiap badge status tiket di-render dengan atribut
 *   <span data-status data-ticket-id="T-001" data-default="Open">
 * dan fungsi ini mengganti isinya dengan ticketStatus(id) saat halaman dimuat.
 * Inilah yang membuat status konsisten: teknisi ubah status -> pelapor &
 * admin melihat nilai terbaru tanpa restart (localStorage dibaca tiap load).
 * Untuk no-JS, generator sudah menulis badge default di dalam span. */
var STATUS_BADGE_CLASSES = {
  'Open': 'bg-warn/10 text-warn dark:text-warn-dark',
  'In Progress': 'bg-accent/10 text-accent dark:text-accent-dark',
  'Resolved': 'bg-good/10 text-good dark:text-good-dark'
};
function statusBadgeHTML(s) {
  var cls = STATUS_BADGE_CLASSES[s] || 'bg-line/40 text-ink2 dark:text-ink2-dark';
  return '<span class="inline-block px-2 py-0.5 rounded-full text-[11px] ' + cls + '">' + s + '</span>';
}
function hydrateStatusBadges() {
  var nodes = document.querySelectorAll('[data-status][data-ticket-id]');
  for (var i = 0; i < nodes.length; i++) {
    var el = nodes[i];
    el.innerHTML = statusBadgeHTML(ticketStatus(el.getAttribute('data-ticket-id'),
                                                el.getAttribute('data-default') || 'Open'));
  }
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', hydrateStatusBadges);
} else {
  hydrateStatusBadges();
}

/* KPI "Sedang dikerjakan" dll. dihitung ulang dari localStorage saat halaman
 * dimuat — tidak di-cache dari saat server start. Markup:
 *   <span data-count-status="In Progress" data-count-tickets="T-001,T-008,...">
 * Hitung hanya tiket yang listed yang statusnya cocok. */
function hydrateStatusCounts() {
  var nodes = document.querySelectorAll('[data-count-status]');
  for (var i = 0; i < nodes.length; i++) {
    var el = nodes[i];
    var match = el.getAttribute('data-count-status');
    var ids = (el.getAttribute('data-count-tickets') || '').split(',');
    var n = 0;
    for (var j = 0; j < ids.length; j++) {
      var id = ids[j].trim();
      if (id && ticketStatus(id, 'Open') === match) n++;
    }
    el.textContent = String(n);
  }
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', hydrateStatusCounts);
} else {
  hydrateStatusCounts();
}
"""


def esc(text) -> str:
    return html.escape(str(text))


def root_prefix(depth: int) -> str:
    """Path relatif dari halaman ke root mockup. depth=0 -> './', 1 -> '../'."""
    return "./" if depth == 0 else "../" * depth


def prio_badge(p: str) -> str:
    cls = {
        "High": "bg-danger/10 text-danger dark:text-danger-dark",
        "Medium": "bg-accent/10 text-accent dark:text-accent-dark",
        "Low": "bg-good/10 text-good dark:text-good-dark",
    }.get(p, "bg-line/40 text-ink2 dark:text-ink2-dark")
    return f'<span class="inline-block px-2 py-0.5 rounded-full text-[11px] {cls}">{esc(p)}</span>'


STATUS_CLASSES = {
    "Open": "bg-warn/10 text-warn dark:text-warn-dark",
    "In Progress": "bg-accent/10 text-accent dark:text-accent-dark",
    "Resolved": "bg-good/10 text-good dark:text-good-dark",
    "Available": "bg-good/10 text-good dark:text-good-dark",
    "Busy": "bg-danger/10 text-danger dark:text-danger-dark",
}


def status_badge(s: str) -> str:
    cls = STATUS_CLASSES.get(s, "bg-line/40 text-ink2 dark:text-ink2-dark")
    return f'<span class="inline-block px-2 py-0.5 rounded-full text-[11px] {cls}">{esc(s)}</span>'


def ticket_status_badge(ticket_id: str, default: str = "Open") -> str:
    """Badge status tiket yang hidrat dari localStorage saat halaman dimuat.

    Mengikuti satu sumber data: generator menulis badge default (agar tetap
    terbaca tanpa JS), lalu hydrateStatusBadges() di _auth.js menimpanya
    dengan ticketStatus(id) — nilai terbaru dari update teknisi.
    """
    return (
        '<span data-status data-ticket-id="{id}" data-default="{d}">'
        "{inner}</span>"
    ).format(id=esc(ticket_id), d=esc(default), inner=status_badge(default))


def live_status_count(label: str, tickets: list, match: str,
                      sub: str = "") -> str:
    """KPI tile yang nilainya dihitung ulang dari localStorage tiap page load.

    `tickets` = list dict tiket; hanya tiket dengan id tercantam yang dihitung.
    Generator menulis nilai awal (benar untuk dataset default) sebagai fallback
    tanpa-JS, lalu hydrateStatusCounts() menimpanya.
    """
    ids = ",".join(t["id"] for t in tickets)
    initial = sum(1 for t in tickets if t["lifecycle"] == match)
    value = (
        '<span data-count-status="{m}" data-count-tickets="{ids}">{n}</span>'
    ).format(m=esc(match), ids=esc(ids), n=initial)
    return kpi_tile(label, value, sub)


def kpi_tile(label: str, value: str, sub: str = "") -> str:
    return (
        '<div class="rounded-xl border border-line dark:border-line-dark '
        'bg-panel2 dark:bg-panel2-dark p-4">'
        f'<div class="text-xs text-muted dark:text-muted-dark">{esc(label)}</div>'
        f'<div class="mt-1 text-2xl font-semibold tabular-nums">{value}</div>'
        f'{f"<div class=\"mt-0.5 text-[11px] text-muted dark:text-muted-dark\">{sub}</div>" if sub else ""}'
        "</div>"
    )


def shell(title: str, role: str, depth: int, body: str, active: str = "",
          guard: bool = True) -> str:
    """Shell bersama: head, guard role, nav per-role, footer.

    depth = kedalaman folder halaman (0 = root mockup).
    active = href nav yang disorot.
    """
    root = root_prefix(depth)
    roles = f"'{role}'" if guard else ""
    nav_items = []
    for href, label in NAV_PER_ROLE.get(role, []):
        base = (
            "bg-accent dark:bg-accent-dark text-white border-accent dark:border-accent-dark"
            if href == active
            else "border-line dark:border-line-dark text-ink2 dark:text-ink2-dark "
                 "hover:bg-panel2 dark:hover:bg-panel2-dark"
        )
        nav_items.append(
            f'<a href="{root}{href}" class="px-3 py-1.5 rounded-lg text-sm border transition-colors {base}">{esc(label)}</a>'
        )

    head = f"""<!DOCTYPE html>
<html lang="id" class="h-full">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<script>(function(){{var t=localStorage.getItem('theme');if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme: dark)').matches)){{document.documentElement.classList.add('dark');}}}})();</script>
<script src="https://cdn.tailwindcss.com/3.4.17"></script>
<script>tailwind.config = {TAILWIND_CONFIG.strip()};</script>
<style>
{VIZ_CSS}
{CSS_EXTRA}
</style>
{GUARD_SNIPPET.format(root=root, roles=roles) if guard else _NO_GUARD.format(root=root)}
<script defer src="https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.14.1/dist/cdn.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js"></script>
</head>
<body class="h-full bg-canvas dark:bg-canvas-dark text-ink dark:text-ink-dark font-sans antialiased p-4 sm:p-6 lg:p-8">
<div class="max-w-6xl mx-auto">
<header class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-2">
  <div class="flex items-center gap-3">
    <h1 class="text-xl font-bold tracking-tight">{esc(title)}</h1>
    <span class="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide
                 bg-accent/15 text-accent dark:text-accent-dark border border-accent/30">MOCKUP</span>
  </div>
  <div class="flex items-center gap-3">
    <span class="inline-flex items-center px-3 py-1 rounded-full border border-line dark:border-line-dark text-xs text-ink2 dark:text-ink2-dark">
      <span id="nav-user">{esc(role and USERS[0]["nama"] or "belum login")}</span>{(' · <strong>' + esc(role) + '</strong>') if role else ''}
    </span>
    <button type="button" onclick="logout()"
            class="px-3 py-1.5 rounded-lg text-sm border border-line dark:border-line-dark text-ink2 dark:text-ink2-dark hover:bg-panel2 dark:hover:bg-panel2-dark transition-colors"
            {'' if role else 'hidden'}>
      Logout
    </button>
    <button type="button"
            x-data="{{ dark: document.documentElement.classList.contains('dark') }}"
            @click="dark = !dark; document.documentElement.classList.toggle('dark', dark); localStorage.setItem('theme', dark ? 'dark' : 'light')"
            :aria-pressed="dark.toString()" aria-label="Ganti tema terang/gelap" title="Ganti tema"
            class="inline-flex items-center justify-center w-10 h-10 rounded-lg border border-line dark:border-line-dark bg-panel dark:bg-panel-dark hover:bg-panel2 dark:hover:bg-panel2-dark transition-colors">
      <svg x-show="!dark" class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path stroke-linecap="round" d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5M17.5 17.5 19 19m0-14-1.5 1.5M6.5 17.5 5 19"/></svg>
      <svg x-show="dark" x-cloak class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path stroke-linecap="round" d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>
    </button>
  </div>
</header>
<nav class="flex flex-wrap gap-2 mb-4">
  {''.join(nav_items)}
</nav>
<p class="text-xs text-muted dark:text-muted-dark mb-6">
  Data asli dari mesin simulasi (identik dengan Excel, 42/42 cek). Status alur
  kerja tiket (Open → In Progress → Resolved) adalah <strong>usulan</strong> —
  belum ada di mesin Excel.
</p>
{body}
<footer class="mt-10 text-xs text-muted dark:text-muted-dark">
  v{__version__} · Mockup statis tanpa server. Indikator pemerataan &amp; skenario S4
  adalah usulan yang perlu validasi dosen.
</footer>
</div>
<script>
  // isi chip user dari session
  (function() {{
    var s = session();
    var el = document.getElementById('nav-user');
    if (s && el) el.textContent = s.username;
  }})();
</script>
</body>
</html>
"""
    return head


# ===========================================================================
# Halaman auth (root, tanpa guard)
# ===========================================================================


def page_login(depth: int = 0) -> str:
    quick = "\n".join(
        f"""<button type="button" onclick="quickLogin('{u["username"]}')"
                class="flex-1 min-w-[140px] rounded-lg border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark hover:bg-accent/5 hover:border-accent/40 px-3 py-2.5 text-left transition-colors">
          <div class="text-sm font-semibold">{esc(u["nama"])}</div>
          <div class="text-[11px] text-muted dark:text-muted-dark">@{esc(u["username"])} · {esc(u["role"])}</div>
        </button>"""
        for u in USERS
    )
    body = f"""
<div class="max-w-md mx-auto">
  <div class="rounded-2xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-6 shadow-sm">
    <h2 class="text-lg font-bold">Masuk</h2>
    <p class="mt-1 text-sm text-ink2 dark:text-ink2-dark">
      Satu halaman untuk semua role. Setelah masuk, Anda dialihkan otomatis
      sesuai role.
    </p>
    <form x-data="loginForm()" @submit.prevent="submit()"
          class="mt-5 space-y-4">
      <div>
        <label for="username" class="block text-xs text-muted dark:text-muted-dark mb-1">Username</label>
        <input id="username" type="text" x-model="username" autocomplete="off" required
               class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
      </div>
      <div>
        <label for="password" class="block text-xs text-muted dark:text-muted-dark mb-1">Password</label>
        <input id="password" type="password" x-model="password" placeholder="mockup — apa pun diterima" required
               class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
      </div>
      <p x-show="error" x-cloak class="text-sm text-danger dark:text-danger-dark" x-text="error"></p>
      <button type="submit"
              class="w-full rounded-md bg-accent dark:bg-accent-dark hover:brightness-110 text-white px-4 py-2.5 text-sm font-medium transition">
        Masuk
      </button>
    </form>

    <div class="mt-6 pt-5 border-t border-line dark:border-line-dark">
      <div class="text-xs font-semibold text-ink2 dark:text-ink2-dark mb-2">Login cepat (demo)</div>
      <div class="flex flex-wrap gap-2">{quick}</div>
    </div>

    <p class="mt-6 text-center text-sm text-ink2 dark:text-ink2-dark">
      Belum punya akun?
      <a href="{root_prefix(depth)}register.html" class="font-medium text-accent dark:text-accent-dark hover:underline">Daftar sebagai pelapor</a>
    </p>
  </div>
  <p class="mt-4 text-center text-xs text-muted dark:text-muted-dark">
    MOCKUP — tidak ada autentikasi nyata. Username menentukan role &amp; halaman tujuan.
  </p>
</div>
<script>
function quickLogin(username) {{
  var u = DB.users.find(function (x) {{ return x.username === username; }});
  if (!u) return;
  login(u.username, u.role);
  location.replace(APP_ROOT + ROLE_HOME[u.role]);
}}
function doLogin(username, password, setError) {{
  var u = DB.users.find(function (x) {{ return x.username === username; }});
  if (!u) {{ setError('Username tidak ditemukan'); return; }}
  login(u.username, u.role);
  location.replace(APP_ROOT + ROLE_HOME[u.role]);
}}
document.addEventListener('alpine:init', function () {{
  Alpine.data('loginForm', function () {{
    return {{
      username: '', password: '', error: '',
      submit: function () {{
        doLogin(this.username, this.password, (function (self) {{
          return function (msg) {{ self.error = msg; }};
        }})(this));
      }}
    }};
  }});
}});
</script>
"""
    return body


def page_register(depth: int = 0) -> str:
    body = f"""
<div class="max-w-md mx-auto">
  <div class="rounded-2xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-6 shadow-sm">
    <h2 class="text-lg font-bold">Daftar Pelapor</h2>
    <p class="mt-1 text-sm text-ink2 dark:text-ink2-dark">
      Pendaftaran terbuka hanya untuk <strong>pelapor</strong>. Akun teknisi
      dan admin dibuat oleh admin lewat menu Manajemen Teknisi, supaya daftar
      teknisi tetap terkontrol — mesin distribusi beban membutuhkan daftar
      teknisi aktif yang valid.
    </p>
    <form x-data="{{ nama: '', username: '', done: false }}" @submit.prevent="done = true" class="mt-5 space-y-4">
      <div>
        <label for="nama" class="block text-xs text-muted dark:text-muted-dark mb-1">Nama Lengkap</label>
        <input id="nama" type="text" x-model="nama" required
               class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
      </div>
      <div>
        <label for="username" class="block text-xs text-muted dark:text-muted-dark mb-1">Username</label>
        <input id="username" type="text" x-model="username" required
               class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
      </div>
      <div>
        <label for="password" class="block text-xs text-muted dark:text-muted-dark mb-1">Password</label>
        <input id="password" type="password" required
               class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
      </div>
      <button type="submit"
              class="w-full rounded-md bg-accent dark:bg-accent-dark hover:brightness-110 text-white px-4 py-2.5 text-sm font-medium transition">
        Daftar
      </button>
      <div x-show="done" x-cloak class="px-4 py-2.5 rounded-lg border border-good/30 bg-good/10 text-good dark:text-good-dark text-sm">
        Mockup: akun pelapor tidak benar-benar disimpan. Implementasi nyata
        menyimpan ke <code>data/users.json</code> dan langsung masuk.
      </div>
    </form>
    <p class="mt-6 text-center text-sm text-ink2 dark:text-ink2-dark">
      Sudah punya akun?
      <a href="{root_prefix(depth)}login.html" class="font-medium text-accent dark:text-accent-dark hover:underline">Masuk</a>
    </p>
  </div>
</div>
"""
    return body


def page_403(depth: int = 0) -> str:
    root = root_prefix(depth)
    body = f"""
<div class="max-w-md mx-auto text-center py-12">
  <div class="text-5xl font-bold text-muted dark:text-muted-dark tabular-nums">403</div>
  <h2 class="mt-3 text-lg font-bold">Akses Ditolak</h2>
  <p class="mt-2 text-sm text-ink2 dark:text-ink2-dark">
    Halaman ini hanya untuk role tertentu. Anda masuk sebagai
    <strong id="role-now">…</strong>.
  </p>
  <div class="mt-6 flex flex-wrap justify-center gap-2">
    <a id="home-link" href="#"
       class="px-4 py-2 rounded-md bg-accent dark:bg-accent-dark text-white text-sm font-medium">
      Ke dashboard saya
    </a>
    <button type="button" onclick="logout()"
            class="px-4 py-2 rounded-md border border-line dark:border-line-dark text-ink2 dark:text-ink2-dark text-sm font-medium">
      Ganti akun
    </button>
  </div>
</div>
<script>
(function () {{
  var s = session();
  var el = document.getElementById('role-now');
  var link = document.getElementById('home-link');
  if (s && el) el.textContent = s.role;
  if (s && link) link.href = APP_ROOT + ROLE_HOME[s.role];
  else if (link) link.href = APP_ROOT + 'login.html';
}})();
</script>
"""
    return body


def page_404(depth: int = 0) -> str:
    root = root_prefix(depth)
    body = f"""
<div class="max-w-md mx-auto text-center py-12">
  <div class="text-5xl font-bold text-muted dark:text-muted-dark tabular-nums">404</div>
  <h2 class="mt-3 text-lg font-bold">Halaman Tidak Ditemukan</h2>
  <p class="mt-2 text-sm text-ink2 dark:text-ink2-dark">
    URL yang Anda buka tidak ada di sistem.
  </p>
  <a href="{root}login.html"
     class="mt-6 inline-block px-4 py-2 rounded-md bg-accent dark:bg-accent-dark text-white text-sm font-medium">
    Ke halaman masuk
  </a>
</div>
"""
    return body


# ===========================================================================
# Halaman admin
# ===========================================================================


def page_admin_dashboard(depth: int, data: dict) -> str:
    s2 = data["scen"][OPERATIONAL]
    techs = data["techs"]
    ideal = s2["ideal"]

    rows = []
    max_dur = max(l["dur"] for l in s2["loads"].values())
    for t in techs:
        load = s2["loads"][t["id"]]
        pct = load["dur"] / max_dur * 100
        over = load["dur"] > ideal
        bar = "bg-danger dark:bg-danger-dark" if over else "bg-accent dark:bg-accent-dark"
        rows.append(
            f'<tr><td class="font-mono font-semibold">{t["id"]}</td><td>{esc(t["name"])}</td>'
            f'<td>{status_badge(t["status"])}</td>'
            f'<td class="num">{load["dur"]} menit</td>'
            f'<td class="num">{load["w"]} pt-min</td>'
            f'<td class="num">{load["n"]}</td>'
            f'<td class="num {"font-semibold text-danger dark:text-danger-dark" if over else ""}">'
            f'{"+" if load["dur"] - ideal >= 0 else ""}{load["dur"] - ideal:.0f}</td></tr>'
            f'<tr><td colspan="7" class="!py-1.5 !border-b-0">'
            f'<div class="h-2 rounded-full bg-line dark:bg-line-dark overflow-hidden">'
            f'<div class="h-full rounded-full {bar}" style="width:{pct:.1f}%"></div>'
            f'</div></td></tr>'
        )

    recent = "\n".join(
        f'<tr><td class="font-mono font-semibold">{esc(t["id"])}</td>'
        f'<td class="font-mono">{esc(t["time"])}</td><td>{esc(t["category"])}</td>'
        f'<td>{esc(t["detail"])}</td><td>{prio_badge(t["priority"])}</td>'
        f'<td class="num">{t["duration"]}</td></tr>'
        for t in data["recent"]
    )

    body = f"""
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
  {kpi_tile("Beban ideal per teknisi", f"{ideal:g} menit", f"total durasi {s2['dur']} ÷ {len(techs)} teknisi")}
  {kpi_tile("Total tiket hari ini", str(s2["total"]), f'{s2["cases"]} kasus unik (TK- tidak dihitung)')}
  {kpi_tile("Gap terkecil", f'{s2["gap"]} menit', f"{OPERATIONAL} Cumulative — paling merata")}
  {kpi_tile("Teknisi tersedia", f'{sum(1 for t in techs if t["status"] == "Available")}/{len(techs)}', "status awal shift 08:00")}
</div>

<h2 class="text-base font-semibold mt-8 mb-3">Status Tiket</h2>
<div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
  {live_status_count("Open", data["tickets"], "Open", "menunggu dikerjakan")}
  {live_status_count("In Progress", data["tickets"], "In Progress", "sedang dikerjakan teknisi")}
  {live_status_count("Resolved", data["tickets"], "Resolved", "selesai")}
</div>

<h2 class="text-base font-semibold mt-8 mb-3">Beban Kerja per Teknisi</h2>
<div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4 viz-root">
  {data["chart_durasi"]}
  <p class="mt-2 text-xs text-muted dark:text-muted-dark">
    Beban <strong>{OPERATIONAL} Cumulative</strong> dipakai sebagai kondisi monitor
    karena Gap-nya paling kecil. Bar melebihi beban ideal ditandai merah di tabel.
  </p>
</div>

<h2 class="text-base font-semibold mt-8 mb-3">Status Teknisi</h2>
<div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
  <div class="overflow-x-auto">
  <table class="tbl">
    <thead><tr>
      <th>ID</th><th>Nama</th><th>Status</th>
      <th class="num">Beban (menit)</th><th class="num">Beban Berbobot</th>
      <th class="num">Tiket</th><th class="num">Selisih vs Ideal</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  </div>
</div>

<h2 class="text-base font-semibold mt-8 mb-3">Tiket Masuk Terbaru</h2>
<div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
  <div class="overflow-x-auto">
  <table class="tbl">
    <thead><tr><th>ID</th><th>Waktu</th><th>Kategori</th><th>Detail</th><th>Prioritas</th><th class="num">Durasi</th></tr></thead>
    <tbody>{recent}</tbody>
  </table>
  </div>
  <p class="mt-3"><a href="{root_prefix(depth)}admin/tiket.html" class="text-sm font-medium text-accent dark:text-accent-dark hover:underline">Lihat semua tiket →</a></p>
</div>
"""
    return shell("Dashboard Monitoring Beban Kerja", "admin", depth, body,
                 active="admin/dashboard.html")


def page_admin_simulasi(depth: int, data: dict) -> str:
    scen = data["scen"]
    keys = list(scen)
    best_gap = data["best_gap"]
    best_gapw = data["best_gapw"]

    tabs = "\n".join(
        f'<button type="button" @click="sel = \'{k}\'" '
        f':class="sel === \'{k}\' ? \'bg-accent dark:bg-accent-dark text-white border-accent dark:border-accent-dark\' : \'border-line dark:border-line-dark text-ink2 dark:text-ink2-dark hover:bg-panel2 dark:hover:bg-panel2-dark\'"'
        f' class="px-3.5 py-1.5 rounded-lg text-sm border transition-colors">{esc(scen[k]["name"])}</button>'
        for k in keys
    )

    cards = "\n".join(
        f'<div x-show="sel === \'{k}\'" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">'
        + "".join(
            f'<div class="rounded-lg border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark p-3">'
            f'<div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">{lbl}</div>'
            f'<div class="mt-1 text-lg font-semibold tabular-nums {extra}">{val}</div></div>'
            for lbl, val, extra in (
                ("Max", f'{scen[k]["max"]} m', ""),
                ("Min", f'{scen[k]["min"]} m', ""),
                ("Gap", f'{scen[k]["gap"]} m', "text-accent dark:text-accent-dark"),
                ("Min/Max", f'{scen[k]["balance"]:.4f}', ""),
                ("Std Dev", f'{scen[k]["stdev"]:.2f}', ""),
                ("Jain’s", f'{scen[k]["jains"]:.4f}', ""),
            )
        )
        + "</div>"
        for k in keys
    )

    rules = "\n".join(
        f'<div x-show="sel === \'{k}\'" x-cloak class="mt-3 text-sm text-ink2 dark:text-ink2-dark">'
        f'<strong class="text-ink dark:text-ink-dark">Aturan:</strong> {esc(scen[k]["rule"])}'
        f' — {esc(scen[k]["purpose"])}'
        + (' <span class="inline-block ml-1 px-2 py-0.5 rounded-full text-[10px] bg-good/10 text-good dark:text-good-dark">Gap terkecil</span>' if k == best_gap else "")
        + (' <span class="inline-block ml-1 px-2 py-0.5 rounded-full text-[10px] bg-accent/10 text-accent dark:text-accent-dark">Gap berbobot terkecil</span>' if k == best_gapw else "")
        + "</div>"
        for k in keys
    )

    rows = "\n".join(
        f'<tr class="{"bg-accent/5" if k == best_gap else ""}">'
        f'<td class="font-semibold">{esc(scen[k]["name"])}</td>'
        f'<td class="text-xs text-muted dark:text-muted-dark">{esc(scen[k]["rule"])}</td>'
        f'<td class="num">{scen[k]["max"]}</td><td class="num">{scen[k]["min"]}</td>'
        f'<td class="num font-semibold">{scen[k]["gap"]}</td>'
        f'<td class="num">{scen[k]["balance"]:.4f}</td>'
        f'<td class="num">{scen[k]["stdev"]:.2f}</td>'
        f'<td class="num">{scen[k]["jains"]:.4f}</td>'
        f'<td class="num">{scen[k]["gapw"]}</td>'
        f'<td class="num">{scen[k]["jainsw"]:.4f}</td>'
        f'<td class="num">{scen[k]["avgw"]:.2f}</td>'
        f'<td class="num">{scen[k]["maxw"]}</td>'
        f'<td class="font-mono">{scen[k]["last"]}</td></tr>'
        for k in keys
    )

    body = f"""
<div x-data="{{ sel: '{best_gap}' }}" class="space-y-6">
  <div>
    <h2 class="text-base font-semibold mb-3">Pilih Skenario</h2>
    <div class="flex flex-wrap gap-2">{tabs}</div>
    {cards}
    {rules}
  </div>

  <div>
    <h2 class="text-base font-semibold mt-8 mb-3">Grafik Beban per Teknisi (semua skenario)</h2>
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4 viz-root">
      {data["chart_durasi"]}
    </div>
    <div class="mt-4 rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4 viz-root">
      {data["chart_weighted"]}
    </div>
  </div>

  <div>
    <h2 class="text-base font-semibold mt-8 mb-3">Perbandingan Indikator</h2>
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
      <div class="overflow-x-auto">
      <table class="tbl">
        <thead><tr>
          <th>Skenario</th><th>Aturan</th>
          <th class="num">Max</th><th class="num">Min</th><th class="num">Gap</th>
          <th class="num">Min/Max</th><th class="num">Std Dev</th><th class="num">Jain's</th>
          <th class="num">Gap Berbobot</th><th class="num">Jain's Berbobot</th>
          <th class="num">Tunggu avg</th><th class="num">Tunggu max</th><th>Selesai</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
      </div>
      <p class="mt-3 text-xs text-muted dark:text-muted-dark">
        Baris <span class="text-accent dark:text-accent-dark">disorot</span> = Gap menit terkecil.
        Jain's Fairness Index = (Σx)² / (n·Σx²); 1 = sangat merata.
      </p>
    </div>
  </div>
</div>
"""
    return shell("Simulasi Skenario", "admin", depth, body,
                 active="admin/simulasi.html")


def page_admin_tiket(depth: int, data: dict) -> str:
    tickets = data["tickets"]
    tech_opts = "\n".join(f'<option value="{t["id"]}">{t["id"]} {esc(t["name"])}</option>'
                          for t in data["techs"])
    rows = "\n".join(
        f'<tr x-show="(f.status === \'\' || ticketStatus(\'{esc(t["id"])}\', \'Open\') === f.status)'
        f' && (f.kategori === \'\' || $el.dataset.kategori === f.kategori)'
        f' && (f.teknisi === \'\' || $el.dataset.teknisi === f.teknisi)'
        f' && (f.type === \'\' || $el.dataset.type === f.type)"'
        f' data-kategori="{esc(t["category"])}" data-teknisi="{esc(t["assigned_tech"] or "")}"'
        f' data-type="{esc(t["ticket_type"])}">'
        f'<td class="font-mono font-semibold">{esc(t["id"])}</td>'
        f'<td>{esc(t["ticket_type"])}</td>'
        f'<td class="font-mono">{esc(t["time"])}</td>'
        f'<td>{esc(t["category"])}</td><td class="max-w-[200px] truncate" title="{esc(t["detail"])}">{esc(t["detail"])}</td>'
        f'<td>{prio_badge(t["priority"])}</td>'
        f'<td class="font-mono">{esc(t["assigned_tech"] or "—")}</td>'
        f'<td>{ticket_status_badge(t["id"], t["lifecycle"])}</td>'
        f'<td><a href="{root_prefix(depth)}admin/tiket/{esc(t["id"])}.html" class="text-accent dark:text-accent-dark hover:underline">detail</a></td>'
        f'</tr>'
        for t in tickets
    )
    body = f"""
<div x-data="{{ f: {{ status: '', kategori: '', teknisi: '', type: '' }} }}" class="space-y-4">
  <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
    <div class="flex flex-wrap gap-x-4 gap-y-3 items-end">
      <div class="min-w-[140px]">
        <label class="block text-xs text-muted dark:text-muted-dark mb-1">Status (usulan)</label>
        <select x-model="f.status" class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          <option value="">Semua</option><option>Open</option><option>In Progress</option><option>Resolved</option>
        </select>
      </div>
      <div class="min-w-[150px]">
        <label class="block text-xs text-muted dark:text-muted-dark mb-1">Kategori</label>
        <select x-model="f.kategori" class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          <option value="">Semua</option>
          {''.join(f'<option>{esc(c)}</option>' for c in CATEGORIES)}
        </select>
      </div>
      <div class="min-w-[140px]">
        <label class="block text-xs text-muted dark:text-muted-dark mb-1">Teknisi</label>
        <select x-model="f.teknisi" class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          <option value="">Semua</option>{tech_opts}
        </select>
      </div>
      <div class="min-w-[150px]">
        <label class="block text-xs text-muted dark:text-muted-dark mb-1">Jenis Tiket</label>
        <select x-model="f.type" class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          <option value="">Semua</option><option>User Report</option><option>Technician Request</option>
        </select>
      </div>
      <button type="button" @click="f = {{ status: '', kategori: '', teknisi: '', type: '' }}"
              class="px-3 py-1.5 rounded-md border border-line dark:border-line-dark text-ink2 dark:text-ink2-dark text-sm">
        Reset filter
      </button>
    </div>
  </div>

  <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
    <div class="overflow-x-auto">
    <table class="tbl">
      <thead><tr>
        <th>ID</th><th>Jenis</th><th>Waktu</th><th>Kategori</th><th>Detail</th>
        <th>Prioritas</th><th>Teknisi</th><th>Status</th><th></th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
    </div>
    <p class="mt-3 text-xs text-muted dark:text-muted-dark">
      {len(tickets)} tiket · filter memakai status alur kerja (usulan). Teknisi
      adalah hasil assignment mesin {OPERATIONAL}.
    </p>
  </div>
</div>
"""
    return shell("Daftar Semua Tiket", "admin", depth, body,
                 active="admin/tiket.html")


def page_admin_tiket_baru(depth: int, data: dict) -> str:
    tech_opts = "\n".join(f'<option>{t["id"]}</option>' for t in data["techs"])
    root_opts = "\n".join(
        f'<option>{esc(t["id"])}</option>' for t in data["tickets"]
        if t["ticket_type"] == "User Report"
    )
    body = f"""
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
  <div class="lg:col-span-2">
    <h2 class="text-base font-semibold mb-3">Buat Tiket TK- (Manual)</h2>
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
      <p class="mb-4 text-sm text-ink2 dark:text-ink2-dark">
        Dipakai untuk membuat tiket <strong>Technician Request</strong> resmi dari
        permintaan bantuan teknisi lain. Prefix ID otomatis <strong>TK-</strong>.
      </p>
      <form x-data="{{ done: false }}" @submit.prevent="done = true" class="space-y-4">
        <div class="flex flex-wrap gap-x-4 gap-y-3 items-end">
          <div class="min-w-[180px]">
            <label for="related_id" class="block text-xs text-muted dark:text-muted-dark mb-1">Related Ticket ID <span class="text-danger dark:text-danger-dark">wajib</span></label>
            <select id="related_id" name="related_id" required
                    class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
              <option value="">— pilih tiket induk —</option>
              {root_opts}
            </select>
          </div>
          <div class="min-w-[150px]">
            <label for="requested_by" class="block text-xs text-muted dark:text-muted-dark mb-1">Requested By (Teknisi) <span class="text-danger dark:text-danger-dark">wajib</span></label>
            <select id="requested_by" name="requested_by" required
                    class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
              <option value="">— pilih teknisi —</option>
              {tech_opts}
            </select>
          </div>
          <div class="min-w-[180px]">
            <label for="timestamp" class="block text-xs text-muted dark:text-muted-dark mb-1">Waktu Masuk</label>
            <input id="timestamp" name="timestamp" type="datetime-local" value="2026-09-23T13:00" required
                   class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          </div>
        </div>
        <div class="flex flex-wrap gap-x-4 gap-y-3 items-end">
          <div class="min-w-[160px]">
            <label for="category" class="block text-xs text-muted dark:text-muted-dark mb-1">Kategori</label>
            <select id="category" name="category"
                    class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
              {''.join(f'<option>{esc(c)}</option>' for c in CATEGORIES)}
            </select>
          </div>
          <div class="min-w-[140px]">
            <label for="priority" class="block text-xs text-muted dark:text-muted-dark mb-1">Prioritas</label>
            <select id="priority" name="priority"
                    class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
              <option>Low</option><option>Medium</option><option selected>High</option>
            </select>
          </div>
          <div class="min-w-[110px]">
            <label for="duration" class="block text-xs text-muted dark:text-muted-dark mb-1">Durasi (menit)</label>
            <input id="duration" name="duration" type="number" min="1" value="30" required
                   class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          </div>
          <div class="flex-[2] min-w-[220px]">
            <label for="detail" class="block text-xs text-muted dark:text-muted-dark mb-1">Detail Kasus</label>
            <input id="detail" name="detail" type="text" placeholder="mis. butuh bongkar server di ruang C" required
                   class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          </div>
          <div>
            <button type="submit"
                    class="rounded-md bg-accent dark:bg-accent-dark hover:brightness-110 text-white px-4 py-2 text-sm font-medium transition">
              Simpan Tiket TK-
            </button>
          </div>
        </div>
        <div x-show="done" x-cloak class="px-4 py-2.5 rounded-lg border border-good/30 bg-good/10 text-good dark:text-good-dark text-sm">
          Mockup: tiket tidak benar-benar disimpan. Implementasi nyata:
          <code>POST /admin/tiket/baru</code> → <code>add_ticket(ticket_type=Technician Request)</code>
          (ID TK- otomatis, beban dihitung mesin, tetapi bukan kasus unik).
        </div>
      </form>
    </div>
  </div>

  <div>
    <h2 class="text-base font-semibold mb-3">Aturan Tiket TK-</h2>
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4 space-y-3 text-sm text-ink2 dark:text-ink2-dark">
      <div>
        <div class="text-xs font-semibold text-ink dark:text-ink-dark">Dihitung sebagai beban</div>
        <p class="mt-0.5 text-xs">Durasi TK- masuk ke beban kumulatif teknisi di semua skenario.</p>
      </div>
      <div class="border-t border-line dark:border-line-dark pt-3">
        <div class="text-xs font-semibold text-ink dark:text-ink-dark">Bukan kasus unik</div>
        <p class="mt-0.5 text-xs">TK- memakai Related Ticket ID, jadi tidak menambah jumlah kasus unik.</p>
      </div>
      <div class="border-t border-line dark:border-line-dark pt-3">
        <div class="text-xs font-semibold text-ink dark:text-ink-dark">Wajib dua field</div>
        <p class="mt-0.5 text-xs">Related Ticket ID + Requested By tidak boleh kosong — server tetap memvalidasi.</p>
      </div>
    </div>
  </div>
</div>
"""
    return shell("Buat Tiket TK-", "admin", depth, body,
                 active="admin/tiket-baru.html")


def page_admin_tiket_detail(depth: int, data: dict, ticket: dict) -> str:
    root = root_prefix(depth)
    asg = ticket["assignment"]
    body = f"""
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
  <div class="lg:col-span-2 space-y-4">
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="font-mono text-xl font-bold">{esc(ticket["id"])}</span>
          <span class="inline-block px-2 py-0.5 rounded-full text-[11px] bg-line/40 text-ink2 dark:text-ink2-dark">{esc(ticket["ticket_type"])}</span>
          {prio_badge(ticket["priority"])}
          {ticket_status_badge(ticket["id"], ticket["lifecycle"])}
        </div>
        <a href="{root}admin/tiket.html" class="text-sm text-ink2 dark:text-ink2-dark hover:underline">← semua tiket</a>
      </div>
      <p class="mt-3 text-sm">{esc(ticket["detail"])}</p>
      <div class="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Kategori</div>{esc(ticket["category"])}</div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Dibuat oleh</div>{esc(ticket["created_by"])}</div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Waktu masuk</div><span class="font-mono">{esc(ticket["time"])}</span></div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Durasi</div>{ticket["duration"]} menit (bobot {ticket["weight"]})</div>
        {''.join(f'<div><div class=\"text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark\">{lbl}</div><span class=\"font-mono\">{val}</span></div>' for lbl, val in (("Related Ticket ID", ticket["related_id"]), ("Requested By", ticket["requested_by"])) if val)}
      </div>
    </div>

    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
      <h2 class="text-base font-semibold mb-3">Penanganan (mesin {OPERATIONAL})</h2>
      {'<p class="text-sm text-ink2 dark:text-ink2-dark">Belum ditugaskan.</p>' if not asg else f'''
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Teknisi</div><span class="font-mono font-semibold">{esc(asg["tech_id"])}</span></div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Mulai</div><span class="font-mono">{esc(asg["start"])}</span></div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Selesai</div><span class="font-mono">{esc(asg["finish"])}</span></div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Menunggu</div>{asg["waiting"]} menit</div>
      </div>
      <p class="mt-3 text-xs text-muted dark:text-muted-dark">{esc(asg["rule_note"])}</p>
      <p class="mt-2 text-xs text-muted dark:text-muted-dark">
        Status mesin: <strong>{esc(ticket["assigned_tech"] or "—")}</strong> di semua skenario
        lihat <a href="{root}admin/simulasi.html" class="text-accent dark:text-accent-dark hover:underline">Simulasi Skenario</a>.
      </p>'''}
    </div>
  </div>

  <div>
    <h2 class="text-base font-semibold mb-3">Riwayat</h2>
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
      <ol class="space-y-3 text-sm">
        {''.join(f'<li class="flex gap-3"><span class="mt-1 w-2 h-2 rounded-full {c} shrink-0"></span><div><div class="font-medium">{esc(t)}</div><div class="text-xs text-muted dark:text-muted-dark">{esc(d)}</div></div></li>' for t, d, c in ticket["history"])}
      </ol>
      <p class="mt-4 text-xs text-muted dark:text-muted-dark">
        Riwayat status (usulan) — mesin Excel belum menyimpan perubahan status.
      </p>
    </div>
  </div>
</div>
"""
    return shell(f"Tiket {ticket['id']}", "admin", depth, body,
                 active="admin/tiket.html")


def page_admin_teknisi(depth: int, data: dict) -> str:
    scen = data["scen"][OPERATIONAL]
    rows = []
    for t in data["techs"]:
        load = scen["loads"][t["id"]]
        rows.append(
            f'<tr data-id="{t["id"]}">'
            f'<td class="font-mono font-semibold">{t["id"]}</td>'
            f'<td class="font-mono">{esc(t["name"])}</td>'
            f'<td>{status_badge(t["status"])}</td>'
            f'<td class="num">{load["dur"]}</td>'
            f'<td class="num">{load["w"]}</td>'
            f'<td class="num">{load["n"]}</td>'
            f'<td class="space-x-2 whitespace-nowrap">'
            f'<button type="button" class="text-accent dark:text-accent-dark text-sm hover:underline">edit</button>'
            f'<button type="button" class="text-danger dark:text-danger-dark text-sm hover:underline">nonaktifkan</button>'
            f'</td></tr>'
        )
    body = f"""
<div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
  <div class="flex items-center justify-between mb-4">
    <p class="text-sm text-ink2 dark:text-ink2-dark">
      Mesin distribusi beban (S1–S4) butuh daftar teknisi aktif yang valid —
      itulah sebabnya teknisi &amp; admin tidak self-register.
    </p>
    <button type="button"
            class="rounded-md bg-accent dark:bg-accent-dark hover:brightness-110 text-white px-4 py-2 text-sm font-medium transition">
      + Tambah Teknisi
    </button>
  </div>
  <div class="overflow-x-auto">
  <table class="tbl">
    <thead><tr>
      <th>ID</th><th>Nama</th><th>Status</th>
      <th class="num">Beban (m)</th><th class="num">Beban Berbobot</th>
      <th class="num">Tiket</th><th>Aksi</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  </div>
  <p class="mt-3 text-xs text-muted dark:text-muted-dark">
    Beban dari hasil mesin {OPERATIONAL}. Tombol edit/nonaktifkan/tambah
    tampak saja di mockup — belum menyimpan.
  </p>
</div>
"""
    return shell("Manajemen Teknisi", "admin", depth, body,
                 active="admin/teknisi.html")


# ===========================================================================
# Halaman pelapor
# ===========================================================================


def page_pelapor_dashboard(depth: int, data: dict) -> str:
    mine = [t for t in data["tickets"] if t["ticket_type"] == "User Report"]
    rows = "\n".join(
        f'<tr>'
        f'<td class="font-mono font-semibold">{esc(t["id"])}</td>'
        f'<td class="font-mono">{esc(t["time"])}</td>'
        f'<td class="max-w-[200px] truncate" title="{esc(t["detail"])}">{esc(t["detail"])}</td>'
        f'<td>{esc(t["category"])}</td><td>{prio_badge(t["priority"])}</td>'
        f'<td class="font-mono">{esc(t["assigned_tech"] or "—")}</td>'
        f'<td>{ticket_status_badge(t["id"], t["lifecycle"])}</td>'
        f'<td><a href="{root_prefix(depth)}pelapor/tiket/{esc(t["id"])}.html" class="text-accent dark:text-accent-dark hover:underline">lihat</a></td>'
        f'</tr>'
        for t in mine
    )
    s = data["scen"][OPERATIONAL]
    body = f"""
<div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
  {kpi_tile("Tiket saya", str(len(mine)), "semua User Report")}
  {live_status_count("Sedang dikerjakan", mine, "In Progress", "In Progress (update teknisi)")}
  {kpi_tile("Rata-rata tunggu", f'{s["avgw"]:.2f} m', f'maks {s["maxw"]} m (mesin {OPERATIONAL})')}
</div>

<div class="mt-8 rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
  <div class="flex items-center justify-between mb-3">
    <h2 class="text-base font-semibold">Tiket Saya</h2>
    <a href="{root_prefix(depth)}pelapor/tiket-baru.html"
       class="rounded-md bg-accent dark:bg-accent-dark hover:brightness-110 text-white px-4 py-2 text-sm font-medium transition">
      + Buat Tiket Baru
    </a>
  </div>
  <div class="overflow-x-auto">
  <table class="tbl">
    <thead><tr>
      <th>ID</th><th>Waktu</th><th>Detail</th><th>Kategori</th>
      <th>Prioritas</th><th>Teknisi</th><th>Status</th><th></th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
</div>
"""
    return shell("Tiket Saya", "pelapor", depth, body,
                 active="pelapor/dashboard.html")


def page_pelapor_tiket_baru(depth: int, data: dict) -> str:
    body = f"""
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
  <div class="lg:col-span-2">
    <h2 class="text-base font-semibold mb-3">Buat Tiket Baru</h2>
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
      <p class="mb-4 text-sm text-ink2 dark:text-ink2-dark">
        Tiket Anda akan dapat ID <strong>T-</strong> otomatis dan masuk antrian
        distribusi mesin. Teknisi ditugaskan oleh sistem, bukan dipilih Anda.
      </p>
      <form x-data="{{ done: false }}" @submit.prevent="done = true" class="space-y-4">
        <div class="flex flex-wrap gap-x-4 gap-y-3 items-end">
          <div class="min-w-[180px]">
            <label for="timestamp" class="block text-xs text-muted dark:text-muted-dark mb-1">Waktu Masuk</label>
            <input id="timestamp" name="timestamp" type="datetime-local" value="2026-09-23T13:00" required
                   class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          </div>
          <div class="min-w-[160px]">
            <label for="category" class="block text-xs text-muted dark:text-muted-dark mb-1">Kategori</label>
            <select id="category" name="category"
                    class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
              {''.join(f'<option>{esc(c)}</option>' for c in CATEGORIES)}
            </select>
          </div>
          <div class="min-w-[140px]">
            <label for="priority" class="block text-xs text-muted dark:text-muted-dark mb-1">Prioritas</label>
            <select id="priority" name="priority"
                    class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
              <option>Low</option><option>Medium</option><option selected>High</option>
            </select>
          </div>
          <div class="min-w-[110px]">
            <label for="duration" class="block text-xs text-muted dark:text-muted-dark mb-1">Estimasi Durasi (menit)</label>
            <input id="duration" name="duration" type="number" min="1" value="30" required
                   class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          </div>
        </div>
        <div class="flex flex-wrap gap-x-4 gap-y-3 items-end">
          <div class="flex-[2] min-w-[220px]">
            <label for="detail" class="block text-xs text-muted dark:text-muted-dark mb-1">Detail Kasus</label>
            <input id="detail" name="detail" type="text" placeholder="mis. WiFi mati total di gedung C" required
                   class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          </div>
          <div>
            <button type="submit"
                    class="rounded-md bg-accent dark:bg-accent-dark hover:brightness-110 text-white px-4 py-2 text-sm font-medium transition">
              Kirim Tiket
            </button>
          </div>
        </div>
        <div x-show="done" x-cloak class="px-4 py-2.5 rounded-lg border border-good/30 bg-good/10 text-good dark:text-good-dark text-sm">
          Mockup: tiket tidak benar-benar disimpan. Implementasi nyata:
          <code>POST /pelapor/tiket/baru</code> → ID T- otomatis, langsung masuk
          antrian mesin distribusi.
        </div>
      </form>
    </div>
  </div>

  <div>
    <h2 class="text-base font-semibold mb-3">Yang Terjadi Selanjutnya</h2>
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4 space-y-3 text-sm text-ink2 dark:text-ink2-dark">
      <div><div class="text-xs font-semibold text-ink dark:text-ink-dark">1. ID otomatis</div>
        <p class="mt-0.5 text-xs">Sistem men-generate ID T- (counter terpisah dari TK-) untuk mencegah bentrok input bersamaan.</p></div>
      <div class="border-t border-line dark:border-line-dark pt-3"><div class="text-xs font-semibold text-ink dark:text-ink-dark">2. Teknisi dipilih mesin</div>
        <p class="mt-0.5 text-xs">Berdasarkan skenario aktif (S1–S4). Anda tidak memilih teknisi.</p></div>
      <div class="border-t border-line dark:border-line-dark pt-3"><div class="text-xs font-semibold text-ink dark:text-ink-dark">3. Status berubah</div>
        <p class="mt-0.5 text-xs">Open → In Progress → Resolved. Riwayat terlihat di detail tiket.</p></div>
    </div>
  </div>
</div>
"""
    return shell("Buat Tiket Baru", "pelapor", depth, body,
                 active="pelapor/tiket-baru.html")


def page_pelapor_tiket_detail(depth: int, data: dict, ticket: dict) -> str:
    root = root_prefix(depth)
    asg = ticket["assignment"]
    body = f"""
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
  <div class="lg:col-span-2 space-y-4">
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="font-mono text-xl font-bold">{esc(ticket["id"])}</span>
          <span class="inline-block px-2 py-0.5 rounded-full text-[11px] bg-line/40 text-ink2 dark:text-ink2-dark">{esc(ticket["ticket_type"])}</span>
          {prio_badge(ticket["priority"])}
          {ticket_status_badge(ticket["id"], ticket["lifecycle"])}
        </div>
        <a href="{root}pelapor/dashboard.html" class="text-sm text-ink2 dark:text-ink2-dark hover:underline">← kembali</a>
      </div>
      <p class="mt-3 text-sm">{esc(ticket["detail"])}</p>
      <div class="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Kategori</div>{esc(ticket["category"])}</div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Prioritas</div>{esc(ticket["priority"])} (bobot {ticket["weight"]})</div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Waktu masuk</div><span class="font-mono">{esc(ticket["time"])}</span></div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Estimasi durasi</div>{ticket["duration"]} menit</div>
      </div>
    </div>

    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
      <h2 class="text-base font-semibold mb-3">Penanganan</h2>
      {'<p class="text-sm text-ink2 dark:text-ink2-dark">Belum ditugaskan.</p>' if not asg else f'''
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Teknisi</div><span class="font-mono font-semibold">{esc(asg["tech_id"])}</span></div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Mulai</div><span class="font-mono">{esc(asg["start"])}</span></div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Selesai</div><span class="font-mono">{esc(asg["finish"])}</span></div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Menunggu</div>{asg["waiting"]} menit</div>
      </div>
      <p class="mt-3 text-xs text-muted dark:text-muted-dark">{esc(asg["rule_note"])}</p>
      <p class="mt-2 text-xs text-muted dark:text-muted-dark">
        Aturan penugasan: mesin {OPERATIONAL} ({esc(data["scen"][OPERATIONAL]["rule"])}).
      </p>'''}
    </div>
  </div>

  <div>
    <h2 class="text-base font-semibold mb-3">Riwayat</h2>
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
      <ol class="space-y-3 text-sm">
        {''.join(f'<li class="flex gap-3"><span class="mt-1 w-2 h-2 rounded-full {c} shrink-0"></span><div><div class="font-medium">{esc(t)}</div><div class="text-xs text-muted dark:text-muted-dark">{esc(d)}</div></div></li>' for t, d, c in ticket["history"])}
      </ol>
      <p class="mt-4 text-xs text-muted dark:text-muted-dark">
        Riwayat status (usulan) — mesin Excel belum menyimpan perubahan status.
      </p>
    </div>
  </div>
</div>
"""
    return shell(f"Tiket {ticket['id']}", "pelapor", depth, body)


# ===========================================================================
# Halaman teknisi
# ===========================================================================


def page_teknisi_dashboard(depth: int, data: dict, tech_id: str) -> str:
    tech = next(t for t in data["techs"] if t["id"] == tech_id)
    mine = [t for t in data["tickets"] if t["assigned_tech"] == tech_id]
    scen = data["scen"][OPERATIONAL]
    load = scen["loads"][tech_id]

    rows = "\n".join(
        f'<tr x-show="(f.status === \'\' || ticketStatus(\'{esc(t["id"])}\', \'{esc(t["lifecycle"])}\') === f.status)'
        f' && (f.prio === \'\' || $el.dataset.prio === f.prio)">'
        f' data-prio="{esc(t["priority"])}">'
        f'<td class="font-mono font-semibold">{esc(t["id"])}</td>'
        f'<td class="font-mono">{esc(t["time"])}</td>'
        f'<td class="max-w-[200px] truncate" title="{esc(t["detail"])}">{esc(t["detail"])}</td>'
        f'<td>{esc(t["category"])}</td><td>{prio_badge(t["priority"])}</td>'
        f'<td class="font-mono">{esc(t["start"] or "—")} → {esc(t["finish"] or "—")}</td>'
        f'<td><span data-status data-ticket-id="{esc(t["id"])}" data-default="{esc(t["lifecycle"])}">{status_badge(t["lifecycle"])}</span></td>'
        f'<td><a href="{root_prefix(depth)}teknisi/tiket/{esc(t["id"])}.html" class="text-accent dark:text-accent-dark hover:underline">kerjakan</a></td>'
        f'</tr>'
        for t in mine
    )

    body = f"""
<div class="grid grid-cols-1 sm:grid-cols-4 gap-4">
  {kpi_tile("Tiket ditugaskan", str(len(mine)), f"hasil mesin {OPERATIONAL}")}
  {kpi_tile("Beban saya", f'{load["dur"]} menit', f'ideal {scen["ideal"]:g} menit')}
  {kpi_tile("Beban berbobot", f'{load["w"]} pt-min', f'{load["n"]} tiket')}
  {live_status_count("Sedang dikerjakan", mine, "In Progress", "In Progress")}
</div>

<div class="mt-8 rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
  <div class="flex items-center justify-between mb-3">
    <h2 class="text-base font-semibold">Tiket Ditugaskan ke {esc(tech_id)} {esc(tech["name"])}</h2>
    <a href="{root_prefix(depth)}teknisi/minta-bantuan.html"
       class="rounded-md border border-line dark:border-line-dark text-ink2 dark:text-ink2-dark hover:bg-panel2 dark:hover:bg-panel2-dark px-4 py-2 text-sm font-medium transition">
      Minta Bantuan Teknisi Lain
    </a>
  </div>
  <div x-data="{{ f: {{ status: '', prio: '' }} }}">
    <div class="flex flex-wrap gap-x-4 gap-y-3 items-end mb-3">
      <div class="min-w-[140px]">
        <label class="block text-xs text-muted dark:text-muted-dark mb-1">Filter status</label>
        <select x-model="f.status" class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          <option value="">Semua</option><option>Open</option><option>In Progress</option><option>Resolved</option>
        </select>
      </div>
      <div class="min-w-[140px]">
        <label class="block text-xs text-muted dark:text-muted-dark mb-1">Filter prioritas</label>
        <select x-model="f.prio" class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          <option value="">Semua</option><option>Low</option><option>Medium</option><option>High</option>
        </select>
      </div>
    </div>
    <div class="overflow-x-auto">
    <table class="tbl">
      <thead><tr>
        <th>ID</th><th>Waktu</th><th>Detail</th><th>Kategori</th>
        <th>Prioritas</th><th>Jadwal</th><th>Status</th><th></th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
    </div>
  </div>
</div>
"""
    return shell("Tiket Ditugaskan", "teknisi", depth, body,
                 active="teknisi/dashboard.html")


def page_teknisi_tiket_detail(depth: int, data: dict, ticket: dict) -> str:
    root = root_prefix(depth)
    asg = ticket["assignment"]
    body = f"""
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
  <div class="lg:col-span-2 space-y-4">
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4"
         x-data="{{ status: ticketStatus('{esc(ticket["id"])}', '{esc(ticket["lifecycle"])}'), saved: false }}"
         x-init="$watch('status', function (v) {{ setTicketStatus('{esc(ticket["id"])}', v); saved = true; }})">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="font-mono text-xl font-bold">{esc(ticket["id"])}</span>
          {prio_badge(ticket["priority"])}
          <span data-status x-show="false">{status_badge("Open")}</span>
        </div>
        <a href="{root}teknisi/dashboard.html" class="text-sm text-ink2 dark:text-ink2-dark hover:underline">← kembali</a>
      </div>
      <p class="mt-3 text-sm">{esc(ticket["detail"])}</p>

      <div class="mt-4 border-t border-line dark:border-line-dark pt-4">
        <div class="text-xs font-semibold text-ink2 dark:text-ink2-dark mb-2">Update Status</div>
        <div class="flex flex-wrap gap-2">
          {''.join(f'<button type="button" @click="status = \'{s}\'" :class="status === \'{s}\' ? \'bg-accent dark:bg-accent-dark text-white border-accent dark:border-accent-dark\' : \'border-line dark:border-line-dark text-ink2 dark:text-ink2-dark hover:bg-panel2 dark:hover:bg-panel2-dark\'" class="px-3.5 py-1.5 rounded-lg text-sm border transition-colors">{s}</button>' for s in ("Open", "In Progress", "Resolved"))}
        </div>
        <p class="mt-3 text-xs text-muted dark:text-muted-dark">
          Status sekarang: <strong x-text="status"></strong>
          <span x-show="saved" x-cloak>· disimpan (mockup, client-side)</span>
        </p>
        <p class="mt-1 text-xs text-muted dark:text-muted-dark">
          Siklus Open → In Progress → Resolved adalah <strong>usulan</strong> —
          belum ada di mesin Excel.
        </p>
      </div>
    </div>

    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
      <h2 class="text-base font-semibold mb-3">Data Penugasan (mesin {OPERATIONAL})</h2>
      {'<p class="text-sm text-ink2 dark:text-ink2-dark">Belum ditugaskan.</p>' if not asg else f'''
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Mulai</div><span class="font-mono">{esc(asg["start"])}</span></div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Selesai</div><span class="font-mono">{esc(asg["finish"])}</span></div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Menunggu</div>{asg["waiting"]} menit</div>
        <div><div class="text-[10px] uppercase tracking-wide text-muted dark:text-muted-dark">Beban berbobot</div>{asg["weighted_load"]} pt-min</div>
      </div>
      <p class="mt-3 text-xs text-muted dark:text-muted-dark">{esc(asg["rule_note"])}</p>'''}
    </div>
  </div>

  <div>
    <h2 class="text-base font-semibold mb-3">Riwayat</h2>
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
      <ol class="space-y-3 text-sm">
        {''.join(f'<li class="flex gap-3"><span class="mt-1 w-2 h-2 rounded-full {c} shrink-0"></span><div><div class="font-medium">{esc(t)}</div><div class="text-xs text-muted dark:text-muted-dark">{esc(d)}</div></div></li>' for t, d, c in ticket["history"])}
      </ol>
    </div>
    <div class="mt-4 rounded-xl border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark p-4">
      <div class="text-xs text-muted dark:text-muted-dark mb-1">Butuh bantuan?</div>
      <p class="text-xs text-ink2 dark:text-ink2-dark">
        Minta teknisi lain bantu — permintaan akan dibuatkan tiket TK- oleh admin.
      </p>
      <a href="{root}teknisi/minta-bantuan.html" class="mt-3 inline-block text-sm font-medium text-accent dark:text-accent-dark hover:underline">Form minta bantuan →</a>
    </div>
  </div>
</div>
"""
    return shell(f"Kerjakan Tiket {ticket['id']}", "teknisi", depth, body)


def page_teknisi_minta_bantuan(depth: int, data: dict, tech_id: str) -> str:
    root_opts = "\n".join(
        f'<option value="{esc(t["id"])}">{esc(t["id"])} — {esc(t["detail"][:40])}</option>'
        for t in data["tickets"]
        if t["assigned_tech"] == tech_id
    )
    others = "\n".join(
        f'<option value="{t["id"]}">{t["id"]} {esc(t["name"])}</option>'
        for t in data["techs"] if t["id"] != tech_id
    )
    body = f"""
<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
  <div class="lg:col-span-2">
    <h2 class="text-base font-semibold mb-3">Minta Bantuan Teknisi Lain</h2>
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4">
      <p class="mb-4 text-sm text-ink2 dark:text-ink2-dark">
        Permintaan Anda masuk sebagai <strong>permintaan</strong>, bukan tiket
        langsung. Admin yang membuatkan tiket <strong>TK-</strong> reslinya —
        sesuai skema: TK- dihitung sebagai beban, tetapi bukan kasus unik.
      </p>
      <form x-data="{{ done: false }}" @submit.prevent="done = true" class="space-y-4">
        <div class="flex flex-wrap gap-x-4 gap-y-3 items-end">
          <div class="min-w-[240px]">
            <label for="related_id" class="block text-xs text-muted dark:text-muted-dark mb-1">Related Ticket ID (tiket saya) <span class="text-danger dark:text-danger-dark">wajib</span></label>
            <select id="related_id" name="related_id" required
                    class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
              <option value="">— pilih tiket —</option>
              {root_opts}
            </select>
          </div>
          <div class="min-w-[160px]">
            <label for="requested_by" class="block text-xs text-muted dark:text-muted-dark mb-1">Saya</label>
            <input id="requested_by" type="text" value="{tech_id}" readonly
                   class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm font-mono text-ink2 dark:text-ink2-dark">
          </div>
          <div class="min-w-[160px]">
            <label for="target" class="block text-xs text-muted dark:text-muted-dark mb-1">Teknisi Tujuan</label>
            <select id="target" name="target"
                    class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
              <option value="">— pilih teknisi —</option>
              {others}
            </select>
          </div>
        </div>
        <div class="flex flex-wrap gap-x-4 gap-y-3 items-end">
          <div class="flex-[2] min-w-[220px]">
            <label for="detail" class="block text-xs text-muted dark:text-muted-dark mb-1">Detail Bantuan yang Dibutuhkan</label>
            <input id="detail" name="detail" type="text" placeholder="mis. butuh dua orang angkat rack server" required
                   class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          </div>
          <div class="min-w-[110px]">
            <label for="duration" class="block text-xs text-muted dark:text-muted-dark mb-1">Estimasi Durasi (menit)</label>
            <input id="duration" name="duration" type="number" min="1" value="30" required
                   class="w-full rounded-md border border-line dark:border-line-dark bg-panel2 dark:bg-panel2-dark px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40">
          </div>
          <div>
            <button type="submit"
                    class="rounded-md bg-accent dark:bg-accent-dark hover:brightness-110 text-white px-4 py-2 text-sm font-medium transition">
              Kirim Permintaan
            </button>
          </div>
        </div>
        <div x-show="done" x-cloak class="px-4 py-2.5 rounded-lg border border-good/30 bg-good/10 text-good dark:text-good-dark text-sm">
          Mockup: permintaan tercatat. Admin akan melihat ini dan membuat tiket
          TK- via menu <strong>Buat Tiket TK-</strong>.
        </div>
      </form>
    </div>
  </div>

  <div>
    <h2 class="text-base font-semibold mb-3">Kenapa Begitu?</h2>
    <div class="rounded-xl border border-line dark:border-line-dark bg-panel dark:bg-panel-dark p-4 space-y-3 text-sm text-ink2 dark:text-ink2-dark">
      <div><div class="text-xs font-semibold text-ink dark:text-ink-dark">Bukan tiket langsung</div>
        <p class="mt-0.5 text-xs">Teknisi tidak membuat TK- sendiri — admin yang menyetujui, supaya daftar beban tetap terkontrol.</p></div>
      <div class="border-t border-line dark:border-line-dark pt-3"><div class="text-xs font-semibold text-ink dark:text-ink-dark">Beban tambahan</div>
        <p class="mt-0.5 text-xs">Saat TK- dibuat, durasinya masuk ke beban kumulatif teknisi tujuan di semua skenario.</p></div>
      <div class="border-t border-line dark:border-line-dark pt-3"><div class="text-xs font-semibold text-ink dark:text-ink-dark">Bukan kasus unik</div>
        <p class="mt-0.5 text-xs">TK- selalu merujuk tiket induk lewat Related Ticket ID.</p></div>
    </div>
  </div>
</div>
"""
    return shell("Minta Bantuan Teknisi Lain", "teknisi", depth, body,
                 active="teknisi/minta-bantuan.html")


# ===========================================================================
# Generator utama
# ===========================================================================


def main() -> int:
    sim = Simulation.load()
    res = sim.run_all()
    techs = sim.technicians

    # --- data dari mesin (bukan hardcode) ---
    data: dict = {
        "users": USERS,
        "techs": [{"id": t.id, "name": t.name, "status": t.initial_status.value}
                  for t in techs],
        "scen": {},
        "tickets": [],
        "recent": [],
    }
    for k, ind in res.indicators.items():
        data["scen"][k] = {
            "name": ind.name, "rule": ind.rule, "purpose": ind.purpose,
            "max": ind.max_minutes, "min": ind.min_minutes, "gap": ind.gap_minutes,
            "balance": round(ind.balance_index, 4), "stdev": round(ind.stdev_minutes, 2),
            "jains": round(ind.jains_index, 4), "gapw": ind.gap_weighted,
            "jainsw": round(ind.jains_index_weighted, 4),
            "avgw": round(ind.avg_waiting, 2), "maxw": ind.max_waiting,
            "last": ind.last_finish.strftime("%H:%M"),
            "total": ind.total_tickets, "cases": ind.unique_cases,
            "dur": ind.total_duration, "ideal": round(ind.ideal_load, 2),
            "loads": {tid: {"dur": l.total_minutes, "w": l.weighted_load, "n": l.tickets}
                      for tid, l in ind.loads.items()},
        }
    data["best_gap"] = res.best_by_gap_minutes
    data["best_gapw"] = res.best_by_gap_weighted

    # assignment kondisi operasional: tiket -> teknisi & jadwal
    op_ind = res.indicators[OPERATIONAL]
    by_ticket = {}
    for a in op_ind.assignments:
        by_ticket[a.ticket.id] = {
            "tech_id": a.tech_id,
            "start": a.start.strftime("%H:%M"),
            "finish": a.finish.strftime("%H:%M"),
            "waiting": a.waiting,
            "weighted_load": a.weighted_load,
            "rule_note": a.rule_note,
        }

    def lifecycle(t) -> str:
        """Status alur kerja (USULAN) — tidak dari mesin Excel."""
        return "Open"

    for t in sorted(sim.tickets, key=lambda x: x.timestamp):
        asg = by_ticket.get(t.id)
        data["tickets"].append({
            "id": t.id,
            "ticket_type": t.ticket_type.value,
            "created_by": t.created_by,
            "time": t.timestamp.strftime("%Y-%m-%d %H:%M"),
            "category": t.category,
            "detail": t.detail,
            "priority": t.priority.value,
            "weight": t.weight,
            "duration": t.duration,
            "related_id": t.related_id,
            "requested_by": t.requested_by,
            "assigned_tech": asg["tech_id"] if asg else None,
            "start": asg["start"] if asg else None,
            "finish": asg["finish"] if asg else None,
            "lifecycle": lifecycle(t),
            "assignment": asg,
            "history": [
                ("Tiket dibuat", f"{t.timestamp.strftime('%H:%M')} oleh {t.created_by}", "bg-accent"),
                ("Ditugaskan ke " + (asg["tech_id"] if asg else "—"),
                 f"mesin {OPERATIONAL} · {asg['rule_note'] if asg else 'belum'}", "bg-warn"),
                ("Dikerjakan", "status alur kerja (usulan)", "bg-good"),
            ],
        })
    data["recent"] = [
        {"id": t["id"], "time": t["time"].split(" ")[1], "category": t["category"],
         "detail": t["detail"], "priority": t["priority"], "duration": t["duration"]}
        for t in data["tickets"][-5:]
    ]

    # --- chart ---
    cats = [(k, data["scen"][k]["name"]) for k in data["scen"]]
    series = [(t.id, f"{t.id} {t.name}") for t in techs]

    def mk(weighted: bool, title: str, unit: str) -> str:
        vals = {
            (ck, sk): (data["scen"][ck]["loads"][sk]["w"] if weighted
                       else data["scen"][ck]["loads"][sk]["dur"])
            for ck, _ in cats for sk, _ in series
        }
        return grouped_bar_chart(categories=cats, series=series, values=vals,
                                 title=title, unit=unit)

    data["chart_durasi"] = mk(False, "Beban Durasi per Teknisi (menit)", "menit")
    data["chart_weighted"] = mk(True, "Beban Berbobot per Teknisi (pt-min)", "pt-min")

    # --- tulis file statis pendukung ---
    with open(os.path.join(OUT_DIR, "_auth.js"), "w", encoding="utf-8") as f:
        f.write(AUTH_JS)
    with open(os.path.join(OUT_DIR, "_data.js"), "w", encoding="utf-8") as f:
        # data JS: tidak menyertakan SVG (berupa string besar)
        payload = {k: v for k, v in data.items() if not k.startswith("chart")}
        f.write("/* Data dari mesin simulasi tervalidasi. Jangan diedit manual —\n"
                "   di-generate oleh build_mockup.py. */\n")
        f.write("const ROLE_HOME = " + json.dumps(ROLE_HOME, indent=2) + ";\n")
        f.write("const DB = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n")

    # --- tulis halaman ---
    written: list = []

    def write(path: str, content: str) -> None:
        full = os.path.join(OUT_DIR, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        written.append((path, len(content)))

    # auth (root, depth 0)
    write("login.html",
          shell("Masuk", None, 0, page_login(), guard=False))
    write("register.html",
          shell("Daftar Pelapor", None, 0, page_register(), guard=False))
    write("403.html", shell("Akses Ditolak", None, 0, page_403(), guard=False))
    write("404.html", shell("Tidak Ditemukan", None, 0, page_404(), guard=False))

    # root: pengalih ke login. Host statis umum (file://, GitHub Pages, Netlify
    # tanpa redirect rule) membuka index.html saat user ketik URL folder —
    # tanpa ini root mockup mendarat di 404 host / error blank.
    write("index.html", INDEX_REDIRECT)

    # admin (depth 1)
    write("admin/dashboard.html", page_admin_dashboard(1, data))
    write("admin/simulasi.html", page_admin_simulasi(1, data))
    write("admin/tiket.html", page_admin_tiket(1, data))
    write("admin/tiket-baru.html", page_admin_tiket_baru(1, data))
    write("admin/teknisi.html", page_admin_teknisi(1, data))
    for t in data["tickets"]:
        write(f"admin/tiket/{t['id']}.html",
              page_admin_tiket_detail(2, data, t))

    # pelapor (depth 1; detail tiket depth 2)
    write("pelapor/dashboard.html", page_pelapor_dashboard(1, data))
    write("pelapor/tiket-baru.html", page_pelapor_tiket_baru(1, data))
    for t in data["tickets"]:
        write(f"pelapor/tiket/{t['id']}.html",
              page_pelapor_tiket_detail(2, data, t))

    # teknisi (depth 1; detail tiket depth 2)
    write("teknisi/dashboard.html", page_teknisi_dashboard(1, data, "T01"))
    write("teknisi/minta-bantuan.html", page_teknisi_minta_bantuan(1, data, "T01"))
    for t in data["tickets"]:
        if t["assigned_tech"] == "T01":
            write(f"teknisi/tiket/{t['id']}.html",
                  page_teknisi_tiket_detail(2, data, t))

    # --- bersihkan mockup lama yang sudah dipindah ---
    for stale in ("dashboard.html", "simulasi.html", "tiket-baru.html", "_data.json"):
        old = os.path.join(OUT_DIR, stale)
        if os.path.exists(old):
            os.remove(old)

    for path, size in sorted(written):
        print(f"ditulis: {path:<32} {size:>8,} b")
    print(f"\nTotal {len(written)} halaman + _data.js + _auth.js di {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
