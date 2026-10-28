"""Web application — antarmuka browser untuk simulasi ticketing.

Jalankan::

    python -m ticketing.web            # http://localhost:5000
    python -m ticketing.web --port 8080
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    jsonify,
)

from .. import __version__
from ..models import CATEGORIES, PRIORITIES, TICKET_TYPES, TicketType, Priority, TechStatus
from ..scenarios import SCENARIOS
from ..seed import DEFAULT_DATA_PATH, _default_parameters, _load_parameters, _dataset, save_dataset, Dataset, _ticket_from_dict
from ..simulation import Simulation

# ---------------------------------------------------------------------------
# Konfigurasi Autentikasi Sederhana (BISA DIGANTI GANTI)
# ---------------------------------------------------------------------------
# Username/Password statis — untuk demo/prototype saja.
# Di produksi gunakan hash password atau integrasi OAuth.
USERS = {
    # Admin — akses penuh
    "admin": {"password": "admin123", "role": "admin"},
    # Teknisi — masing-masing punya kredensial sendiri
    "T01": {"password": "tech01", "role": "technician"},
    "T02": {"password": "tech02", "role": "technician"},
    "T03": {"password": "tech03", "role": "technician"},
    # User/Pelapor — login cepat, terbatas fitur
    "user": {"password": "guest", "role": "user"},
}

# Kunci rahasia sesi Flask (ganti dengan kunci acak di produksi)
app = Flask(__name__)
app.secret_key = "ticketing-sim-dev-change-this-secret"


# ---------------------------------------------------------------------------
# Bantuan (Helper) untuk cek role & login
# ---------------------------------------------------------------------------

def login_required(role: Optional[str] = None):
    """Decorator: memastikan pengguna sudah login dan (opsional) memiliki role tertentu."""
    def wrapper(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            if "username" not in session:
                return redirect(url_for("login"))
            user_role = USERS.get(session["username"], {}).get("role")
            if user_role != session.get("_role"):
                session.clear()
                flash("Sesi berakhir atau role tidak valid.", "error")
                return redirect(url_for("login"))
            # Jika role spesifik diminta dan tidak cocok, tolak akses
            if role and user_role != role:
                flash("Anda tidak memiliki akses untuk halaman ini.", "error")
                return redirect(url_for("index"))
            return fn(*args, **kwargs)
        return wrapped
    return wrapper


def owner_required(fn):
    """Decorator: hanya admin yang bisa mengakses."""
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        if session.get("_role") != "admin":
            flash("Hanya admin yang bisa mengakses fitur ini.", "error")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Fungsi bantuan dataset & simulasi (menggunakan session-based store)
# ---------------------------------------------------------------------------

def _build_sim(path: Optional[str] = None) -> Simulation:
    return Simulation(_dataset(path))


# ---------------------------------------------------------------------------
# Rute: Login & Logout
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    # Jika pengguna sudah login, arahkan ke index
    if "username" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user_info = USERS.get(username)
        if user_info and user_info["password"] == password:
            session["username"] = username
            session["_role"] = user_info["role"]
            flash(f"Selamat datang, {username}!", "success")
            # Arahkan berdasarkan role
            if user_info["role"] == "admin":
                return redirect(url_for("index"))
            elif user_info["role"] == "technician":
                # Teknisi langsung ke halaman simulasi dengan parameter skenario default (S1)
                return redirect(url_for("index", _escaped_fragment_="S1"))
            else:  # user
                return redirect(url_for("index"))
        else:
            flash("Username atau password salah.", "error")
    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    flash("Anda telah logout.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Rute: Utama & Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
@login_required()  # Butuh login, tapi role bebas untuk halaman awal
def index():
    # Ambil parameter session atau gunakan default
    if "sim_start" not in session:
        session["sim_start"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    sim = _build_sim()
    result = sim.run_all()

    # Tentukan skenario aktif dari query string (?active=S1) atau default None
    active = request.args.get("active")

    detail = None
    if active and active in SCENARIOS:
        sim = _build_sim()
        ind = sim.run(active)
        result = sim.run_all()
        detail = ind

    return render_template(
        "index.html",
        sim=sim,
        result=result,
        active_scenario=active,
        detail=detail,
        username=session.get("username"),
        user_role=session.get("_role"),
    )


# ---------------------------------------------------------------------------
# Rute: Skenario S1–S4 (Run & Indikator)
# ---------------------------------------------------------------------------

@app.route("/run/<key>")
@login_required()  # Harus login
def run_one(key: str):
    if key not in SCENARIOS:
        flash(f"Skenario tidak dikenal: {key}", "error")
        return redirect(url_for("index"))

    sim = _build_sim()
    ind = sim.run(key)
    result = sim.run_all()
    return render_template(
        "index.html",
        sim=sim,
        result=result,
        active_scenario=key,
        detail=ind,
        username=session.get("username"),
        user_role=session.get("_role"),
    )


@app.route("/api/indicators")
@login_required()
def api_indicators():
    sim = _build_sim()
    result = sim.run_all()
    payload = {}
    for k, ind in result.indicators.items():
        payload[k] = {
            "name": ind.name,
            "gap_minutes": ind.gap_minutes,
            "balance_index": ind.balance_index,
            "jains_index": ind.jains_index,
            "gap_weighted": ind.gap_weighted,
            "jains_index_weighted": ind.jains_index_weighted,
            "avg_waiting": ind.avg_waiting,
            "max_waiting": ind.max_waiting,
        }
    return jsonify(payload)


# ---------------------------------------------------------------------------
# Rute: Tambah Tiket (Hanya Admin & Teknisi)
# ---------------------------------------------------------------------------

@app.route("/tickets", methods=["POST"])
@login_required(role="admin")  # HANYA admin yang bisa menambah tiket via CLI/web
def add_ticket_route():
    form = request.form
    try:
        ttype = form["ticket_type"]
        ds = _dataset()
        related = form.get("related_id") or None
        requested = form.get("requested_by") or None
        if ttype == "Technician Request" and (not related or not requested):
            flash(
                "Technician Request wajib mengisi Related Ticket ID dan "
                "Requested By (Technician).",
                "error",
            )
            return redirect(url_for("index"))
        ticket = add_ticket(
            dataset=ds,
            ticket_type=ttype,
            created_by="Admin" if ttype == "User Report" else "Admin",
            timestamp=datetime.strptime(
                form["timestamp"], "%Y-%m-%dT%H:%M"
            ),
            category=form["category"],
            detail=form["detail"],
            priority=form["priority"],
            duration=int(form["duration"]),
            related_id=related,
            requested_by=requested,
        )
        # reset cache supaya simulasi memakai dataset baru
        _store["dataset"] = None
        save_dataset(ds, _store["path"])
        flash(
            f"Tiket {ticket.id} ({ticket.ticket_type.value}) ditambahkan "
            f"dan dataset disimpan.",
            "success",
        )
    except ValueError as exc:
        flash(f"Input tidak valid: {exc}", "error")
    return redirect(url_for("index"))


@app.route("/reset", methods=["POST"])
@login_required(role="admin")
def reset_data():
    _store["dataset"] = None
    _store["path"] = None
    flash("Dataset dimuat ulang dari file.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Rute: Mockup multi-role (prefix /mockup/)
# ---------------------------------------------------------------------------
_MOCKUP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "mockup",
)


@app.route("/mockup")
def mockup_index():
    return redirect(url_for("mockup_root"))


@app.route("/mockup/", strict_slash=False)
@app.route("/mockup/index.html")
def mockup_root():
    return send_from_directory(_MOCKUP_DIR, "index.html")


@app.route("/mockup/<path:filename>")
def mockup_file(filename: str):
    full = os.path.join(_MOCKUP_DIR, filename)
    if os.path.commonpath([os.path.abspath(full), _MOCKUP_DIR]) != _MOCKUP_DIR:
        abort(404)
    return send_from_directory(_MOCKUP_DIR, filename)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Web app simulasi ticketing")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--data", default=None, help="path dataset JSON")
    args = parser.parse_args(argv)

    app = create_app(args.data)
    print(f"Server: http://{args.host}:{args.port}")
    print("Tekan Ctrl+C untuk berhenti.")
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())