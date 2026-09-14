import os
import sqlite3
import tempfile

import pytest

from app import create_app


@pytest.fixture()
def app():
    handle, path = tempfile.mkstemp()
    os.close(handle)
    application = create_app({"TESTING": True, "DATABASE": path, "SECRET_KEY": "test-key"})
    yield application
    os.unlink(path)


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "test-token"
    return "test-token"


def login(client, email, password):
    token = csrf(client)
    return client.post("/login", data={"csrf_token": token, "email": email, "password": password})


def test_employee_login_and_time_workflow(client, app):
    response = login(client, "employee@hygrometry.com", "Employee123!")
    assert response.status_code == 302
    token = csrf(client)
    response = client.post(
        "/employee/time",
        data={
            "csrf_token": token,
            "clock_in": "2026-09-14T08:00",
            "clock_out": "2026-09-14T16:30",
            "break_minutes": "30",
            "note": "Regular shift",
        },
        follow_redirects=True,
    )
    assert b"Time entry saved as a draft" in response.data
    with app.app_context():
        conn = sqlite3.connect(app.config["DATABASE"])
        entry_id = conn.execute("SELECT id FROM time_entries").fetchone()[0]
        conn.close()
    response = client.post(
        f"/employee/time/{entry_id}/accept",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    assert b"sent to your manager" in response.data


def test_manager_approves_time_and_creates_payroll(client, app):
    test_employee_login_and_time_workflow(client, app)
    token = csrf(client)
    client.post("/logout", data={"csrf_token": token})
    login(client, "manager@hygrometry.com", "Manager123!")
    token = csrf(client)
    with app.app_context():
        conn = sqlite3.connect(app.config["DATABASE"])
        entry_id = conn.execute("SELECT id FROM time_entries").fetchone()[0]
        conn.close()
    response = client.post(
        f"/manager/time/{entry_id}/approve",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    assert b"Time entry approved" in response.data
    response = client.post(
        "/payroll/create",
        data={"csrf_token": token, "period_start": "2026-09-14", "period_end": "2026-09-14"},
        follow_redirects=True,
    )
    assert b"Payroll batch created" in response.data
    assert b"$180.00" in response.data


def test_employee_cannot_open_manager_pages(client):
    login(client, "employee@hygrometry.com", "Employee123!")
    assert client.get("/manager").status_code == 403


def test_invalid_csrf_is_rejected(client):
    login(client, "employee@hygrometry.com", "Employee123!")
    response = client.post("/employee/time", data={"csrf_token": "wrong"})
    assert response.status_code == 400
