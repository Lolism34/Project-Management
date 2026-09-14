import secrets
from datetime import datetime, timezone
from functools import wraps
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import abort, flash, redirect, request, session, url_for


def generate_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(24)
    return session["csrf_token"]


def validate_csrf():
    sent = request.form.get("csrf_token", "")
    stored = session.get("csrf_token", "")
    if not sent or not stored or not secrets.compare_digest(sent, stored):
        abort(400, "Invalid form token.")


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("user_id"):
            flash("Log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(**kwargs)

    return wrapped_view


def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped_view(**kwargs):
            if session.get("role") != role:
                abort(403)
            return view(**kwargs)

        return wrapped_view

    return decorator


def local_to_utc(value, timezone_name):
    try:
        local_zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Select a valid time zone.") from exc
    try:
        local_time = datetime.fromisoformat(value).replace(tzinfo=local_zone)
    except ValueError as exc:
        raise ValueError("Enter a valid date and time.") from exc
    return local_time.astimezone(timezone.utc).isoformat()


def utc_to_local(value, timezone_name):
    if not value:
        return ""
    utc_time = datetime.fromisoformat(value)
    return utc_time.astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %I:%M %p")


def hours_between(start, end, break_minutes=0):
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    hours = (end_dt - start_dt).total_seconds() / 3600 - break_minutes / 60
    return round(max(0, hours), 2)
