from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from database import get_db
from utils import hours_between, local_to_utc, role_required, utc_to_local, validate_csrf

employee_bp = Blueprint("employee", __name__)


@employee_bp.route("/employee")
@role_required("employee")
def dashboard():
    db = get_db()
    user_id = session["user_id"]
    summary = db.execute(
        """
        SELECT
          COUNT(*) AS entry_count,
          SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved_count,
          SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) AS waiting_count
        FROM time_entries WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    recent = db.execute(
        "SELECT * FROM time_entries WHERE user_id = ? ORDER BY clock_in_utc DESC LIMIT 5",
        (user_id,),
    ).fetchall()
    entries = [dict(row) for row in recent]
    for entry in entries:
        entry["local_start"] = utc_to_local(entry["clock_in_utc"], session["timezone"])
        entry["local_end"] = utc_to_local(entry["clock_out_utc"], session["timezone"])
        entry["hours"] = hours_between(
            entry["clock_in_utc"], entry["clock_out_utc"], entry["break_minutes"]
        )
    return render_template("employee_dashboard.html", summary=summary, entries=entries)


@employee_bp.route("/employee/time", methods=("GET", "POST"))
@role_required("employee")
def time_entries():
    db = get_db()
    user_id = session["user_id"]
    if request.method == "POST":
        validate_csrf()
        try:
            start = local_to_utc(request.form["clock_in"], session["timezone"])
            end = local_to_utc(request.form["clock_out"], session["timezone"])
            break_minutes = int(request.form.get("break_minutes", 0))
            if hours_between(start, end, break_minutes) <= 0:
                raise ValueError("Clock-out must occur after clock-in and the break.")
            if break_minutes < 0:
                raise ValueError("Break minutes cannot be negative.")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "error")
        else:
            db.execute(
                """
                INSERT INTO time_entries
                (user_id, clock_in_utc, clock_out_utc, break_minutes, employee_note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, start, end, break_minutes, request.form.get("note", "").strip()),
            )
            db.commit()
            flash("Time entry saved as a draft.", "success")
            return redirect(url_for("employee.time_entries"))

    rows = db.execute(
        "SELECT * FROM time_entries WHERE user_id = ? ORDER BY clock_in_utc DESC",
        (user_id,),
    ).fetchall()
    entries = [dict(row) for row in rows]
    for entry in entries:
        entry["local_start"] = utc_to_local(entry["clock_in_utc"], session["timezone"])
        entry["local_end"] = utc_to_local(entry["clock_out_utc"], session["timezone"])
        entry["hours"] = hours_between(
            entry["clock_in_utc"], entry["clock_out_utc"], entry["break_minutes"]
        )
    return render_template("time_entries.html", entries=entries)


@employee_bp.route("/employee/time/<int:entry_id>/accept", methods=("POST",))
@role_required("employee")
def accept_time(entry_id):
    validate_csrf()
    db = get_db()
    result = db.execute(
        "UPDATE time_entries SET status = 'accepted' WHERE id = ? AND user_id = ? AND status = 'draft'",
        (entry_id, session["user_id"]),
    )
    db.commit()
    flash("Time entry sent to your manager." if result.rowcount else "Entry could not be submitted.",
          "success" if result.rowcount else "error")
    return redirect(url_for("employee.time_entries"))


@employee_bp.route("/employee/time-off", methods=("GET", "POST"))
@role_required("employee")
def time_off():
    db = get_db()
    user_id = session["user_id"]
    if request.method == "POST":
        validate_csrf()
        try:
            start_date = date.fromisoformat(request.form["start_date"])
            end_date = date.fromisoformat(request.form["end_date"])
            hours = float(request.form["hours"])
            if end_date < start_date or hours <= 0:
                raise ValueError("Enter a valid date range and number of hours.")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "error")
        else:
            db.execute(
                """
                INSERT INTO time_off
                (user_id, leave_type, start_date, end_date, hours, employee_note)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, request.form["leave_type"], str(start_date), str(end_date), hours,
                 request.form.get("note", "").strip()),
            )
            db.commit()
            flash("Time-off request sent to your manager.", "success")
            return redirect(url_for("employee.time_off"))

    requests = db.execute(
        "SELECT * FROM time_off WHERE user_id = ? ORDER BY start_date DESC", (user_id,)
    ).fetchall()
    return render_template("time_off.html", requests=requests)
