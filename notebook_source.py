# %% [markdown]
# # AI-Powered Personal Task Manager
#
# ## 1. Problem understanding and proposed approach
#
# A personal task manager should remove the friction between thinking of a task and
# recording it. Typing into a form is slow, and a wall of text messages is hard to
# query. This notebook accepts short natural-language requests such as
# "add a task to submit the GenAI assignment by tomorrow" and turns them into
# structured SQLite rows.
#
# The approach is deliberately small:
#
# 1. The user sends a message.
# 2. The agent asks an OpenAI-compatible chat model for a tool call.
# 3. Python validates the arguments and executes exactly one of four tools.
# 4. The tool result goes back to the model for a short confirmation.
# 5. If the model is unavailable, a deterministic local parser handles the same
#    common requests, so the notebook still works without a key.
#
# Scope: single user, local database, English requests, four operations. The agent
# never deletes data, never invents a due date, and asks a follow-up question when
# a request is ambiguous.
#
# ## 2. Tech stack and justification
#
# | Layer | Choice | Why |
# |---|---|---|
# | Interface | Jupyter notebook | The assignment asks for a runnable notebook; cells show each layer. |
# | Language | Python 3.10+ | Simple standard-library SQLite, dataclasses, and type hints. |
# | Storage | SQLite | Zero setup, one file, transactions, and enough SQL for this scope. |
# | Model | OpenAI-compatible chat completions | The same SDK works with NVIDIA's endpoint and a local fake in tests. |
# | Fallback | Deterministic parser | Keeps the notebook usable offline and makes tests fast and stable. |
# | Tests | pytest | Plain functions, temporary databases, no network. |
# | Notebook source | jupytext | Keeps source reviewable in Git while still producing an executed `.ipynb`. |
#
# ## 3. Python implementation
#
# ### 3.1 Setup and optional imports

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


def reset_database(db_path: str = DB_PATH) -> None:
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)


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

# %% [markdown]
# ### 3.4 Tools and result shape
#
# The model chooses one tool. Python validates the arguments, calls SQLite, and
# returns a small dictionary with a status, a message, and optional data.

# %%
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Create a task with a title and a due date. Omit due_date if the user did not give one; the tool will ask for it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short task title."},
                    "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format. Omit it if the user did not give one."},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List tasks by status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["pending", "completed", "all"]},
                },
                "required": ["status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark one task as completed. Use a title fragment or task ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_ref": {"type": "string", "description": "Title fragment or numeric task ID."},
                },
                "required": ["task_ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_task_details",
            "description": "Get the due date and status of one task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_ref": {"type": "string", "description": "Title fragment or numeric task ID."},
                },
                "required": ["task_ref"],
            },
        },
    },
]


def tool_add_task(title: str, due_date: str | None = None, db_path: str = DB_PATH) -> dict:
    title = (title or "").strip()
    if not title:
        return {"status": "error", "message": "Task title cannot be empty."}
    if due_date is None or not str(due_date).strip():
        return {
            "status": "needs_due_date",
            "message": f"What due date should I use for '{title}'?",
        }
    return add_task(title, due_date, db_path)


def tool_list_tasks(status: str = "pending", db_path: str = DB_PATH) -> dict:
    if status not in {"pending", "completed", "all"}:
        return {"status": "error", "message": "Status must be pending, completed, or all."}
    tasks = list_tasks(status, db_path)
    for task in tasks:
        task["overdue"] = task["status"] == "pending" and task["due_date"] < date.today().isoformat()
    if not tasks:
        message = "No tasks yet." if status == "all" else f"No {status} tasks."
    elif status == "all":
        message = f"Found {len(tasks)} task(s)."
    else:
        message = f"Found {len(tasks)} {status} task(s)."
    return {"status": "success", "message": message, "data": {"tasks": tasks}}


