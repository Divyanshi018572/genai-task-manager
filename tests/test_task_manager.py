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
