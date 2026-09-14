import os

from flask import Flask, redirect, session, url_for

import database
from auth import auth_bp
from employee import employee_bp
from manager import manager_bp
from payroll import payroll_bp
from utils import generate_csrf_token


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-this-key"),
        DATABASE=os.path.join(app.instance_path, "hygrometry.sqlite"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    database.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(manager_bp)
    app.register_blueprint(payroll_bp)
    app.jinja_env.globals["csrf_token"] = generate_csrf_token

    @app.route("/")
    def index():
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        if session.get("role") == "manager":
            return redirect(url_for("manager.dashboard"))
        return redirect(url_for("employee.dashboard"))

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