def tool_complete_task(task_ref: str, db_path: str = DB_PATH) -> dict:
    task_ref = (task_ref or "").strip()
    if not task_ref:
        return {"status": "error", "message": "Tell me which task to complete."}
    matches = find_tasks(task_ref, status="pending", db_path=db_path)
    if len(matches) > 1:
        return {
            "status": "ambiguous",
            "message": f"I found {len(matches)} tasks. Which one?",
            "data": {"candidates": [{"id": task["id"], "title": task["title"]} for task in matches]},
        }
    if not matches:
        completed = find_tasks(task_ref, status="completed", db_path=db_path)
        if len(completed) == 1:
            return {"status": "already_completed", "message": f"'{completed[0]['title']}' is already completed.", "data": {"task": completed[0]}}
        return {"status": "not_found", "message": f"I could not find a pending task matching '{task_ref}'.", "data": {"suggestions": suggestions_for(task_ref, db_path)}}
    task = matches[0]
    complete_task(task["id"], db_path)
    return {"status": "success", "message": f"Marked '{task['title']}' as completed.", "data": {"task": get_task(task["id"], db_path)}}


def tool_get_task_details(task_ref: str, db_path: str = DB_PATH) -> dict:
    task_ref = (task_ref or "").strip()
    if not task_ref:
        return {"status": "error", "message": "Tell me which task to look up."}
    matches = find_tasks(task_ref, status="all", db_path=db_path)
    if len(matches) > 1:
        return {
            "status": "ambiguous",
            "message": f"I found {len(matches)} tasks. Which one?",
            "data": {"candidates": [{"id": task["id"], "title": task["title"]} for task in matches]},
        }
    if not matches:
        return {"status": "not_found", "message": f"I could not find a task matching '{task_ref}'.", "data": {"suggestions": suggestions_for(task_ref, db_path)}}
    task = matches[0]
    return {
        "status": "success",
        "message": f"'{task['title']}' is {task['status']} and due on {task['due_date']}.",
        "data": {"task": task},
    }


def suggestions_for(phrase: str, db_path: str = DB_PATH) -> list[dict]:
    scored = [
        (token_overlap(phrase, task["title"]), task)
        for task in list_tasks("pending", db_path)
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {"id": task["id"], "title": task["title"]}
        for score, task in scored
        if score > 0
    ][:3]


TOOL_FUNCTIONS = {
    "add_task": tool_add_task,
    "list_tasks": tool_list_tasks,
    "complete_task": tool_complete_task,
    "get_task_details": tool_get_task_details,
}


def execute_tool(name: str, arguments: dict, db_path: str = DB_PATH) -> dict:
    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return {"status": "error", "message": f"Unknown tool: {name}"}
    if not isinstance(arguments, dict):
        return {"status": "error", "message": "Tool arguments must be an object."}
    try:
        return function(db_path=db_path, **arguments)
    except TypeError as error:
        return {"status": "error", "message": f"Invalid tool arguments: {error}"}
    except Exception as error:
        return {"status": "error", "message": f"Tool failed: {error}"}

# %% [markdown]
# ### 3.5 Local parser
#
# The parser recognizes common requests without an API key. It is deliberately
# narrow: anything it does not understand returns None and gets a friendly reply.

# %%
def extract_reference(text: str, leading_phrases: list[str]) -> str:
    quoted = re.search(r"""['"]([^'"]+)['"]""", text)
    if quoted:
        return quoted.group(1).strip(" .,!?:;")

    value = text.strip(" .,!?:;")
    value = re.sub(r"(?i)^\s*please\s+", "", value)
    for phrase in sorted(leading_phrases, key=len, reverse=True):
        value = re.sub(r"(?i)^\s*" + re.escape(phrase) + r"\b\s*", "", value)

    for _ in range(2):
        value = re.sub(
            r"(?i)\s+(and\s+)?(is\s+it\s+)?(as\s+)?(done|completed|complete|overdue|pending|due)\s*$",
            "",
            value,
        )

    value = re.sub(r"(?i)^\s*(the|my)\s+", "", value)
    return value.strip(" .,!?:;")


