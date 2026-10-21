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


def test_list_tasks_empty(db):
    result = tm.tool_list_tasks("pending", db_path=db)
    assert result["status"] == "success"
    assert result["data"]["tasks"] == []
    assert "no pending" in result["message"].lower()


def test_complete_by_id(db):
    added = tm.tool_add_task("Read chapter", "2026-10-22", db_path=db)
    task_id = added["data"]["task"]["id"]
    result = tm.tool_complete_task(str(task_id), db_path=db)
    assert result["status"] == "success"


def test_details_not_found(db):
    result = tm.tool_get_task_details("Gym", db_path=db)
    assert result["status"] == "not_found"


def test_list_completed(db):
    tm.tool_add_task("Read chapter", "2026-10-22", db_path=db)
    tm.tool_complete_task("Read chapter", db_path=db)
    result = tm.tool_list_tasks("completed", db_path=db)
    assert len(result["data"]["tasks"]) == 1


def test_invalid_status(db):
    result = tm.tool_list_tasks("everything", db_path=db)
    assert result["status"] == "error"


def test_tool_add_needs_due_date(db):
    result = tm.tool_add_task("Buy milk", None, db_path=db)
    assert result["status"] == "needs_due_date"


def test_tool_invalid_date(db):
    result = tm.tool_add_task("Buy milk", "2026-02-30", db_path=db)
    assert result["status"] == "invalid_date"


def test_complete_ambiguous(db):
    tm.tool_add_task("Python assignment", "2026-10-22", db_path=db)
    tm.tool_add_task("GenAI assignment", "2026-10-23", db_path=db)
    result = tm.tool_complete_task("assignment", db_path=db)
    assert result["status"] == "ambiguous"
    assert len(result["data"]["candidates"]) == 2


def test_already_completed(db):
    tm.tool_add_task("Python assignment", "2026-10-22", db_path=db)
    tm.tool_complete_task("Python assignment", db_path=db)
    result = tm.tool_complete_task("Python assignment", db_path=db)
    assert result["status"] == "already_completed"


def test_details_include_due_and_status(db):
    tm.tool_add_task("GenAI assignment", "2026-10-22", db_path=db)
    result = tm.tool_get_task_details("GenAI assignment", db_path=db)
    assert result["status"] == "success"
    task = result["data"]["task"]
    assert task["due_date"] == "2026-10-22"
    assert task["status"] == "pending"


def test_local_parser_examples():
    call = tm.parse_local_intent(
        "Add a task to prepare for the GenAI assignment by tomorrow.", TODAY
    )
    assert call["name"] == "add_task"
    assert call["arguments"]["due_date"] == "2026-10-22"
    assert call["arguments"]["title"] == "Prepare for the GenAI assignment"

    call = tm.parse_local_intent("Show me all my pending tasks.", TODAY)
    assert call["name"] == "list_tasks"
    assert call["arguments"]["status"] == "pending"

    call = tm.parse_local_intent("Mark the Python assignment as completed.", TODAY)
    assert call["name"] == "complete_task"
    assert "python assignment" in call["arguments"]["task_ref"].lower()


def test_local_parser_missing_due_date():
    call = tm.parse_local_intent("Add a task to buy milk.", TODAY)
    assert call["name"] == "add_task"
    assert call["arguments"]["due_date"] is None


def test_local_parser_add_with_finish_word():
    call = tm.parse_local_intent("Add a task to finish the Python assignment by 2026-10-28.", TODAY)
    assert call["name"] == "add_task"
    assert call["arguments"]["title"] == "Finish the Python assignment"
    assert call["arguments"]["due_date"] == "2026-10-28"


def test_local_parser_details():
    call = tm.parse_local_intent("When is the GenAI assignment due?", TODAY)
    assert call["name"] == "get_task_details"
    assert "genai assignment" in call["arguments"]["task_ref"].lower()


def test_local_parser_unknown():
    assert tm.parse_local_intent("Tell me a joke.", TODAY) is None


