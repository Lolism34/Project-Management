from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from database import get_db
from utils import hours_between, local_to_utc, role_required, utc_to_local, validate_csrf

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")


@manager_bp.route("")
@role_required("manager")
def dashboard():
    db = get_db()
    counts = {
        "time": db.execute("SELECT COUNT(*) FROM time_entries WHERE status = 'accepted'").fetchone()[0],
        "leave": db.execute("SELECT COUNT(*) FROM time_off WHERE status = 'pending'").fetchone()[0],
        "employees": db.execute("SELECT COUNT(*) FROM users WHERE role = 'employee' AND active = 1").fetchone()[0],
    }
    return render_template("manager_dashboard.html", counts=counts)


@manager_bp.route("/time")
@role_required("manager")
def review_time():
    rows = get_db().execute(
        """
        SELECT t.*, u.name, u.timezone
        FROM time_entries t JOIN users u ON u.id = t.user_id
        ORDER BY CASE t.status WHEN 'accepted' THEN 0 WHEN 'draft' THEN 1 ELSE 2 END,
                 t.clock_in_utc DESC
        """
    ).fetchall()
    entries = [dict(row) for row in rows]
    for entry in entries:
        entry["local_start"] = utc_to_local(entry["clock_in_utc"], entry["timezone"])
        entry["local_end"] = utc_to_local(entry["clock_out_utc"], entry["timezone"])
        entry["hours"] = hours_between(
            entry["clock_in_utc"], entry["clock_out_utc"], entry["break_minutes"]
        )
    return render_template("manager_time.html", entries=entries)


@manager_bp.route("/time/<int:entry_id>/approve", methods=("POST",))
@role_required("manager")
def approve_time(entry_id):
    validate_csrf()
    db = get_db()
    result = db.execute(
        """
        UPDATE time_entries
        SET status = 'approved', reviewed_by = ?, reviewed_at = ?
        WHERE id = ? AND status = 'accepted'
        """,
        (session["user_id"], datetime.now(timezone.utc).isoformat(), entry_id),
    )
    db.commit()
    flash("Time entry approved." if result.rowcount else "Only accepted entries can be approved.",
          "success" if result.rowcount else "error")
    return redirect(url_for("manager.review_time"))


@manager_bp.route("/time/<int:entry_id>/correct", methods=("POST",))
@role_required("manager")
def correct_time(entry_id):
    validate_csrf()
    db = get_db()
    entry = db.execute(
        """
        SELECT t.*, u.timezone FROM time_entries t
        JOIN users u ON u.id = t.user_id WHERE t.id = ?
        """,
        (entry_id,),
    ).fetchone()
    if not entry or entry["status"] != "accepted":
        flash("Only accepted entries can be corrected.", "error")
        return redirect(url_for("manager.review_time"))
    try:
        new_start = local_to_utc(request.form["clock_in"], entry["timezone"])
        new_end = local_to_utc(request.form["clock_out"], entry["timezone"])
        reason = request.form.get("reason", "").strip()
        if hours_between(new_start, new_end, entry["break_minutes"]) <= 0 or not reason:
            raise ValueError("Enter valid times and a correction reason.")
    except (ValueError, KeyError) as exc:
        flash(str(exc), "error")
        return redirect(url_for("manager.review_time"))

    db.execute(
        """
        INSERT INTO correction_log
        (entry_id, manager_id, old_clock_in_utc, old_clock_out_utc,
         new_clock_in_utc, new_clock_out_utc, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (entry_id, session["user_id"], entry["clock_in_utc"], entry["clock_out_utc"],
         new_start, new_end, reason),
    )
    db.execute(
        """
        UPDATE time_entries SET clock_in_utc = ?, clock_out_utc = ?,
        manager_note = ?, status = 'approved', reviewed_by = ?, reviewed_at = ?
        WHERE id = ?
        """,
        (new_start, new_end, reason, session["user_id"],
         datetime.now(timezone.utc).isoformat(), entry_id),
    )
    db.commit()
    flash("Entry corrected, logged, and approved.", "success")
    return redirect(url_for("manager.review_time"))


@manager_bp.route("/time-off")
@role_required("manager")
def review_time_off():
    requests = get_db().execute(
        """
        SELECT o.*, u.name FROM time_off o JOIN users u ON u.id = o.user_id
        ORDER BY CASE o.status WHEN 'pending' THEN 0 ELSE 1 END, o.start_date DESC
        """
    ).fetchall()
    return render_template("manager_time_off.html", requests=requests)


@manager_bp.route("/time-off/<int:request_id>/<decision>", methods=("POST",))
@role_required("manager")
def decide_time_off(request_id, decision):
    validate_csrf()
    if decision not in {"approved", "rejected"}:
        flash("Invalid decision.", "error")
        return redirect(url_for("manager.review_time_off"))
    db = get_db()
    result = db.execute(
        """
        UPDATE time_off SET status = ?, manager_note = ?, reviewed_by = ?, reviewed_at = ?
        WHERE id = ? AND status = 'pending'
        """,
        (decision, request.form.get("manager_note", "").strip(), session["user_id"],
         datetime.now(timezone.utc).isoformat(), request_id),
    )
    db.commit()
    flash(f"Time-off request {decision}." if result.rowcount else "Request was already reviewed.",
          "success" if result.rowcount else "error")
    return redirect(url_for("manager.review_time_off"))
