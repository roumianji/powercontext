import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from context_module.__main__ import write_json
from task_state.evidence import check_fixed_tests
from . import api
from .change import TARGET, atomic_write, diff, parse_change, sha256


def run_command(root, command, record):
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True)
    result = {"command": command, "exit_code": completed.returncode,
              "stdout": completed.stdout, "stderr": completed.stderr}
    record.setdefault("commands", []).append(result)
    print(completed.stdout, end="", flush=True)
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr, flush=True)
    return completed.returncode


def prepare_context(root, task_id, record):
    command = [sys.executable, "-m", "task_state", "--task-id", task_id, "resume"]
    if run_command(root, command, record) != 0:
        raise ValueError("任务恢复失败；先根据上面的 task_state 输出修复。")
    path = root / ".runtime/context_with_state.json"
    raw = path.read_bytes()
    context = json.loads(raw)
    progress = context.get("task_progress", {})
    if context.get("database", {}).get("engine") != "seekdb" or progress.get("source") != "PowerContext":
        raise ValueError("上下文必须来自 seekdb，并包含从 PowerContext 恢复的进度。")
    if progress.get("phase") != "before":
        raise ValueError("当前任务已进入修改后阶段；如需补做收尾，请使用 finalize，不要重复调用模型。")
    paths = {item["source_path"] for item in context["documents"]}
    required = {"specs/task_list.md", TARGET, "demo_app/__main__.py", "tests/test_target.py", "tests/test_regression.py", "data/tasks.json"}
    if not required.issubset(paths):
        raise ValueError("上下文缺少验证样例要求的必要规格、代码、测试或数据来源。")
    for item in context["documents"]:
        source = (root / item["source_path"]).resolve()
        if not source.is_relative_to(root) or not source.is_file() or sha256(source.read_bytes()) != item["sha256"]:
            raise ValueError("上下文来源已变化，请重新导入并保存任务状态。")
    return context, raw


def finalize_steps(root, record):
    steps = [
        [sys.executable, "-m", "context_module", "ingest"],
        [sys.executable, "-m", "context_module", "context", "--task", record["task"]],
        [sys.executable, "-m", "task_state", "--task-id", record["task_id"], "checkpoint", "--phase", "after"],
        [sys.executable, "-m", "task_state", "--task-id", record["task_id"], "resume"],
    ]
    for command in steps:
        if run_command(root, command, record) != 0:
            record["failed_finalize_command"] = command
            raise RuntimeError("代码测试已通过，但收尾步骤失败；修复后执行 python -m coding_assistant finalize，无需重新调用模型。")