def parse_local_intent(text: str, today: date | None = None):
    today = today or date.today()
    lowered = text.lower().strip()

    details_request = (
        re.search(r"\b(when|details?|status|due)\b", lowered)
        or re.search(r"\bis\b.*\b(done|completed)\b", lowered)
    )
    if details_request and re.search(r"\b(task|assignment|it)\b", lowered):
        task_ref = extract_reference(
            text, ["when is", "when's", "details of", "details for", "status of", "is"]
        )
        if task_ref:
            return {"name": "get_task_details", "arguments": {"task_ref": task_ref}}

    if re.search(r"\b(add|create|make|schedule|remind me to|i need to|i have to|remember to)\b", lowered):
        iso_date, phrase, date_error = parse_due_date(lowered, today)
        title = extract_create_title(text, phrase)
        if date_error:
            return {"name": "add_task", "arguments": {"title": title, "due_date": "__invalid__"}}
        return {"name": "add_task", "arguments": {"title": title, "due_date": iso_date}}

    if re.search(r"\b(mark|complete|finish|done)\b", lowered) and re.search(r"\b(task|assignment|it)\b", lowered):
        task_ref = extract_reference(text, ["mark", "complete", "finish"])
        if task_ref:
            return {"name": "complete_task", "arguments": {"task_ref": task_ref}}

    if re.search(r"\b(show|list|display|see|what are)\b", lowered) and re.search(r"\b(task|tasks|todo|pending|completed|done)\b", lowered):
        if re.search(r"\b(pending|to do|todo)\b", lowered):
            status = "pending"
        elif re.search(r"\b(completed|done)\b", lowered):
            status = "completed"
        elif re.search(r"\ball\b", lowered):
            status = "all"
        else:
            status = "pending"
        return {"name": "list_tasks", "arguments": {"status": status}}

    return None

# %% [markdown]
# ### 3.6 LLM client
#
# The client is optional. It points the OpenAI SDK at an OpenAI-compatible base URL
# and returns one of three shapes: tool calls, text, or an error.

# %%
@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    label: str


def load_llm_configs() -> list[LLMConfig]:
    if load_dotenv is not None:
        load_dotenv()
    configs = []
    primary_key = os.getenv("LLM_API_KEY", "").strip()
    primary_base = os.getenv("LLM_BASE_URL", "").strip()
    primary_model = os.getenv("LLM_MODEL", "").strip()
    if primary_key and primary_base and primary_model:
        configs.append(LLMConfig(primary_key, primary_base, primary_model, "primary"))
    fallback_key = os.getenv("LLM_FALLBACK_API_KEY", "").strip()
    fallback_base = os.getenv("LLM_FALLBACK_BASE_URL", "").strip()
    fallback_model = os.getenv("LLM_FALLBACK_MODEL", "").strip()
    if fallback_key and fallback_base and fallback_model:
        configs.append(LLMConfig(fallback_key, fallback_base, fallback_model, "fallback"))
    return configs


def call_llm(messages: list[dict], tools: list[dict], configs: list[LLMConfig] | None = None) -> dict:
    configs = configs if configs is not None else load_llm_configs()
    if not configs:
        return {"type": "unavailable", "message": "No LLM configured."}
    if OpenAI is None:
        return {"type": "unavailable", "message": "The openai package is not installed."}
    last_error = ""
    for config in configs:
        try:
            client = OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=30.0, max_retries=2)
            response = client.chat.completions.create(
                model=config.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0,
            )
            message = response.choices[0].message
            if message.tool_calls:
                return {
                    "type": "tool_calls",
                    "provider": config.label,
                    "calls": [
                        {"id": call.id, "name": call.function.name, "arguments": json.loads(call.function.arguments)}
                        for call in message.tool_calls
                    ],
                }
            if message.content:
                return {"type": "text", "provider": config.label, "content": message.content}
            last_error = "The provider returned an empty response."
        except json.JSONDecodeError:
            return {"type": "error", "message": "The model returned invalid JSON for the tool arguments."}
        except Exception as error:
            last_error = f"{config.label} failed: {type(error).__name__}"
    return {"type": "error", "message": last_error}


class FakeLLM:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)

    def __call__(self, messages: list[dict], tools: list[dict]) -> dict:
        if not self.responses:
            return {"type": "error", "message": "No fake responses left."}
        return self.responses.pop(0)

# %% [markdown]
# ### 3.7 Agent loop
#
# The agent decides between a model call and the local parser. Tool results stay
# inside the agent loop. Only the final user-facing reply is returned.

