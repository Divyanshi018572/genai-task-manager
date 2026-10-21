from datetime import date

import pytest

import notebook_source as tm
from streamlit_app import build_agent, build_task_rows, offline_llm


def test_task_rows_include_status_and_overdue(tmp_path):
    db_path = str(tmp_path / "ui.db")
    tm.init_db(db_path)
    first = tm.add_task("Overdue task", "2020-01-01", db_path)["data"]["task"]
    tm.add_task("Future task", "2999-01-01", db_path)
    tm.complete_task(first["id"], db_path)

    rows = build_task_rows(db_path, today=date(2026, 10, 21))

    assert [row["Title"] for row in rows] == ["Overdue task", "Future task"]
    assert rows[0]["Status"] == "completed"
    assert rows[0]["Overdue"] is False
    assert rows[1]["Overdue"] is False


def test_task_rows_mark_only_pending_past_dates_overdue(tmp_path):
    db_path = str(tmp_path / "ui.db")
    tm.init_db(db_path)
    tm.add_task("Past pending", "2020-01-01", db_path)

    rows = build_task_rows(db_path, today=date(2026, 10, 21))

    assert rows[0]["Overdue"] is True


def test_offline_agent_never_needs_a_provider(tmp_path):
    db_path = str(tmp_path / "ui.db")
    tm.init_db(db_path)
    agent = build_agent("offline", db_path, today=date(2026, 10, 21))

    reply = agent.chat("add buy milk tomorrow")

    assert agent.llm_call is offline_llm
    assert agent.fallback_used is True
    assert "buy milk" in reply.lower()
    assert tm.list_tasks("pending", db_path)[0]["due_date"] == "2026-10-22"


def test_live_agent_uses_the_configured_client(tmp_path):
    db_path = str(tmp_path / "ui.db")
    tm.init_db(db_path)

    agent = build_agent("live", db_path, today=date(2026, 10, 21))

    assert agent.llm_call is tm.call_llm


def test_unknown_mode_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        build_agent("magic", str(tmp_path / "ui.db"))
