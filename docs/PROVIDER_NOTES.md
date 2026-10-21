# Provider Notes

Status: **VERIFIED 2026-10-21**.

No key was pasted into the build session or written to this file. The checks below
were run from the project virtual environment with the local `.env` file.

## Text check

```powershell
.\.venv\Scripts\python.exe scripts\check_provider.py
```

Observed:

```text
primary: model=nvidia/nemotron-3.5-lightning-30b-a3b base_url=https://integrate.api.nvidia.com/v1
  text: provider check ok
```

## Live tool-call check

The agent was run against a fresh temporary database with the real provider:

```text
USER:  Add a task to submit the GenAI assignment by tomorrow.
TOOL:  add_task {"title": "Submit GenAI assignment", "due_date": "2026-10-22"}
REPLY: Added task "Submit GenAI assignment" due 2026-10-22.

USER:  Show me all my pending tasks.
TOOL:  list_tasks {"status": "pending"}
REPLY: Pending tasks:
       - Submit GenAI assignment (due 2026-10-22)
```

`FALLBACK: False` in both turns, so the model completed the tool calls directly.
Relative dates now resolve against the date injected into the system prompt
(`2026-10-21` in the check).

## Record

| Date | Provider | Base URL | Model | Result | Observed reply or error |
|------|----------|----------|-------|--------|-------------------------|
| 2026-10-21 | NVIDIA | `https://integrate.api.nvidia.com/v1` | `nvidia/nemotron-3.5-lightning-30b-a3b` | Pass | `text: provider check ok` |
| 2026-10-21 | NVIDIA | `https://integrate.api.nvidia.com/v1` | `openai/gpt-oss-20b` | Fail | `APITimeoutError` on repeated checks |

## Decision

`nvidia/nemotron-3.5-lightning-30b-a3b` is the default model. `openai/gpt-oss-20b`
timed out twice on this network, so it is not the primary path. The fallback key is
left blank by default; the notebook still works offline when no provider is
configured.

## Review checkpoint

Do not change the table from memory. Re-run `scripts/check_provider.py` and the live
tool-call check before recording a new model or endpoint.
