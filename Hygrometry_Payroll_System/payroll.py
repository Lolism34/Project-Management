import csv
import io
from datetime import date

from flask import Blueprint, Response, flash, redirect, render_template, request, session, url_for

from database import get_db
from utils import hours_between, role_required, validate_csrf

payroll_bp = Blueprint("payroll", __name__, url_prefix="/payroll")


@payroll_bp.route("")
@role_required("manager")
def dashboard():
    db = get_db()
    batches = db.execute(
        """
        SELECT b.*, u.name AS created_by_name, COUNT(r.id) AS employee_count,
               COALESCE(SUM(r.gross_pay), 0) AS total_gross
        FROM payroll_batches b
        JOIN users u ON u.id = b.created_by
        LEFT JOIN payroll_records r ON r.batch_id = b.id
        GROUP BY b.id ORDER BY b.created_at DESC
        """
    ).fetchall()
    return render_template("payroll.html", batches=batches)


@payroll_bp.route("/create", methods=("POST",))
@role_required("manager")
def create_batch():
    validate_csrf()
    try:
        period_start = date.fromisoformat(request.form["period_start"])
        period_end = date.fromisoformat(request.form["period_end"])
        if period_end < period_start:
            raise ValueError("Payroll end date must follow its start date.")
    except (ValueError, KeyError) as exc:
        flash(str(exc), "error")
        return redirect(url_for("payroll.dashboard"))

    db = get_db()
    entries = db.execute(
        """
        SELECT t.*, u.hourly_rate, u.id AS employee_id
        FROM time_entries t JOIN users u ON u.id = t.user_id
        WHERE t.status = 'approved' AND t.payroll_batch_id IS NULL
          AND date(t.clock_in_utc) BETWEEN ? AND ?
        """,
        (str(period_start), str(period_end)),
    ).fetchall()
    leave = db.execute(
        """
        SELECT o.*, u.hourly_rate, u.id AS employee_id
        FROM time_off o JOIN users u ON u.id = o.user_id
        WHERE o.status = 'approved' AND o.leave_type != 'Unpaid'
          AND o.payroll_batch_id IS NULL AND o.start_date BETWEEN ? AND ?
        """,
        (str(period_start), str(period_end)),
    ).fetchall()
    if not entries and not leave:
        flash("No approved, unprocessed records exist for this period.", "error")
        return redirect(url_for("payroll.dashboard"))

    cursor = db.execute(
        "INSERT INTO payroll_batches (period_start, period_end, created_by) VALUES (?, ?, ?)",
        (str(period_start), str(period_end), session["user_id"]),
    )
    batch_id = cursor.lastrowid
    totals = {}
    for entry in entries:
        employee = totals.setdefault(
            entry["employee_id"], {"regular": 0, "leave": 0, "rate": entry["hourly_rate"]}
        )
        employee["regular"] += hours_between(
            entry["clock_in_utc"], entry["clock_out_utc"], entry["break_minutes"]
        )
        db.execute("UPDATE time_entries SET payroll_batch_id = ? WHERE id = ?", (batch_id, entry["id"]))
    for item in leave:
        employee = totals.setdefault(
            item["employee_id"], {"regular": 0, "leave": 0, "rate": item["hourly_rate"]}
        )
        employee["leave"] += item["hours"]
        db.execute("UPDATE time_off SET payroll_batch_id = ? WHERE id = ?", (batch_id, item["id"]))
    for user_id, total in totals.items():
        gross = round((total["regular"] + total["leave"]) * total["rate"], 2)
        db.execute(
            """
            INSERT INTO payroll_records
            (batch_id, user_id, regular_hours, paid_leave_hours, hourly_rate, gross_pay)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (batch_id, user_id, round(total["regular"], 2), round(total["leave"], 2),
             total["rate"], gross),
        )
    db.commit()
    flash("Payroll batch created and approved records transferred.", "success")
    return redirect(url_for("payroll.dashboard"))


@payroll_bp.route("/<int:batch_id>/export")
@role_required("manager")
def export_batch(batch_id):
    db = get_db()
    batch = db.execute("SELECT * FROM payroll_batches WHERE id = ?", (batch_id,)).fetchone()
    if not batch:
        return "Payroll batch not found.", 404
    rows = db.execute(
        """
        SELECT u.name, u.email, r.regular_hours, r.paid_leave_hours,
               r.hourly_rate, r.gross_pay
        FROM payroll_records r JOIN users u ON u.id = r.user_id
        WHERE r.batch_id = ? ORDER BY u.name
        """,
        (batch_id,),
    ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Employee", "Email", "Regular Hours", "Paid Leave Hours", "Rate", "Gross Pay"])
    for row in rows:
        writer.writerow(list(row))
    filename = f"payroll_{batch['period_start']}_{batch['period_end']}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
