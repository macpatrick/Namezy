"""
SQLite schema + connection helpers for Namezy.

Schema is modeled on the original brief's Projects / Candidates / Validation
tables, deliberately kept close to that shape (including unused, nullable
columns like `apple`, `play`, `trademark`, `social`, `risk`) so v2 can add
App Store / Play Store / trademark / social-handle checks without a schema
migration -- just start writing to columns that already exist.
"""
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "NAMEZY_DB_PATH", os.path.join(os.path.dirname(__file__), "namezy.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT,
    description TEXT NOT NULL,
    industry TEXT,
    personality_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    candidate TEXT NOT NULL,
    candidate_norm TEXT NOT NULL,
    method TEXT,
    score INTEGER,
    status TEXT DEFAULT 'active',
    favorite INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation (
    candidate_id INTEGER PRIMARY KEY REFERENCES candidates(id),
    domain_com TEXT,
    domain_io TEXT,
    domain_app TEXT,
    google TEXT,
    google_top_result TEXT,
    apple TEXT,
    play TEXT,
    trademark TEXT,
    social TEXT,
    risk TEXT,
    checked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_candidates_project ON candidates(project_id);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
