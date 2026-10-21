# Review log

One row per commit. Do not tick a box until you have run the command and read the output.

| Commit | What it does | Test command | Result | Notebook run? | Secrets scan | I can explain it? |
|---|---|---|---|---|---|---|
| `e6126f1` | Project skeleton and docs | `python scripts/check_secrets.py` | Clean | Yes, build check | Clean | Pending |
| `35dc76b` | SQLite layer | `pytest tests/test_task_manager.py -q` | 8 passed | Yes, executed | Clean | Pending |
| `f12c9c8` | Date parsing and matching | `pytest tests/test_task_manager.py -q` | 13 passed | Yes, executed | Clean | Pending |
| `069ea69` | Four tools and result shape | `pytest tests/test_task_manager.py -q` | 23 passed | Yes, executed | Clean | Pending |
| `71d36b9` | Offline intent parser | `pytest tests/test_task_manager.py -q` | 29 passed | Yes, executed | Clean | Pending |
| `f0c844c` | Optional LLM client and provider check | `pytest tests/test_task_manager.py -q` | 32 passed | Yes, executed | Clean | Pending |
| `4151dc5` | Agent loop with offline fallback | `pytest tests/test_task_manager.py -q` | 44 passed | Yes, executed | Clean | Pending |
| `fcbbf98` | Twelve-case offline evaluation | `pytest tests/test_task_manager.py -q` | 45 passed | Build failed, BOM found | Clean | Pending |
| `e5173e7` | Remove stray BOM | `pytest tests/test_task_manager.py -q` | 45 passed | Yes, executed | Clean | Pending |
| `0156fd4` | Complete notebook sections and docs | `pytest tests/test_task_manager.py -q` | 46 passed; eval 12/12 | Yes, executed | Clean | Pending |
| `2650fb6` | Inject today into prompt; verify NVIDIA provider | `pytest tests/test_task_manager.py -q` | 46 passed; live tool calls passed | Yes, executed | Clean | Pending |
| `38179f0` | Record verified provider result | — | Docs only | — | Clean | Pending |
| `3244eda` | Normalize reply checks; record live eval | `pytest tests/test_task_manager.py -q` | 47 passed; offline 12/12; live 11/12 | Yes, executed | Clean | Pending |
| `ac71a31` | Record live evaluation result | — | Docs only | — | Clean | Pending |
| `debe69f` | Deterministic completion guard | `pytest tests/test_task_manager.py -q` | 48 passed; offline 12/12; live 12/12 | Yes, executed | Clean | Pending |
| `e25e70a` | Record 12/12 live evaluation | — | Docs only | — | Clean | Pending |
| `f9ad2f8` | Correct ambiguity traceability in SPEC | — | Docs only | — | Clean | Pending |

## Notes

- The live provider check is verified. See `docs/PROVIDER_NOTES.md`.
- The notebook's demo cell uses the offline parser, so the recorded outputs do not
  depend on a key or network access.
- The `I can explain it?` column is for the human reviewer to fill after reading the
  diff. It is intentionally not pre-filled.
