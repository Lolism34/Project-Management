from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database import get_db
from utils import validate_csrf

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        validate_csrf()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE email = ? AND active = 1", (email,)
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            session["timezone"] = user["timezone"]
            if user["role"] == "manager":
                return redirect(url_for("manager.dashboard"))
            return redirect(url_for("employee.dashboard"))

        flash("Email or password is incorrect.", "error")
    return render_template("login.html")


@auth_bp.route("/logout", methods=("POST",))
def logout():
    validate_csrf()
    session.clear()
    return redirect(url_for("auth.login"))