# %%
SYSTEM_PROMPT = """You are a concise task manager.

Rules:
- Use one tool at a time.
- Ask for a due date if the user does not give one.
- Never invent a task ID or a due date.
- If the user asks for details, use get_task_details.
- Keep final replies short and plain.
"""


class Agent:
    def __init__(self, db_path: str = DB_PATH, today: date | None = None, llm_call=None):
        self.db_path = db_path
        self.today = today or date.today()
        self.llm_call = llm_call or call_llm
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.fallback_used = False
        self.last_tool_calls = []
        self.last_tool_results = []

    def chat(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})
        self.fallback_used = False
        self.last_tool_calls = []
        self.last_tool_results = []
        tools_used = False
        for _step in range(5):
            result = self.llm_call(to_openai_messages(self.messages), TOOLS)
            if result.get("type") == "tool_calls":
                calls = result.get("calls") or []
                if not calls:
                    return self._local_reply(user_text)
                tools_used = True
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": call["id"],
                                "type": "function",
                                "function": {
                                    "name": call["name"],
                                    "arguments": json.dumps(call["arguments"]),
                                },
                            }
                            for call in calls
                        ],
                    }
                )
                for call in calls:
                    tool_result = execute_tool(call["name"], call["arguments"], db_path=self.db_path)
                    self.last_tool_calls.append({"name": call["name"], "arguments": call["arguments"]})
                    self.last_tool_results.append(tool_result)
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "name": call["name"],
                            "content": json.dumps(tool_result),
                        }
                    )
                continue
            if result.get("type") == "text":
                if tools_used:
                    self.messages.append({"role": "assistant", "content": result["content"]})
                    return result["content"]
                return self._local_reply(user_text)
            return self._local_reply(user_text)

        return "I stopped after several tool steps. Please say that in a simpler way."

    def _local_reply(self, user_text: str) -> str:
        self.fallback_used = True
        call = parse_local_intent(user_text, self.today)
        if call is None:
            return "I can add, list, complete, or show details for tasks. Try: add task buy milk by tomorrow."
        result = execute_tool(call["name"], call["arguments"], db_path=self.db_path)
        self.last_tool_calls.append({"name": call["name"], "arguments": call["arguments"]})
        self.last_tool_results.append(result)
        if result.get("status") == "invalid_date":
            return "That date is not valid. Use a real date such as 2026-10-22."
        return self._reply_from_results([result])

    def _reply_from_results(self, results: list[dict]) -> str:
        lines = []
        for result in results:
            status = result.get("status")
            data = result.get("data") or {}
            if status in {"success", "already_completed"} and "tasks" in data:
                lines.append(result["message"])
                for task in data["tasks"]:
                    marker = " (overdue)" if task.get("overdue") else ""
                    lines.append(f"- #{task['id']} {task['title']} â€” {task['status']}, due {task['due_date']}{marker}")
            elif status in {"success", "already_completed"}:
                lines.append("Done: " + result["message"])
            elif status == "needs_due_date":
                lines.append(result["message"])
            elif status == "ambiguous":
                lines.append(result["message"])
                lines.extend(f"- #{task['id']} {task['title']}" for task in result.get("data", {}).get("candidates", []))
            elif status == "not_found":
                lines.append(result["message"])
                suggestions = result.get("data", {}).get("suggestions", [])
                if suggestions:
                    lines.append("Did you mean:")
                    lines.extend(f"- {task['title']} (due {task['due_date']})" for task in suggestions)
            elif status == "invalid_date":
                lines.append("That date is not valid. Use a real date such as 2026-10-22.")
            elif status == "error":
                lines.append(result["message"])
            else:
                lines.append(str(result))
        return "\n".join(lines)


def to_openai_messages(messages: list[dict]) -> list[dict]:
    converted = []
    for item in messages:
        role = item.get("role")
        if role == "system":
            content = item.get("content")
            if isinstance(content, list):
                content = "\n".join(str(part) for part in content)
            converted.append({"role": "system", "content": content or ""})
        elif role == "tool":
            converted.append({"role": "tool", "tool_call_id": item["tool_call_id"], "content": item.get("content", "")})
        else:
            converted.append({key: value for key, value in item.items() if key in {"role", "content", "tool_calls"}})
    return converted

