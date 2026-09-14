import sqlite3

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with current_app.open_resource("schema.sql") as schema:
        db.executescript(schema.read().decode("utf8"))
    seed_db(db)


def seed_db(db=None):
    db = db or get_db()
    users = [
        (
            "Demo Employee",
            "employee@hygrometry.com",
            generate_password_hash("Employee123!"),
            "employee",
            "America/Chicago",
            22.50,
        ),
        (
            "Demo Manager",
            "manager@hygrometry.com",
            generate_password_hash("Manager123!"),
            "manager",
            "America/Chicago",
            38.00,
        ),
    ]
    db.executemany(
        """
        INSERT OR IGNORE INTO users
        (name, email, password_hash, role, timezone, hourly_rate)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        users,
    )
    db.commit()


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Database initialized with demo accounts.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    with app.app_context():
        db = get_db()
        table = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        if table is None:
            init_db()
