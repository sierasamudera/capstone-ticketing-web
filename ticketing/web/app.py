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
    current_app,
    redirect,
    render_template,
    request,
    session,
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
    register_user,
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

# Path absolut berbasis __file__ agar aman di semua working directory
# (terutama PythonAnywhere di Linux).
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# In-memory copy agar penambahan tiket tidak menulis file terus-menerus,
# kecuali diminta simpan.
_store: dict = {"dataset": None, "path": None}


def _dataset(path: Optional[str] = None):
    target = path or current_app.config.get("DATA_PATH") or DEFAULT_DATA_PATH
    if _store["dataset"] is None or (path and path != _store["path"]):
        _store["dataset"] = load_dataset(target)
        _store["path"] = target
    return _store["dataset"]


def _build_sim(path: Optional[str] = None) -> Simulation:
    return Simulation(_dataset(path))


def create_app(data_path: Optional[str] = None, db_path: Optional[str] = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "ticketing-sim-dev-default")
    # Selalu gunakan path absolut; None tidak pernah disimpan.
    app.config["DATA_PATH"] = data_path or os.path.join(_BASE_DIR, "data", "tickets.json")
    app.config["DB_PATH"] = db_path or os.path.join(_BASE_DIR, "data", "ticketing.db")
    init_login_manager(app)
    # Pastikan tabel users (dan seluruh skema DB) ada sebelum request pertama
    # dijalankan — aman dipanggil berulang kali (CREATE TABLE IF NOT EXISTS).
    with app.app_context():
        from ..db import init_db
        init_db(app.config["DB_PATH"])
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
    @login_required()
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("auth_dashboard"))
        return redirect(url_for("login"))

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

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("auth_dashboard"))
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            try:
                user = register_user(username, password)
                do_login(user)
                flash(f"Akun pelapor '{user.username}' berhasil dibuat. Selamat datang!", "success")
                return redirect(url_for("auth_dashboard"))
            except ValueError as exc:
                error = str(exc)
        return render_template("register.html", error=error)

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
    @login_required(role="admin")
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

    def _redirect_by_role() -> str:
        """Arahkan ke dashboard sesuai role user yang login."""
        if current_user.is_authenticated:
            return url_for("auth_dashboard")
        return url_for("login")


    @app.route("/tickets", methods=["POST"])
    @login_required()
    def add_ticket_route():
        form = request.form
        ds = _dataset()
        role = current_user.role

        try:
            if role == "user":
                # Pelapor hanya boleh membuat User Report.
                ttype = "User Report"
                created_by = current_user.username
                related = None
                requested = None
            elif role == "technician":
                # Teknisi hanya boleh membuat Technician Request.
                ttype = "Technician Request"
                created_by = current_user.username
                related = form.get("related_id") or None
                requested = current_user.tech_id
                if not related:
                    flash(
                        "Technician Request wajib memilih Related Ticket ID.",
                        "error",
                    )
                    return redirect(_redirect_by_role())
                # related_id harus merujuk tiket yang sudah ada di dataset.
                existing_ids = {t.id for t in ds.tickets}
                if related not in existing_ids:
                    flash(f"Related Ticket ID '{related}' tidak ditemukan.", "error")
                    return redirect(_redirect_by_role())
            elif role == "admin":
                ttype = form["ticket_type"]
                created_by = current_user.username
                related = form.get("related_id") or None
                requested = form.get("requested_by") or None
                if ttype == "Technician Request" and (not related or not requested):
                    flash(
                        "Technician Request wajib mengisi Related Ticket ID dan "
                        "Requested By (Technician).",
                        "error",
                    )
                    return redirect(_redirect_by_role())
            else:
                flash("Role tidak dikenal.", "error")
                return redirect(_redirect_by_role())

            ticket = add_ticket(
                dataset=ds,
                ticket_type=ttype,
                created_by=created_by,
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
            # Simpan ke data/tickets.json (satu sumber kebenaran untuk
            # tiket + teknisi) agar perubahan persisten dan dibaca lagi
            # oleh load_dataset() pada request berikutnya.
            save_dataset(ds, app.config["DATA_PATH"])
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

        return redirect(_redirect_by_role())

    @app.route("/reset", methods=["POST"])
    @login_required(role="admin")
    def reset_data():
        _store["dataset"] = None
        _store["path"] = None
        flash("Dataset dimuat ulang dari file.", "info")
        return redirect(url_for("index"))

        # --- Status Tiket (Teknisi) --------------------------------------------
    @app.route("/tickets/<int:ticket_id>/status", methods=["POST"])
    @login_required(role="technician")
    def ticket_status(int ticket_id):
        action = request.form.get("action")
        if action not in ("start", "resolve"):
            flash("Aksi tidak valid.", "error")
            return redirect(_redirect_by_role())

        db_path = current_app.config["DB_PATH"]
        conn = get_db_connection(db_path)
        try:
            # Cek status saat ini
            row = conn.execute(
                "SELECT status, handled_by FROM ticket_status WHERE ticket_id = ?",
                (str(ticket_id),),
            ).fetchone()

            # Jika ticket belum ada di tabel status, status default "Open"
            if row is None:
                if action != "start":
                    flash("Tiket tidak bisa diselesaikan karena statusnya Open.", "error")
                    return redirect(_redirect_by_role())
                # Buat entri status Open dulu, baru start
                from datetime import datetime
                conn.execute(
                    "INSERT INTO ticket_status (ticket_id, status, handled_by, updated_at) VALUES (?, 'Open', NULL, datetime('now'))",
                    (str(ticket_id),),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT status, handled_by FROM ticket_status WHERE ticket_id = ?",
                    (str(ticket_id),),
                ).fetchone()

            current_status = row[0]
            handled_by = row[1]

            # Validasi transisi
            if action == "start":
                if current_status != "Open":
                    flash("Tiket harus status Open untuk dimulai.", "error")
                    return redirect(_redirect_by_role())
                # Start: Open -> In Progress, handled_by = teknisi login
                conn.execute(
                    "UPDATE ticket_status SET status = 'In Progress', handled_by = ?, updated_at = datetime('now') WHERE ticket_id = ?",
                    (current_user.tech_id, str(ticket_id)),
                )
                conn.commit()
                flash("Tiket berhasil diangkat untuk dikerjakan.", "success")
            elif action == "resolve":
                if current_status != "In Progress":
                    flash("Tiket harus status In Progress untuk diselesaikan.", "error")
                    return redirect(_redirect_by_role())
                # Resolve: hanya teknisi yang sama yang bisa resolve
                if handled_by != current_user.tech_id:
                    flash("Anda tidak bisa menyelesaikan tiket ini karena bukan teknisi yang menangani.", "error")
                    return redirect(_redirect_by_role())
                # In Progress -> Resolved
                conn.execute(
                    "UPDATE ticket_status SET status = 'Resolved', handled_by = ?, updated_at = datetime('now') WHERE ticket_id = ?",
                    (current_user.tech_id, str(ticket_id)),
                )
                conn.commit()
                flash("Tiket berhasil diselesaikan.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Terjadi kesalahan: {str(e)}", "error")
        finally:
            conn.close()

        return redirect(_redirect_by_role())

    # --- Error handler 403 / 404 -------------------------------------------
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("404.html"), 404

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
