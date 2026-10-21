# AI-Powered Personal Task Manager

A Jupyter notebook that manages tasks from natural-language requests. It creates
tasks, lists pending work, completes tasks, and shows task details. It runs offline
with a deterministic parser and can use an OpenAI-compatible model, including
NVIDIA's endpoint, when a key is configured.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Open `task_manager.ipynb` in Jupyter and run all cells. Offline mode is the default
and needs no key. The notebook creates its own demo database in the system temp
directory.

## Streamlit UI

Run the local web UI:

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Open http://localhost:8501. The sidebar switches between the offline parser and the
NVIDIA model, and includes a database reset. The main area has the chat, a live task
table, add and complete forms, and task details. The UI uses `ui_tasks.db`; override
it with the `TASK_DB_PATH` environment variable. Streamlit is a local interface and
does not run inside Google Colab.

## Google Colab

1. Go to https://colab.research.google.com.
2. Choose **File > Upload notebook** and select `task_manager.ipynb`.
3. Choose **Runtime > Run all**.

Offline mode needs no installation or key. For live model mode, uncomment the
optional setup cell in the notebook, install `openai`, and enter the key through the
hidden `getpass` prompt. Do not paste the key into a code cell or commit it.

## Optional model configuration

Copy `.env.example` to `.env` and fill in the provider values. Do not commit `.env`.

```text
LLM_API_KEY=
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b
LLM_FALLBACK_API_KEY=
LLM_FALLBACK_BASE_URL=
LLM_FALLBACK_MODEL=
```

Check the provider from your own terminal:

```powershell
.\.venv\Scripts\python.exe scripts\check_provider.py
```

Record the dated result in `docs/PROVIDER_NOTES.md`. If the provider is missing or
fails, the agent falls back to the local parser.

## Project layout

| Path | Purpose |
|---|---|
| `notebook_source.py` | Reviewable jupytext source for the notebook. |
| `task_manager.ipynb` | Generated and executed notebook deliverable. |
| `streamlit_app.py` | Local Streamlit chat-and-task interface. |
| `tests/test_task_manager.py` | Offline pytest suite. |
| `tests/test_streamlit_helpers.py` | UI helper tests. |
| `tests/test_streamlit_app.py` | Streamlit AppTest flow tests. |
| `scripts/check_provider.py` | Optional live provider smoke test. |
| `scripts/check_secrets.py` | Blocks common key patterns before commit. |
| `docs/SPEC.md` | Problem, requirements, and non-goals. |
| `docs/PLAN.md` | Approved build plan and test matrix. |
| `docs/REVIEW_LOG.md` | Commit-by-commit verification record. |

## Design

The agent asks the model for one tool call at a time. Python validates the
arguments, runs SQLite, and sends the result back to the model for a short
confirmation. Tool messages stay inside the loop; only the final reply reaches the
user. The model can choose `add_task`, `list_tasks`, `complete_task`, or
`get_task_details`. Completion requests have a deterministic guard: if the model
does not call `complete_task`, the local parser executes it.

If no model is configured, the local parser handles common English requests and
returns the same result shape. Ambiguous titles return candidate IDs, unknown
titles return suggestions, and missing or impossible dates never write a row.

## Limitations

Single user, local SQLite, English date phrases, token-overlap matching, and no
reminders or recurrence. The live model path is optional and is not exercised by
the automated tests.

