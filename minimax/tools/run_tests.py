"""Execute an unchanged test suite and retain commands, source identity and results."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def hashes():
    result = {}
    for directory in ("demo_app", "tests", "specs", "data", "tools"):
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                result[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=("regression", "target"))
    parser.add_argument("--label", required=True, help="e.g. before or after")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        parser.error("label may contain only letters, digits, underscores and hyphens")
    command = [sys.executable, "-m", "unittest", "-v", f"tests.test_{args.suite}"]
    source_hashes = hashes()
    identity = hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest()
    started_at = datetime.now(timezone.utc).isoformat()
    version = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True)
    git_head = version.stdout.strip() if version.returncode == 0 else None
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    output = completed.stdout + completed.stderr
    print(output, end="", flush=True)
    record = {
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "working_directory": str(ROOT),
        "exit_code": completed.returncode,
        "python_version": sys.version,
        "git_head": git_head,
        "code_version": identity,
        "note": "code_version hashes the delivered working-tree files; git_head alone may predate uncommitted files",
        "file_sha256": source_hashes,
        "suite": args.suite,
        "label": args.label,
        "output": output,
    }
    directory = ROOT / "evidence" / args.label
    directory.mkdir(parents=True, exist_ok=True)
    # Never overwrite an earlier result, so a later rerun cannot erase evidence.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    path = directory / f"{args.suite}_{stamp}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nexit_code={completed.returncode}; evidence={path.relative_to(ROOT)}", flush=True)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