# %% [markdown]
# ### 3.8 Evaluation
#
# These cases run against fresh temporary databases. The offline parser is enough
# to exercise every tool and every main failure path.

# %%
EVAL_CASES = [
    {"id": "add_relative", "text": "Add a task to submit the GenAI assignment by tomorrow.", "expected_tool": "add_task", "expected_status": "success", "expected_due": "2026-10-22", "expected_reply_contains": ["submit"]},
    {"id": "add_missing_due", "text": "Add a task to buy groceries.", "expected_tool": "add_task", "expected_status": "needs_due_date", "expected_reply_contains": ["due date"]},
    {"id": "list_pending_empty", "text": "Show me all my pending tasks.", "expected_tool": "list_tasks", "expected_status": "success", "expected_arguments": {"status": "pending"}, "expected_reply_contains": ["No pending tasks"]},
    {"id": "list_pending", "text": "Show me all my pending tasks.", "setup": [{"title": "Read chapter", "due": "2026-10-22"}], "expected_tool": "list_tasks", "expected_status": "success", "expected_arguments": {"status": "pending"}, "expected_reply_contains": ["Read chapter"]},
    {"id": "complete_by_title", "text": "Mark the Python assignment as completed.", "setup": [{"title": "Python assignment", "due": "2026-10-25"}], "expected_tool": "complete_task", "expected_status": "success", "expected_reply_contains": ["Python assignment"]},
    {"id": "details_due", "text": "When is the GenAI assignment due?", "setup": [{"title": "GenAI assignment", "due": "2026-10-22"}], "expected_tool": "get_task_details", "expected_status": "success", "expected_due": "2026-10-22", "expected_reply_contains": ["2026-10-22"]},
    {"id": "unknown_request", "text": "Tell me a joke.", "expected_tool": None, "expected_status": None, "expected_reply_contains": ["I can add"]},
    {"id": "invalid_date", "text": "Add a task to buy milk by 32nd of Feb.", "expected_tool": "add_task", "expected_status": "invalid_date", "expected_reply_contains": ["not valid"]},
    {"id": "ambiguous_complete", "text": "Complete the Python assignment.", "setup": [{"title": "Python assignment", "due": "2026-10-22"}, {"title": "Python assignment notes", "due": "2026-10-23"}], "expected_tool": "complete_task", "expected_status": "ambiguous", "expected_reply_contains": ["Which one"]},
    {"id": "already_completed", "text": "Complete Python assignment.", "setup": [{"title": "Python assignment", "due": "2026-10-22", "completed": True}], "expected_tool": "complete_task", "expected_status": "already_completed", "expected_reply_contains": ["already completed"]},
    {"id": "complete_not_found", "text": "Complete the chemistry lab assignment.", "expected_tool": "complete_task", "expected_status": "not_found", "expected_reply_contains": ["could not find"]},
    {"id": "list_all", "text": "Show me all tasks.", "setup": [{"title": "Read chapter", "due": "2026-10-22"}], "expected_tool": "list_tasks", "expected_status": "success", "expected_arguments": {"status": "all"}, "expected_reply_contains": ["Read chapter"]},
]


def run_eval_cases(cases: list[dict] | None = None, llm_call=None) -> list[dict]:
    cases = cases if cases is not None else EVAL_CASES
    offline = llm_call or (lambda messages, tools: {"type": "unavailable"})
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for case in cases:
            db_path = os.path.join(tmp, f"{case['id']}.db")
            reset_database(db_path)
            for setup in case.get("setup", []):
                added = add_task(setup["title"], setup["due"], db_path)
                if setup.get("completed"):
                    complete_task(added["data"]["task"]["id"], db_path)
            agent = Agent(db_path=db_path, today=date(2026, 10, 21), llm_call=offline)
            reply = agent.chat(case["text"])
            call = agent.last_tool_calls[-1] if agent.last_tool_calls else None
            result = agent.last_tool_results[-1] if agent.last_tool_results else {}
            checks = {}
            checks["tool"] = (call or {}).get("name") == case.get("expected_tool")
            checks["status"] = (result or {}).get("status") == case.get("expected_status")
            if case.get("expected_due"):
                task = (result.get("data") or {}).get("task") or {}
                checks["due"] = task.get("due_date") == case["expected_due"]
            for key, value in case.get("expected_arguments", {}).items():
                checks[f"argument:{key}"] = (call or {}).get("arguments", {}).get(key) == value
            if case.get("expected_reply_contains"):
                checks["reply"] = all(needle.lower() in reply.lower() for needle in case["expected_reply_contains"])
            results.append(
                {
                    "id": case["id"],
                    "passed": all(checks.values()),
                    "checks": checks,
                    "reply": reply,
                }
            )
    return results

