# %% [markdown]
# # AI-Powered Personal Task Manager
#
# ## 1. Problem understanding and proposed approach
#
# ## 2. Tech stack and justification
#
# ## 3. Python implementation
#
# ### 3.1 Setup and optional imports
#
# ## 4. Sample inputs and outputs
#
# ## 5. Testing of core functionality and error handling
#
# ## 6. Limitations and possible improvements

# %%
import json
import os
import re
import sqlite3
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# %% [markdown]
# ### 3.2 Database
#
# Tasks live in a small SQLite table. Every call opens its own connection, so the
# tests and the notebook do not share stale state.

# %%
DB_PATH = os.getenv("TASK_DB_PATH", "tasks.db")


@contextmanager
def db_connection(db_path: str = DB_PATH):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db(db_path: str = DB_PATH) -> None:
    with db_connection(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")


def add_task(title: str, due_date: str, db_path: str = DB_PATH) -> dict:
    title = title.strip()
    if not title:
        return {"status": "error", "message": "Task title cannot be empty."}
    if len(title) > 200:
        return {"status": "error", "message": "Task title is too long. Keep it under 200 characters."}
    if not is_valid_iso_date(due_date):
        return {"status": "invalid_date", "message": "Use a real date in YYYY-MM-DD format."}
    now = datetime.now().isoformat(timespec="seconds")
    with db_connection(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, due_date, status, created_at) VALUES (?, ?, 'pending', ?)",
            (title, due_date, now),
        )
        task_id = cursor.lastrowid
    return {
        "status": "success",
        "message": f"Added '{title}' for {due_date}.",
        "data": {"task": get_task(task_id, db_path)},
    }


def is_valid_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False


def list_tasks(status: str = "pending", db_path: str = DB_PATH) -> list[dict]:
    if status == "all":
        query = "SELECT * FROM tasks ORDER BY due_date, id"
        params = ()
    else:
        query = "SELECT * FROM tasks WHERE status = ? ORDER BY due_date, id"
        params = (status,)
    with db_connection(db_path) as connection:
        rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_task(task_id: int, db_path: str = DB_PATH) -> dict | None:
    with db_connection(db_path) as connection:
        row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row is not None else None


def complete_task(task_id: int, db_path: str = DB_PATH) -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    with db_connection(db_path) as connection:
        cursor = connection.execute(
            "UPDATE tasks SET status = 'completed', completed_at = ? "
            "WHERE id = ? AND status = 'pending'",
            (now, task_id),
        )
        changed = cursor.rowcount
    return changed == 1

