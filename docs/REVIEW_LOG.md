# Review log

One row per commit. Do not tick a box until you have run the command and read the output.

| Commit | What it does | Test command | Result | Notebook run? | Secrets scan | I can explain it? |
|---|---|---|---|---|---|---|
| `f114a97` | Project skeleton and docs | `python scripts/check_secrets.py` | Clean | Yes, build check | Clean | Pending |
| `4db52c0` | SQLite layer | `pytest tests/test_task_manager.py -q` | 8 passed | Yes, executed | Clean | Pending |
| `6124d98` | Date parsing and matching | `pytest tests/test_task_manager.py -q` | 13 passed | Yes, executed | Clean | Pending |
| `8306440` | Four tools and result shape | `pytest tests/test_task_manager.py -q` | 23 passed | Yes, executed | Clean | Pending |
| `0cd777e` | Offline intent parser | `pytest tests/test_task_manager.py -q` | 29 passed | Yes, executed | Clean | Pending |
| `a7938e0` | Optional LLM client and provider check | `pytest tests/test_task_manager.py -q` | 32 passed | Yes, executed | Clean | Pending |
| `4fe86cd` | Agent loop with offline fallback | `pytest tests/test_task_manager.py -q` | 44 passed | Yes, executed | Clean | Pending |
| `240531a` | Twelve-case offline evaluation | `pytest tests/test_task_manager.py -q` | 45 passed | Build failed, BOM found | Clean | Pending |
| `3bcf19e` | Remove stray BOM | `pytest tests/test_task_manager.py -q` | 45 passed | Yes, executed | Clean | Pending |
| Final working tree | Full notebook sections and docs | `pytest tests/test_task_manager.py -q` | 46 passed; eval 12/12 | Yes, executed | Clean | Pending |

## Notes

- The live provider check is still pending. See `docs/PROVIDER_NOTES.md`.
- The notebook's demo cell uses the offline parser, so the recorded outputs do not
  depend on a key or network access.
- The `I can explain it?` column is for the human reviewer to fill after reading the
  diff. It is intentionally not pre-filled.
