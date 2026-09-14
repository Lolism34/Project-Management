DROP TABLE IF EXISTS correction_log;
DROP TABLE IF EXISTS payroll_records;
DROP TABLE IF EXISTS payroll_batches;
DROP TABLE IF EXISTS time_off;
DROP TABLE IF EXISTS time_entries;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('employee', 'manager')),
    timezone TEXT NOT NULL DEFAULT 'UTC',
    hourly_rate REAL NOT NULL DEFAULT 0 CHECK (hourly_rate >= 0),
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payroll_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE time_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    clock_in_utc TEXT NOT NULL,
    clock_out_utc TEXT NOT NULL,
    break_minutes INTEGER NOT NULL DEFAULT 0 CHECK (break_minutes >= 0),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'accepted', 'approved')),
    employee_note TEXT,
    manager_note TEXT,
    reviewed_by INTEGER,
    reviewed_at TEXT,
    payroll_batch_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (reviewed_by) REFERENCES users(id),
    FOREIGN KEY (payroll_batch_id) REFERENCES payroll_batches(id)
);

CREATE TABLE time_off (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    leave_type TEXT NOT NULL CHECK (
        leave_type IN ('PTO', 'Sick', 'Short-Term Disability', 'Unpaid')
    ),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    hours REAL NOT NULL CHECK (hours > 0),
    employee_note TEXT,
    manager_note TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewed_by INTEGER,
    reviewed_at TEXT,
    payroll_batch_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (reviewed_by) REFERENCES users(id),
    FOREIGN KEY (payroll_batch_id) REFERENCES payroll_batches(id)
);

CREATE TABLE correction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    manager_id INTEGER NOT NULL,
    old_clock_in_utc TEXT NOT NULL,
    old_clock_out_utc TEXT NOT NULL,
    new_clock_in_utc TEXT NOT NULL,
    new_clock_out_utc TEXT NOT NULL,
    reason TEXT NOT NULL,
    corrected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entry_id) REFERENCES time_entries(id),
    FOREIGN KEY (manager_id) REFERENCES users(id)
);

CREATE TABLE payroll_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    regular_hours REAL NOT NULL DEFAULT 0,
    paid_leave_hours REAL NOT NULL DEFAULT 0,
    hourly_rate REAL NOT NULL,
    gross_pay REAL NOT NULL,
    FOREIGN KEY (batch_id) REFERENCES payroll_batches(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE (batch_id, user_id)
);

CREATE INDEX idx_time_entries_user ON time_entries(user_id);
CREATE INDEX idx_time_entries_status ON time_entries(status);
CREATE INDEX idx_time_off_user ON time_off(user_id);
CREATE INDEX idx_time_off_status ON time_off(status);