def run(root, config, task_id):
    root = Path(root).resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + uuid.uuid4().hex[:8]
    directory = root / "evidence/minimax" / run_id
    directory.mkdir(parents=True)
    record_path = directory / "record.json"
    record = {"schema": "minimax-coding-run-v1", "provider": "MiniMax", "task_id": task_id,
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "python_version": sys.version,
              "configuration": config.public(), "automatic_retries": 0, "commands": [],
              "model_called": False, "code_validated": False, "rolled_back": False, "exit_code": None}
    original = None
    applied = False
    target = (root / TARGET).resolve()
    exit_code = 0
    try:
        check_fixed_tests(root)
        context, raw_context = prepare_context(root, task_id, record)
        record["task"] = context["task"]
        record["input_context_sha256"] = sha256(raw_context)
        record["powercontext_reference"] = context["task_progress"]["reference"]
        (directory / "input_context.json").write_bytes(raw_context)
        body = api.request_body(context, config)
        write_json(directory / "request_body.json", body)
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError("目标业务文件不存在或不在工程目录内。")
        original = target.read_bytes()
        record["before_sha256"] = sha256(original)
        print(f"正在调用 MiniMax：{config.model}，本次最多一次请求……", flush=True)
        record["model_called"] = True
        record["status"] = "request_started"
        write_json(record_path, record)
        text, metadata = api.call(config, body)
        record["model_response"] = metadata
        (directory / "response_text.txt").write_text(text + "\n", encoding="utf-8")
        if metadata.get("stop_reason") == "max_tokens":
            raise ValueError("模型输出达到上限，可能不完整；本次未应用代码。")
        if not text:
            raise ValueError("模型没有返回可用的文本代码；请检查记录中的 stop_reason 和用量。")
        candidate, summary = parse_change(text, original.decode("utf-8"))
        before_path = directory / "before" / TARGET
        after_path = directory / "after" / TARGET
        before_path.parent.mkdir(parents=True)
        after_path.parent.mkdir(parents=True)
        before_path.write_bytes(original)
        after_path.write_text(candidate, encoding="utf-8")
        (directory / "code.diff").write_text(diff(original.decode("utf-8"), candidate), encoding="utf-8")
        record["summary"] = summary
        record["applied_files"] = [{"path": TARGET, "before_sha256": sha256(original),
                                     "after_sha256": sha256(candidate.encode("utf-8"))}]
        atomic_write(target, candidate.encode("utf-8"))
        applied = True
        print("模型修改已应用，正在运行固定目标测试和回归测试……", flush=True)
        codes = [run_command(root, [sys.executable, "tools/run_tests.py", suite, "--label", "after"], record)
                 for suite in ("target", "regression")]
        record["test_exit_codes"] = {"target": codes[0], "regression": codes[1]}
        check_fixed_tests(root)
        if codes != [0, 0]:
            raise ValueError("修改后测试未全部通过；保留候选和日志，并恢复修改前业务代码。")
        record["code_validated"] = True
        record["status"] = "code_validated"
        write_json(record_path, record)
        print("两组测试均通过，正在更新工程资料与 PowerContext 进度……", flush=True)
        finalize_steps(root, record)
        record["status"] = "completed"
        print("MiniMax 修改、目标/回归测试及修改后状态复用均已完成。", flush=True)
    except (Exception, KeyboardInterrupt) as error:
        exit_code = 130 if isinstance(error, KeyboardInterrupt) else 1
        if applied and original is not None and not record["code_validated"]:
            atomic_write(target, original)
            record["rolled_back"] = True
        record["status"] = "finalize_failed" if record["code_validated"] else "failed"
        message = "用户中断本次运行" if isinstance(error, KeyboardInterrupt) else api.redact(error, config.api_key)
        record["error"] = {"type": type(error).__name__, "message": message}
        print("失败：" + message, file=sys.stderr, flush=True)
    finally:
        record["exit_code"] = exit_code
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        if target.is_file():
            record["final_source_sha256"] = sha256(target.read_bytes())
        write_json(record_path, record)
        print(f"本次开发记录：{record_path.relative_to(root)}", flush=True)
    return exit_code


def finalize(root):
    root = Path(root).resolve()
    candidates = []
    for path in (root / "evidence/minimax").glob("*/record.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        files = record.get("applied_files", [])
        if (record.get("provider") == "MiniMax" and record.get("model_called") and record.get("code_validated")
                and len(files) == 1 and files[0].get("path") == TARGET
                and files[0].get("after_sha256") == sha256((root / TARGET).read_bytes())):
            candidates.append((path, record))
    if not candidates:
        raise ValueError("没有与当前业务代码匹配、且已通过测试的 MiniMax 修改记录。")
    path, record = max(candidates, key=lambda item: item[1]["started_at_utc"])
    try:
        check_fixed_tests(root)
        finalize_steps(root, record)
        record["status"], record["exit_code"] = "completed", 0
        record.pop("error", None)
        record.pop("failed_finalize_command", None)
        print("收尾完成；本命令未调用模型。", flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        code = 130 if isinstance(error, KeyboardInterrupt) else 1
        record["status"], record["exit_code"] = "finalize_failed", code
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        print(f"收尾失败：{error}", file=sys.stderr, flush=True)
        return code
    finally:
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(path, record)
        print(f"开发记录：{path.relative_to(root)}", flush=True)