# %% [markdown]
# ## 4. Sample inputs and outputs
#
# The demo below uses a temporary database and the offline parser. It never touches
# `tasks.db`. With an LLM configured, the same messages go through the model first.

# %%
demo_db = os.path.join(tempfile.gettempdir(), "task_manager_demo.db")
reset_database(demo_db)
demo_agent = Agent(
    db_path=demo_db,
    today=date(2026, 10, 21),
    llm_call=lambda messages, tools: {"type": "unavailable"},
)

for message in [
    "Add a task to submit the GenAI assignment by tomorrow.",
    "Add a task to buy milk.",
    "Add a task to finish the Python assignment by 2026-10-28.",
    "Show me all my pending tasks.",
    "When is the GenAI assignment due?",
    "Mark the Python assignment as completed.",
    "Tell me a joke.",
]:
    print(f"User:  {message}")
    print(f"Agent: {demo_agent.chat(message)}")
    print()

# %% [markdown]
# Expected shape:
#
# - The first request creates a task with due date `2026-10-22`.
# - The second request asks for a due date instead of inventing one.
# - The list includes the generated task ID, status, and due date.
# - The details request reports the stored due date and status.
# - The completion request completes the only matching task.
# - The unknown request gets a short capability message.

# %% [markdown]
# ## 5. Testing of core functionality and error handling
#
# `pytest` covers the database, date parsing, task matching, every tool, the local
# parser, the LLM client seams, the agent loop, and all twelve evaluation cases.
# The evaluation cell below runs the same twelve cases in fresh temporary databases.

# %%
eval_results = run_eval_cases()
passed = sum(1 for result in eval_results if result["passed"])
print(f"{passed}/{len(eval_results)} evaluation cases passed")
for result in eval_results:
    marker = "PASS" if result["passed"] else "FAIL"
    print(f"{marker}  {result['id']}")
    if not result["passed"]:
        print(f"      checks: {result['checks']}")
        print(f"      reply:  {result['reply']}")

# %% [markdown]
# Error paths demonstrated by the tests:
#
# | Case | Expected behavior |
# |---|---|
# | Missing due date | `needs_due_date`; no row is written. |
# | Impossible date such as `2026-02-30` | `invalid_date`; the user is asked for a real date. |
# | Ambiguous title | `ambiguous` with candidate IDs and titles. |
# | Unknown title | `not_found` with up to three suggestions. |
# | Already completed | `already_completed`; the row is unchanged. |
# | Unknown tool or bad arguments | `error`; the agent does not crash. |
#
# ## 6. Limitations and possible improvements
#
# Limitations:
#
# - Single user and a local SQLite file; no accounts, sync, or concurrency control.
# - Matching is token overlap, not semantic search, so unusual paraphrases can miss.
# - The local parser understands a small set of English patterns and date phrases.
# - No reminders, recurrence, time zones, priorities, tags, or calendar integration.
# - The optional LLM path needs network access and a provider key; it is not tested
#   against a live provider in the automated suite.
#
# Possible improvements:
#
# - Add embeddings or fuzzy ranking for task matching, with a confidence threshold.
# - Add `update_task`, `delete_task`, and an undo window.
# - Add recurring tasks and reminders through a scheduler.
# - Store an audit log of every tool call and its result.
# - Evaluate the live model against the same twelve cases and record pass rates per
#   model and prompt version.
# - Package the agent behind a small web UI while keeping the same tool boundary.
