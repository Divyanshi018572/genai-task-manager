import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import notebook_source as tm

configs = tm.load_llm_configs()
if not configs:
    print("No LLM configured. The notebook will use the local parser.")
    raise SystemExit(0)

for config in configs:
    print(f"{config.label}: model={config.model} base_url={config.base_url}")
    result = tm.call_llm(
        [{"role": "user", "content": "Reply with exactly: provider check ok"}],
        tools=[],
        configs=[config],
    )
    if result["type"] == "text":
        preview = result["content"].strip().replace("\n", " ")[:100]
        print(f"  text: {preview}")
    elif result["type"] == "error":
        print(f"  error: {result['message']}")
    else:
        print(f"  {result['type']}: {result.get('message', '')}")
