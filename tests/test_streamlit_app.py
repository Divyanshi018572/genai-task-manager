from datetime import date, timedelta
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def make_app(monkeypatch, tmp_path):
    monkeypatch.setenv("TASK_DB_PATH", str(tmp_path / "ui.db"))
    return AppTest.from_file(APP_PATH, default_timeout=20).run()


def test_app_renders_offline(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)

    assert not app.exception
    assert [title.value for title in app.title] == [
        "AI Personal Task Manager",
        "Task Manager",
    ]
    assert app.info[0].value.startswith("No tasks yet")
    assert app.chat_input[0].placeholder


def test_add_form_updates_the_table(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    app.text_input[0].set_value("Write report")
    app.date_input[0].set_value(date.today() + timedelta(days=1))
    next(button for button in app.button if button.label == "Add task").click().run()

    assert not app.exception
    rows = app.dataframe[0].value.to_dict("records")
    assert rows == [
        {
            "ID": 1,
            "Title": "Write report",
            "Due": (date.today() + timedelta(days=1)).isoformat(),
            "Status": "pending",
            "Overdue": False,
        }
    ]


def test_chat_turn_updates_the_table(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    app.chat_input[0].set_value("Add a task to buy milk tomorrow.").run()

    assert not app.exception
    rows = app.dataframe[0].value.to_dict("records")
    assert rows[0]["Title"] == "Buy milk"
    assert rows[0]["Status"] == "pending"
