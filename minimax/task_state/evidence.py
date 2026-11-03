import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from context_module.catalog import collect_documents, revision


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(root, path):
    root = Path(root).resolve()
    path = Path(path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Evidence file must exist inside project: {path}")
    return {"source_path": path.relative_to(root).as_posix(), "sha256": sha256(path)}


def latest_test(root, phase, suite):
    candidates = []
    for path in (root / "evidence" / phase).glob(f"{suite}_*.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        if item.get("label") == phase and item.get("suite") == suite:
            candidates.append((item.get("started_at_utc", ""), path, item))
    if not candidates:
        raise ValueError(f"Missing test evidence; run: python tools/run_tests.py {suite} --label {phase}")
    _, path, item = max(candidates, key=lambda candidate: (candidate[0], candidate[1].name))
    expected = 1 if phase == "before" and suite == "target" else 0
    if item.get("exit_code") != expected:
        raise ValueError(f"Latest {phase}/{suite} result has exit_code={item.get('exit_code')}; expected {expected}.")
    output = item.get("output", "")
    if expected == 1 and ("AssertionError" not in output or "failures=" not in output
                         or re.search(r"^ERROR:", output, flags=re.MULTILINE) or "errors=" in output):
        raise ValueError("Before-target failure must be an assertion failure, not an environment error.")
    manifest = item.get("file_sha256")
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("Test evidence does not contain a source manifest.")
    for relative, expected_hash in manifest.items():
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or not source.is_file() or sha256(source) != expected_hash:
            raise ValueError(f"Current source differs from {phase}/{suite} evidence: {relative}; rerun tests.")
    summary = [line.strip() for line in output.splitlines()
               if line.startswith("Ran ") or line == "OK" or line.startswith("FAILED (")]
    return {"suite": suite, "phase": phase, "exit_code": item["exit_code"],
            "code_version": item["code_version"], "summary": summary, "log": receipt(root, path)}


def check_fixed_tests(root):
    path = root / "snapshots/before_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for relative, expected_hash in manifest.items():
        if relative.startswith("tests/"):
            current = (root / relative).resolve()
            if not current.is_relative_to(root) or not current.is_file() or sha256(current) != expected_hash:
                raise ValueError(f"Fixed test file changed from the initial snapshot: {relative}")


def context_receipts(root):
    current_path = root / ".runtime/context.json"
    context = json.loads(current_path.read_text(encoding="utf-8"))
    if context.get("schema") != "minimax-sdd-context-v1" or context.get("database", {}).get("engine") != "seekdb":
        raise ValueError("Expected actual seekdb context; run the context_module ingest/context commands first.")
    if context.get("project_revision") != revision(collect_documents(root)):
        raise ValueError("Context is stale; re-import and query the current engineering sources first.")
    same = [path for path in (root / "evidence/context").glob("*.json") if sha256(path) == sha256(current_path)]
    if not same:
        raise ValueError("The current context has no matching immutable evidence/context snapshot.")
    archived = max(same, key=lambda path: path.name)
    queries = []
    for path in (root / "evidence/database").glob("*_context.json"):
        entry = json.loads(path.read_text(encoding="utf-8"))
        if entry.get("exit_code") == 0 and entry.get("context_evidence") == archived.relative_to(root).as_posix():
            queries.append(path)
    if not queries:
        raise ValueError("No successful database query record corresponds to the current context.")
    return context, {"context": receipt(root, archived), "database_query": receipt(root, max(queries))}


def assemble_state(root, task_id, phase, process_instance_id):
    root = Path(root).resolve()
    check_fixed_tests(root)
    context, receipts = context_receipts(root)
    results = [latest_test(root, phase, suite) for suite in ("regression", "target")]
    if results[0]["code_version"] != results[1]["code_version"]:
        raise ValueError("Regression and target results must refer to the same working-tree version.")
    completed = ["工程资料已导入 seekdb", "已查询并构造开发上下文"]
    if phase == "before":
        completed += ["修改前回归测试通过", "修改前目标测试因功能未实现而失败"]
        pending = ["使用 MiniMax 实现 status 筛选", "运行修改后目标测试与回归测试",
                   "验证规格更新并重新导入", "整理提交材料"]
    else:
        completed += ["修改后目标测试通过", "修改后回归测试通过"]
        pending = ["核对 MiniMax 修改记录", "验证规格更新并重新导入", "整理提交材料"]
    return {"schema": "minimax-task-state-v1", "task_id": task_id, "phase": phase,
            "saved_at_utc": datetime.now(timezone.utc).isoformat(), "saved_process_id": os.getpid(),
            "saved_process_instance_id": process_instance_id, "task": context["task"],
            "project_revision": context["project_revision"], "completed": completed,
            "pending": pending, "validation_results": results, "receipts": receipts}


def verify_saved_receipts(root, state):
    for saved in [*state["receipts"].values(), *(result["log"] for result in state["validation_results"])]:
        current = receipt(root, root / saved["source_path"])
        if current["sha256"] != saved["sha256"]:
            raise ValueError(f"Saved evidence changed: {saved['source_path']}")


def attach_state(context, state, metadata):
    if context["project_revision"] != state["project_revision"]:
        raise ValueError("Engineering sources changed after this checkpoint; create a fresh checkpoint first.")
    merged = dict(context)
    merged["task_progress"] = {"source": "PowerContext", "task_id": state["task_id"], "phase": state["phase"],
                               "saved_at_utc": state["saved_at_utc"], "completed": state["completed"],
                               "pending": state["pending"], "validation_results": state["validation_results"],
                               "reference": metadata["reference"], "scope_id": metadata["scope_id"]}
    merged["next_action"] = state["pending"][0] if state["pending"] else "所有已登记事项已完成"
    return merged
