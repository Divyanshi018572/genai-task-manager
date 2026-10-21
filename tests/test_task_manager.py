from datetime import date

import pytest

import notebook_source as tm

TODAY = date(2026, 10, 21)  # Wednesday


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "tasks.db")
    tm.init_db(path)
    return path


def test_add_and_list_pending(db):
    result = tm.add_task("Prepare for the GenAI assignment", "2026-10-22", db_path=db)
    assert result["status"] == "success"
    listing = tm.list_tasks("pending", db_path=db)
    assert [task["title"] for task in listing] == ["Prepare for the GenAI assignment"]


def test_add_task_direct(db):
    result = tm.add_task("Read chapter", "2026-10-22", db_path=db)
    assert result["status"] == "success"
    task_id = result["data"]["task"]["id"]
    assert tm.get_task(task_id, db_path=db)["title"] == "Read chapter"


def test_add_rejects_empty_title(db):
    result = tm.add_task("   ", "2026-10-22", db_path=db)
    assert result["status"] == "error"
    assert "title" in result["message"].lower()


def test_add_rejects_invalid_date(db):
    result = tm.add_task("Buy milk", "2026-02-30", db_path=db)
    assert result["status"] == "invalid_date"


def test_complete_changes_status(db):
    added = tm.add_task("Python assignment", "2026-10-22", db_path=db)
    task_id = added["data"]["task"]["id"]
    assert tm.complete_task(task_id, db_path=db) is True
    assert tm.get_task(task_id, db_path=db)["status"] == "completed"


def test_complete_twice_returns_false(db):
    added = tm.add_task("Python assignment", "2026-10-22", db_path=db)
    task_id = added["data"]["task"]["id"]
    assert tm.complete_task(task_id, db_path=db) is True
    assert tm.complete_task(task_id, db_path=db) is False


def test_get_task_missing_returns_none(db):
    assert tm.get_task(999, db_path=db) is None


def test_persistence_after_reopen(db):
    tm.add_task("Read chapter", "2026-10-22", db_path=db)
    listing = tm.list_tasks("pending", db_path=db)
    assert len(listing) == 1
    assert listing[0]["due_date"] == "2026-10-22"


def test_parse_dates():
    assert tm.parse_due_date("by tomorrow", TODAY)[0] == "2026-10-22"
    assert tm.parse_due_date("today", TODAY)[0] == "2026-10-21"
    assert tm.parse_due_date("in 3 days", TODAY)[0] == "2026-10-24"
    assert tm.parse_due_date("next Friday", TODAY)[0] == "2026-10-23"
    assert tm.parse_due_date("2026-10-25", TODAY)[0] == "2026-10-25"
    assert tm.parse_due_date("25 Oct 2026", TODAY)[0] == "2026-10-25"
    assert tm.parse_due_date("25 October 2026", TODAY)[0] == "2026-10-25"


def test_parse_weekday_on_same_day():
    friday = date(2026, 10, 23)
    assert tm.parse_due_date("Friday", friday)[0] == "2026-10-23"
    assert tm.parse_due_date("next Friday", friday)[0] == "2026-10-30"


def test_parse_invalid_date():
    iso, phrase, error = tm.parse_due_date("32nd of Feb", TODAY)
    assert iso is None
    assert phrase == "32nd of feb"
    assert error


def test_extract_title():
    assert tm.extract_create_title(
        "Add a task to prepare for the GenAI assignment by tomorrow.", "tomorrow"
    ) == "Prepare for the GenAI assignment"
    assert tm.extract_create_title(
        "Add task: submit report on 25 Oct 2026", "25 Oct 2026"
    ) == "Submit report"


def test_matching_is_case_insensitive(db):
    tm.add_task("Python assignment", "2026-10-22", db_path=db)
    matches = tm.find_tasks("mark PYTHON assignment done", status="pending", db_path=db)
    assert len(matches) == 1
    assert matches[0]["title"] == "Python assignment"