def test_local_parser_invalid_date():
    call = tm.parse_local_intent("Add a task to buy milk by 32nd of Feb.", TODAY)
    assert call["name"] == "add_task"
    assert call["arguments"]["due_date"] == "__invalid__"


def test_local_parser_pending_not_all():
    call = tm.parse_local_intent("Show me all my pending tasks.", TODAY)
    assert call["arguments"]["status"] == "pending"


def test_fake_llm_returns_responses():
    fake = tm.FakeLLM([{"type": "text", "content": "hello"}])
    assert fake([], [])["content"] == "hello"
    assert fake([], [])["type"] == "error"


def test_load_configs_requires_base_url(monkeypatch):
    monkeypatch.setattr(tm, "load_dotenv", None, raising=False)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_FALLBACK_API_KEY", raising=False)
    assert tm.load_llm_configs() == []


def test_load_configs_reads_primary(monkeypatch):
    monkeypatch.setattr(tm, "load_dotenv", None, raising=False)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.delenv("LLM_FALLBACK_API_KEY", raising=False)
    configs = tm.load_llm_configs()
    assert len(configs) == 1
    assert configs[0].model == "test-model"
    assert configs[0].base_url == "https://example.test/v1"


def test_agent_offline(db):
    agent = tm.Agent(db_path=db, today=TODAY, llm_call=lambda messages, tools: {"type": "unavailable"})
    assert TODAY.isoformat() in agent.messages[0]["content"]
    reply = agent.chat("Add a task to buy milk by tomorrow.")
    assert "Buy milk" in reply
    assert "2026-10-22" in reply
    assert agent.fallback_used is True


def test_agent_unknown(db):
    agent = tm.Agent(db_path=db, today=TODAY, llm_call=lambda messages, tools: {"type": "unavailable"})
    reply = agent.chat("Tell me a joke.")
    assert "add" in reply.lower()
    assert "list" in reply.lower()


def test_fake_llm_tool_call_then_text(db):
    fake = tm.FakeLLM([
        {"type": "tool_calls", "calls": [{"id": "1", "name": "add_task", "arguments": {"title": "Read chapter", "due_date": "2026-10-22"}}]},
        {"type": "text", "content": "Added Read chapter for 2026-10-22."},
    ])
    agent = tm.Agent(db_path=db, today=TODAY, llm_call=fake)
    reply = agent.chat("Add a task to read a chapter by tomorrow.")
    assert "Added" in reply
    assert agent.fallback_used is False
    listing = tm.tool_list_tasks("pending", db_path=db)
    assert listing["data"]["tasks"][0]["title"] == "Read chapter"


def test_llm_error_falls_back_to_local_parser(db):
    fake = tm.FakeLLM([{"type": "error", "message": "provider down"}, {"type": "error", "message": "provider down"}])
    agent = tm.Agent(db_path=db, today=TODAY, llm_call=fake)
    reply = agent.chat("Add a task to buy milk by tomorrow.")
    assert "Buy milk" in reply
    assert agent.fallback_used is True


def test_agent_text_only_falls_back_to_parser(db):
    fake = tm.FakeLLM([{"type": "text", "content": "I think I added that."}])
    agent = tm.Agent(db_path=db, today=TODAY, llm_call=fake)
    reply = agent.chat("Add a task to buy milk by tomorrow.")
    assert "Buy milk" in reply
    listing = tm.tool_list_tasks("pending", db_path=db)
    assert listing["data"]["tasks"][0]["title"] == "Buy milk"


def test_agent_ambiguous(db):
    tm.tool_add_task("Python assignment", "2026-10-22", db_path=db)
    tm.tool_add_task("Python reading", "2026-10-23", db_path=db)
    fake = tm.FakeLLM([
        {"type": "tool_calls", "calls": [{"id": "1", "name": "complete_task", "arguments": {"task_ref": "Python"}}]},
        {"type": "text", "content": "Which one do you mean?"},
    ])
    agent = tm.Agent(db_path=db, today=TODAY, llm_call=fake)
    reply = agent.chat("Complete Python.")
    assert "Which one" in reply


