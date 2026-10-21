# Provider Notes

Status: **PENDING MANUAL CHECK**.

No key was pasted into the build session or written to this file. Run the command
below in your own terminal, then replace the pending rows with the observed output.

## Command

```powershell
.\.venv\Scripts\python.exe scripts\check_provider.py
```

## Record

| Date | Provider | Base URL | Model | Result | Observed reply or error |
|------|----------|----------|-------|--------|-------------------------|
| PENDING | NVIDIA | `https://integrate.api.nvidia.com/v1` | `openai/gpt-oss-20b` | Pending | Run the command above. |
| PENDING | NVIDIA backup | `https://integrate.api.nvidia.com/v1` | `nvidia/nemotron-3.5-lightning-30b-a3b` | Pending | Run with the fallback variables set. |

## Review checkpoint

The rule for this project is: no model or endpoint is treated as verified until a
real, dated output from `scripts/check_provider.py` is copied into the table above.
Do not fill these rows from memory or from documentation alone.
