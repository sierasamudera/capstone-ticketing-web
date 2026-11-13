"""Web application — antarmuka browser untuk simulasi ticketing.

Jalankan::

    python -m ticketing.web            # http://localhost:5000
    python -m ticketing.web --port 8080
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from typing import Optional

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
    flash,
    jsonify,
)
from flask_login import current_user

from .. import __version__
from ..auth import (
    authenticate,
    do_login,
    do_logout,
    init_login_manager,
    login_required,
    require_any_role,
)
from ..models import CATEGORIES, PRIORITIES, TICKET_TYPES
from ..scenarios import SCENARIOS
from ..seed import DEFAULT_DATA_PATH, add_ticket, load_dataset, save_dataset
from ..simulation import Simulation

# Mockup multi-role (login + 62 halaman statis). Dilayani di bawah prefix
# /mockup/ agar bisa demo online lewat tunnel/PaaS bersama app utama, walau
# implementasi Flask per-role belum jadi. Path di mockup semuanya relatif,
# jadi prefix tidak merusak link-nya.
_MOCKUP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "mockup",
)

# In-memory copy agar penambahan tiket tidak menulis file terus-menerus,
# kecuali diminta simpan.
_store: dict = {"dataset": None, "path": None}


def _dataset(path: Optional[str] = None):
    if _store["dataset"] is None or (path and path != _store["path"]):
        _store["dataset"] = load_dataset(path or DEFAULT_DATA_PATH)
        _store["path"] = path or DEFAULT_DATA_PATH
    return _store["dataset"]


def _build_sim(path: Optional[str] = None) -> Simulation:
    return Simulation(_dataset(path))


def create_app(data_path: Optional[str] = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.config["SECRET_KEY"] = "ticketing-sim-dev"
    init_login_manager(app)
    # Pastikan tabel users (dan seluruh skema DB) ada sebelum request pertama
    # dijalankan — aman dipanggil berulang kali (CREATE TABLE IF NOT EXISTS).
    from ..db import init_db
    init_db()
    if data_path:
        _store["path"] = data_path

    @app.context_processor
    def inject_globals():
        from .charts import VIZ_CSS, grouped_bar_chart

        def workload_chart(result, technicians, weighted=False):
            """Chart beban per teknisi per skenario.

            Palet memakai var(--viz-series-*) dengan fallback hex, jadi chart
            otomatis mengikuti tema (light/dark) lewat CSS tanpa re-render
            server-side; tetap terbaca tanpa CSS variable.
            """
            cats = [(k, SCENARIOS[k]["name"]) for k in result.keys if k in SCENARIOS]
            series = [(t.id, f"{t.id} {t.name}") for t in technicians]
            values = {}
            for ck, _ in cats:
                ind = result[ck]
                for sk, _ in series:
                    load = ind.loads[sk]
                    values[(ck, sk)] = (
                        load.weighted_load if weighted else load.total_minutes
                    )
            return grouped_bar_chart(
                categories=cats,
                series=series,
                values=values,
                title=(
                    "Beban Berbobot per Teknisi (pt-min)"
                    if weighted
                    else "Beban Durasi per Teknisi (menit)"
                ),
                unit="pt-min" if weighted else "menit",
            )

        return {
            "version": __version__,
            "categories": CATEGORIES,
            "priorities": PRIORITIES,
            "ticket_types": TICKET_TYPES,
            "scenarios": SCENARIOS,
            "workload_chart": workload_chart,
            "viz_css": VIZ_CSS,
        }

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("auth_dashboard"))
        sim = _build_sim()
        result = sim.run_all()
        return render_template(
            "index.html",
            sim=sim,
            result=result,
            active_scenario=None,
            detail=None,
        )

    # --- Autentikasi (login/logout/dashboard per role) ---------------------
    @app.route("/login", methods=["GET", "POST"])
    def login():
        from flask import render_template_string

        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = authenticate(username, password)
            if user:
                do_login(user)
                flash(f"Selamat datang, {user.username}.", "success")
                return redirect(url_for("auth_dashboard"))
            else:
                error = "Username atau password salah."
        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        do_logout()
        flash("Anda sudah keluar.", "info")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required()
    def auth_dashboard():
        role = current_user.role
        sim = _build_sim()
        result = sim.run_all()
        if role == "admin":
            return render_template("admin_dashboard.html", sim=sim, result=result)
        if role == "technician":
            return render_template("technician_dashboard.html", sim=sim, result=result, user=current_user)
        return render_template("reporter_dashboard.html", sim=sim, result=result, user=current_user)

    # --- Mockup multi-role -------------------------------------------------
    # Sajikan folder mockup/ di bawah /mockup/ untuk demo online. `index.html`
    # di root mockup mengalihkan ke login.html, jadi /mockup/ = mulai dari
    # halaman login, sama seperti dibuka via file://.
    @app.route("/mockup")
    def mockup_index():
        return redirect(url_for("mockup_root"))

    @app.route("/mockup/")
    @app.route("/mockup/index.html")
    def mockup_root():
        return send_from_directory(_MOCKUP_DIR, "index.html")

    @app.route("/mockup/<path:filename>")
    def mockup_file(filename: str):
        full = os.path.join(_MOCKUP_DIR, filename)
        # tolak path yang keluar dari folder mockup (mis. "../../wsgi.py")
        if os.path.commonpath([os.path.abspath(full), _MOCKUP_DIR]) != _MOCKUP_DIR:
            abort(404)
        return send_from_directory(_MOCKUP_DIR, filename)

    @app.route("/run/<key>")
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
        )

    @app.route("/api/indicators")
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

    @app.route("/tickets", methods=["POST"])
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
                created_by=current_user.username if current_user.is_authenticated else ("User" if ttype == "User Report" else "Admin"),
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

        # Re-run simulasi untuk semua skenario agar indikator & grafik langsung update
        sim = _build_sim()
        result = sim.run_all()

        # Simpan result ke session agar bisa dibaca template di halaman selanjutnya
        session["last_result"] = {
            "indicators": {
                k: {
                    "name": ind.name,
                    "gap_minutes": ind.gap_minutes,
                    "balance_index": ind.balance_index,
                    "jains_index": ind.jains_index,
                    "gap_weighted": ind.gap_weighted,
                    "jains_index_weighted": ind.jains_index_weighted,
                    "avg_waiting": ind.avg_waiting,
                    "max_waiting": ind.max_waiting,
                }
                for k, ind in result.indicators.items()
            },
            "assignments_by_scenario": {
                k: [{"ticket": a.ticket.id, "tech": a.tech_id, "status": a.status.value,
                      "start": a.start.strftime("%H:%M"), "finish": a.finish.strftime("%H:%M"),
                      "waiting": a.waiting, "rule": a.rule_note}
                    for a in result.indicators[k].assignments]
                for k in result.indicators
            },
            "technicians": [{"id": t.id, "name": t.name} for t in sim.technicians],
            "tickets_count": len(sim.tickets),
        }

        return redirect(url_for("index"))

    @app.route("/reset", methods=["POST"])
    def reset_data():
        _store["dataset"] = None
        _store["path"] = None
        flash("Dataset dimuat ulang dari file.", "info")
        return redirect(url_for("index"))

    return app


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
