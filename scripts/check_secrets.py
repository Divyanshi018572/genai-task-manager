from pathlib import Path
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"nvapi-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
    re.compile(r"LLM_API_KEY[ \t]*=[ \t]*[^\s#]+"),
    re.compile(r"LLM_FALLBACK_API_KEY[ \t]*=[ \t]*[^\s#]+"),
]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ipynb_checkpoints"}
SKIP_FILES = {".env", "requirements-lock.txt"}

def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        yield path

def main() -> int:
    findings = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(ROOT)}:{line}: {pattern.pattern}")
    if findings:
        print("Potential secrets found:")
        for finding in findings:
            print("  " + finding)
        return 1
    print("No secret patterns found.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
