from __future__ import annotations

import os
from datetime import date

import streamlit as st

import notebook_source as tm


def offline_llm(messages: list[dict], tools: list[dict]) -> dict:
    return {"type": "unavailable", "message": "Offline mode."}


def build_agent(mode: str, db_path: str, today: date | None = None) -> tm.Agent:
    if mode == "offline":
        return tm.Agent(db_path=db_path, today=today, llm_call=offline_llm)
    if mode == "live":
        return tm.Agent(db_path=db_path, today=today, llm_call=tm.call_llm)
    raise ValueError(f"Unknown assistant mode: {mode}")


def build_task_rows(db_path: str, today: date | None = None) -> list[dict]:
    today_iso = (today or date.today()).isoformat()
    rows = []
    for task in tm.list_tasks("all", db_path):
        rows.append(
            {
                "ID": task["id"],
                "Title": task["title"],
                "Due": task["due_date"],
                "Status": task["status"],
                "Overdue": task["status"] == "pending" and task["due_date"] < today_iso,
            }
        )
    return rows


def main() -> None:
    st.set_page_config(page_title="AI Personal Task Manager", page_icon="âœ…", layout="wide")

    db_path = os.getenv("TASK_DB_PATH", "ui_tasks.db")
    tm.init_db(db_path)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        st.title("Task Manager")
        st.caption("A small agent over a local SQLite database.")
        st.divider()

        mode_label = st.radio(
            "Assistant mode",
            ["Offline parser", "NVIDIA model"],
            help="Offline needs no key. NVIDIA mode uses the values in .env.",
        )
        mode = "live" if mode_label == "NVIDIA model" else "offline"

        configs = tm.load_llm_configs()
        if mode == "live" and configs:
            st.success(f"Configured: {configs[0].model}")
        elif mode == "live":
            st.warning("No provider configured. The agent will fall back offline.")
        else:
            st.caption("Deterministic local parser. No API key needed.")

        agent_key = (mode, db_path)
        previous_key = st.session_state.get("agent_key")
        if previous_key != agent_key:
            st.session_state.agent = build_agent(mode, db_path)
            st.session_state.agent_key = agent_key
            if previous_key is not None:
                st.session_state.messages = []

        st.divider()
        if st.button("Clear chat", width="stretch"):
            st.session_state.messages = []
            st.session_state.agent = build_agent(mode, db_path)
            st.rerun()

        confirm_reset = st.checkbox("Confirm database reset")
        if st.button("Reset database", disabled=not confirm_reset, width="stretch"):
            tm.reset_database(db_path)
            st.session_state.messages = []
            st.session_state.agent = build_agent(mode, db_path)
            st.rerun()

    st.title("AI Personal Task Manager")
    st.caption("Chat naturally, or use the forms. Every action updates the local database.")

    chat_col, task_col = st.columns([1.15, 1], gap="large")

    with chat_col:
        st.subheader("Chat")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        prompt = st.chat_input("e.g. Add submit the report tomorrow")
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        reply = st.session_state.agent.chat(prompt)
                    except Exception as error:
                        reply = f"Something went wrong: {error}"
                st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})

    with task_col:
        header_col, refresh_col = st.columns([3, 1])
        with header_col:
            st.subheader("Tasks")
        with refresh_col:
            if st.button("Refresh", width="stretch"):
                st.rerun()

        rows = build_task_rows(db_path)
        if rows:
            st.dataframe(
                rows,
                width="stretch",
                hide_index=True,
                column_config={
                    "ID": st.column_config.NumberColumn("ID", width="small"),
                    "Overdue": st.column_config.CheckboxColumn("Overdue"),
                },
            )
        else:
            st.info("No tasks yet. Add one below or ask the assistant.")

        with st.expander("Add a task", expanded=True):
            with st.form("add_task_form", clear_on_submit=True):
                title = st.text_input("Title", placeholder="Submit the report")
                due_date = st.date_input("Due date", value=date.today())
                submitted = st.form_submit_button("Add task", width="stretch")
                if submitted:
                    if not title.strip():
                        st.warning("Enter a task title.")
                    else:
                        result = tm.tool_add_task(title, due_date.isoformat(), db_path)
                        if result["status"] == "success":
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.warning(result["message"])

        pending = tm.list_tasks("pending", db_path)
        if pending:
            labels = {
                f"#{task['id']} â€” {task['title']} (due {task['due_date']})": task["id"]
                for task in pending
            }
            with st.expander("Complete a task", expanded=True):
                with st.form("complete_task_form"):
                    choice = st.selectbox("Pending task", list(labels))
                    submitted = st.form_submit_button("Mark completed", width="stretch")
                    if submitted:
                        result = tm.tool_complete_task(str(labels[choice]), db_path)
                        if result["status"] == "success":
                            st.success(result["message"])
                            st.rerun()
                        else:
                            st.warning(result["message"])

        all_tasks = tm.list_tasks("all", db_path)
        if all_tasks:
            detail_labels = {
                f"#{task['id']} â€” {task['title']}": task["id"] for task in all_tasks
            }
            with st.expander("Task details"):
                choice = st.selectbox("Task", list(detail_labels), key="detail_choice")
                task = tm.get_task(detail_labels[choice], db_path)
                if task:
                    st.markdown(f"**{task['title']}**")
                    st.write(f"Status: `{task['status']}`")
                    st.write(f"Due: `{task['due_date']}`")
                    st.write(f"Created: `{task['created_at']}`")
                    if task["completed_at"]:
                        st.write(f"Completed: `{task['completed_at']}`")


if __name__ == "__main__":
    main()

