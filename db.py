"""SQLite storage for the job board bot."""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "/data/jobs.db")


@contextmanager
def _conn():
    # Ensure parent dir exists (Railway volume mounts at /data)
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                username    TEXT,
                title       TEXT NOT NULL,
                short_desc  TEXT NOT NULL,
                full_desc   TEXT NOT NULL,
                budget      TEXT,
                contact     TEXT NOT NULL,
                message_id  INTEGER,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_user ON jobs(user_id)")
        # Migration for existing deployments that pre-date the budget column
        cols = {row["name"] for row in c.execute("PRAGMA table_info(jobs)").fetchall()}
        if "budget" not in cols:
            c.execute("ALTER TABLE jobs ADD COLUMN budget TEXT")


def create_job(user_id, username, title, short_desc, full_desc, budget, contact) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO jobs (user_id, username, title, short_desc, full_desc, budget, contact) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, title, short_desc, full_desc, budget, contact),
        )
        return cur.lastrowid


def set_message_id(job_id: int, message_id: int):
    with _conn() as c:
        c.execute("UPDATE jobs SET message_id = ? WHERE id = ?", (message_id, job_id))


def get_job(job_id: int):
    with _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def get_user_jobs(user_id: int):
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_job(job_id: int):
    with _conn() as c:
        c.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
