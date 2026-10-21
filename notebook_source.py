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

# %% [markdown]
# ### 3.3 Dates and matching
#
# Dates are parsed and validated in Python before they reach SQLite. Matching is a
# small token-overlap score, not semantic search, so the result is predictable.

# %%
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def parse_due_date(text: str, today: date | None = None):
    today = today or date.today()
    lowered = text.lower()

    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", lowered)
    if match:
        value = match.group(1)
        return (value, match.group(0), None) if is_valid_iso_date(value) else (None, match.group(0), "That date is not valid.")

    match = re.search(r"\b(today|tomorrow)\b", lowered)
    if match:
        offset = 0 if match.group(1) == "today" else 1
        return ((today + timedelta(days=offset)).isoformat(), match.group(0), None)

    match = re.search(r"\bin\s+(\d+)\s+(day|days|week|weeks)\b", lowered)
    if match:
        amount = int(match.group(1))
        if match.group(2).startswith("week"):
            amount *= 7
        return ((today + timedelta(days=amount)).isoformat(), match.group(0), None)

    match = re.search(r"\bnext\s+(" + "|".join(WEEKDAYS) + r")\b", lowered)
    if match:
        target = WEEKDAYS.index(match.group(1))
        days = (target - today.weekday()) % 7
        days = days or 7
        return ((today + timedelta(days=days)).isoformat(), match.group(0), None)

    match = re.search(r"\b(" + "|".join(WEEKDAYS) + r")\b", lowered)
    if match:
        target = WEEKDAYS.index(match.group(1))
        days = (target - today.weekday()) % 7
        return ((today + timedelta(days=days)).isoformat(), match.group(0), None)

    month_pattern = "|".join(MONTHS)
    match = re.search(r"\b(\d{1,2})\s+(" + month_pattern + r")\s+(\d{4})\b", lowered)
    if match:
        day, month_name, year = int(match.group(1)), match.group(2), int(match.group(3))
        try:
            value = date(year, MONTHS[month_name], day).isoformat()
            return (value, match.group(0), None)
        except ValueError:
            return (None, match.group(0), "That date is not valid.")

    match = re.search(r"\b(" + month_pattern + r")\s+(\d{1,2}),?\s+(\d{4})\b", lowered)
    if match:
        month_name, day, year = match.group(1), int(match.group(2)), int(match.group(3))
        try:
            value = date(year, MONTHS[month_name], day).isoformat()
            return (value, match.group(0), None)
        except ValueError:
            return (None, match.group(0), "That date is not valid.")

    match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", lowered)
    if match:
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            value = date(year, month, day).isoformat()
            return (value, match.group(0), None)
        except ValueError:
            return (None, match.group(0), "That date is not valid.")

    match = re.search(r"\b\d{1,2}(st|nd|rd|th)?\s+(of\s+)?(" + month_pattern + r")\b", lowered)
    if match:
        return (None, match.group(0), "That date is not valid. Use a real day and month.")

    return (None, None, None)


def extract_create_title(text: str, date_phrase: str | None) -> str:
    title = text.strip()
    title = re.sub(r"(?i)^\s*(please\s+)?(add|create|make|schedule)\s+(a\s+|an\s+)?(task|reminder|todo)\s*(to|for|:)?\s*", "", title)
    title = re.sub(r"(?i)^\s*remind\s+me\s+to\s+", "", title)
    title = re.sub(r"(?i)^\s*(i\s+need\s+to|i\s+have\s+to|remember\s+to)\s+", "", title)
    if date_phrase:
        title = re.sub(r"(?i)\s*\b(by|on|before|due|until)\b\s*" + re.escape(date_phrase), "", title)
        title = re.sub(r"(?i)\s*" + re.escape(date_phrase) + r"\s*$", "", title)
    title = title.strip(" .,!?:;")
    title = re.sub(r"\s+", " ", title)
    if not title:
        return ""
    return title[0].upper() + title[1:]


STOPWORDS = {"the", "a", "an", "my", "task", "please", "to", "for", "of"}


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def token_overlap(query: str, title: str) -> int:
    query_tokens = {token for token in normalize_text(query).split() if token not in STOPWORDS}
    title_tokens = {token for token in normalize_text(title).split() if token not in STOPWORDS}
    return len(query_tokens & title_tokens)


def find_tasks(phrase: str, status: str = "all", db_path: str = DB_PATH) -> list[dict]:
    phrase = phrase.strip()
    if not phrase:
        return []

    if phrase.isdigit():
        task = get_task(int(phrase), db_path)
        if task is None:
            return []
        if status == "all" or task["status"] == status:
            return [task]
        return []

    tasks = list_tasks(status, db_path)
    normalized_phrase = normalize_text(phrase)
    substring_matches = [
        task for task in tasks
        if normalized_phrase and normalized_phrase in normalize_text(task["title"])
    ]
    if substring_matches:
        return substring_matches

    scored = [(token_overlap(phrase, task["title"]), task) for task in tasks]
    best_score = max((score for score, _task in scored), default=0)
    if best_score == 0:
        return []
    return [task for score, task in scored if score == best_score]