def test_agent_needs_due_date(db):
    fake = tm.FakeLLM([
        {"type": "tool_calls", "calls": [{"id": "1", "name": "add_task", "arguments": {"title": "Buy milk"}}]},
        {"type": "text", "content": "What due date should I use for Buy milk?"},
    ])
    agent = tm.Agent(db_path=db, today=TODAY, llm_call=fake)
    reply = agent.chat("Add a task to buy milk.")
    assert "due date" in reply.lower()
    assert tm.tool_list_tasks("pending", db_path=db)["data"]["tasks"] == []


def test_agent_already_completed(db):
    added = tm.tool_add_task("Python assignment", "2026-10-22", db_path=db)
    tm.tool_complete_task(str(added["data"]["task"]["id"]), db_path=db)
    fake = tm.FakeLLM([
        {"type": "tool_calls", "calls": [{"id": "1", "name": "complete_task", "arguments": {"task_ref": "Python assignment"}}]},
        {"type": "text", "content": "It is already completed."},
    ])
    agent = tm.Agent(db_path=db, today=TODAY, llm_call=fake)
    reply = agent.chat("Complete Python assignment.")
    assert "already completed" in reply.lower()


def test_agent_invalid_date(db):
    fake = tm.FakeLLM([
        {"type": "tool_calls", "calls": [{"id": "1", "name": "add_task", "arguments": {"title": "Buy milk", "due_date": "2026-02-30"}}]},
        {"type": "text", "content": "That date is not valid."},
    ])
    agent = tm.Agent(db_path=db, today=TODAY, llm_call=fake)
    reply = agent.chat("Add a task to buy milk by 30 Feb.")
    assert "not valid" in reply.lower()


def test_agent_list(db):
    tm.tool_add_task("Read chapter", "2026-10-22", db_path=db)
    fake = tm.FakeLLM([
        {"type": "tool_calls", "calls": [{"id": "1", "name": "list_tasks", "arguments": {"status": "pending"}}]},
        {"type": "text", "content": "You have 1 pending task: Read chapter."},
    ])
    agent = tm.Agent(db_path=db, today=TODAY, llm_call=fake)
    reply = agent.chat("What are my pending tasks?")
    assert "Read chapter" in reply


def test_agent_details(db):
    tm.tool_add_task("GenAI assignment", "2026-10-22", db_path=db)
    fake = tm.FakeLLM([
        {"type": "tool_calls", "calls": [{"id": "1", "name": "get_task_details", "arguments": {"task_ref": "GenAI assignment"}}]},
        {"type": "text", "content": "It is due on 2026-10-22 and is pending."},
    ])
    agent = tm.Agent(db_path=db, today=TODAY, llm_call=fake)
    reply = agent.chat("When is GenAI assignment due?")
    assert "2026-10-22" in reply
    assert "pending" in reply.lower()


def test_agent_keeps_tool_messages_out_of_jupyter(db):
    class InspectingLLM:
        def __init__(self):
            self.calls = 0
            self.sent = []

        def __call__(self, messages, tools):
            self.calls += 1
            self.sent = list(messages)
            if self.calls == 1:
                return {"type": "tool_calls", "calls": [{"id": "1", "name": "list_tasks", "arguments": {"status": "pending"}}]}
            return {"type": "text", "content": "No pending tasks."}

    llm = InspectingLLM()
    agent = tm.Agent(db_path=db, today=TODAY, llm_call=llm)
    agent.chat("List pending tasks.")
    assert any(message.get("role") == "tool" for message in llm.sent)


def test_eval_offline_all_cases():
    results = tm.run_eval_cases()
    failed = [result for result in results if not result["passed"]]
    assert len(results) == 12
    assert failed == []


def test_normalize_check_text_handles_unicode_dashes():
    assert tm.normalize_check_text("due 2026\u201110\u201122") == "due 2026-10-22"







